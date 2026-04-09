"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob

class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory, then split into paragraphs
        raw_docs = self.load_documents()        # List of (filename, full_text)
        self.documents = self.chunk_documents(raw_docs)  # List of (filename, chunk)

        # Build a retrieval index (implemented in Phase 1)
        self.index = self.build_index(self.documents)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    def chunk_documents(self, raw_docs):
        """
        Splits each document into paragraph-sized chunks by splitting on blank lines.
        Short chunks (under 30 chars, e.g. section headers) are prepended to the
        next chunk so their label stays attached to the content that follows.
        Returns a list of (filename, chunk) tuples.
        """
        chunks = []
        for filename, text in raw_docs:
            raw_chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
            pending = ""
            for chunk in raw_chunks:
                if len(chunk) <= 30:
                    pending = chunk
                else:
                    merged = (pending + "\n" + chunk).strip() if pending else chunk
                    chunks.append((filename, merged))
                    pending = ""
        return chunks

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def build_index(self, documents):
        """
        TODO (Phase 1):
        Build a tiny inverted index mapping lowercase words to the documents
        they appear in.

        Example structure:
        {
            "token": ["AUTH.md", "API_REFERENCE.md"],
            "database": ["DATABASE.md"]
        }

        Keep this simple: split on whitespace, lowercase tokens,
        ignore punctuation if needed.
        """
        index = {}
        for filename, text in documents:
            for word in text.lower().split():
                word = word.strip(".,!?:;\"'()[]")
                if word:
                    if word not in index:
                        index[word] = set()
                    index[word].add(filename)
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def stem(self, word):
        """
        Minimal suffix stripping to normalize word forms.
        Strips common English suffixes so that e.g. 'generated' and
        'generate' both reduce to 'generat' and match each other.
        """
        for suffix in ("ing", "tion", "ation", "ed", "er", "es", "ly", "s", "e"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                return word[:-len(suffix)]
        return word

    def score_document(self, query, text):
        """
        TODO (Phase 1):
        Return a simple relevance score for how well the text matches the query.

        Suggested baseline:
        - Convert query into lowercase words
        - Count how many appear in the text
        - Return the count as the score
        """
        stopwords = {"is", "the", "a", "an", "what", "how", "do", "does",
                     "to", "of", "in", "for", "and", "or", "on", "with"}
        text_lower = text.lower()
        score = 0
        for word in query.lower().split():
            word = word.strip(".,!?:;\"'()[]")
            if word and word not in stopwords:
                stemmed = self.stem(word)
                if stemmed in text_lower:
                    score += 1
        # Penalize top-level intro chunks (# Title) — they mention topics but don't
        # explain them. Section chunks (## Heading) contain actual content, no penalty.
        if text.lstrip().startswith("# ") and not text.lstrip().startswith("## "):
            score = max(0, score - 1)
        return score

    def retrieve(self, query, top_k=3, min_score=2):
        """
        TODO (Phase 1):
        Use the index and scoring function to select top_k relevant document snippets.

        Return a list of (filename, text) sorted by score descending.
        Capped to one chunk per file so no single document dominates results.
        Only returns chunks that meet min_score — below that threshold the
        match is too weak to be meaningful evidence.
        """
        scored = []
        for filename, text in self.documents:
            score = self.score_document(query, text)
            if score >= min_score:
                scored.append((score, filename, text))
        scored.sort(key=lambda x: x[0], reverse=True)

        seen = set()
        results = []
        for score, filename, text in scored:
            if filename not in seen:
                seen.add(filename)
                results.append((filename, text))
            if len(results) == top_k:
                break
        return results

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
