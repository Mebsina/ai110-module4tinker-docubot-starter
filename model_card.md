# DocuBot Model Card

This model card is a short reflection on your DocuBot system. Fill it out after you have implemented retrieval and experimented with all three modes:

1. Naive LLM over full docs  
2. Retrieval only  
3. RAG (retrieval plus LLM)

Use clear, honest descriptions. It is fine if your system is imperfect.

---

## 1. System Overview

**What is DocuBot trying to do?**  
Describe the overall goal in 2 to 3 sentences.

> DocuBot is a documentation assistant that answers developer questions about a project by searching through local markdown files. It combines a keyword-based retrieval system with an optional LLM to produce grounded, evidence-based answers. The goal is to reduce hallucinations by making the model answer only from retrieved snippets rather than its own training data.

**What inputs does DocuBot take?**  
For example: user question, docs in folder, environment variables.

> - A natural language question typed by the user at the CLI
> - Markdown documentation files from the docs folder, loaded at startup
> - A GEMINI_API_KEY environment variable, required for modes 1 and 3

**What outputs does DocuBot produce?**

> - Mode 1: A fluent LLM-generated answer that is not grounded in the actual docs
> - Mode 2: Raw retrieved paragraph chunks from the most relevant files
> - Mode 3: A concise LLM-generated answer grounded only in retrieved snippets, with file citations

---

## 2. Retrieval Design

**How does your retrieval system work?**  
Describe your choices for indexing and scoring.

- How do you turn documents into an index?
- How do you score relevance for a query?
- How do you choose top snippets?

> **Chunking:** Each document is split on blank lines into paragraph-sized chunks. Short chunks that are typically standalone section headers are merged into the next chunk so their label stays attached to the content that follows.
>
> **Indexing:** An inverted index maps each lowercase word to the set of filenames containing it. Punctuation is stripped from tokens before indexing.
>
> **Scoring:** For each query, common stopwords like is, the, and what are removed. Each remaining word is stemmed by stripping common suffixes and then checked as a substring against each chunk's text. The score is a count of how many stemmed query words appear in the chunk. Chunks that begin with a top-level document heading are penalized by one point so that section-level content outranks introductory overview paragraphs on ties.
>
> **Selection:** Chunks that score below 2 are discarded as weak matches. The remaining chunks are sorted by score, capped to one chunk per file to ensure diversity across documents, and the top 3 are returned.

**What tradeoffs did you make?**  
For example: speed vs precision, simplicity vs accuracy.

> - **Simplicity over accuracy:** Word counting is fast and requires no dependencies, but it cannot handle synonyms or semantic similarity. Words like created and generated are treated as unrelated even when they mean the same thing.
> - **Per-file cap trades recall for diversity:** Capping to one chunk per file prevents one document from filling all three result slots, but occasionally blocks a second highly relevant chunk from the same file.
> - **Score threshold trades recall for precision:** Queries with only one meaningful word always return no results, even if that word is highly specific to the topic.
> - **Stemming is approximate:** Simple suffix stripping handles regular English word forms but fails on irregular ones.

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**  
Briefly describe how each mode behaves.

- Naive LLM mode: Calls Gemini with the user's question but does not pass any doc content. The model answers entirely from its own training data with no retrieval involved.
- Retrieval only mode: No LLM call at all. Returns the raw retrieved chunks directly to the user.
- RAG mode: Runs retrieval first, then passes only the top retrieved chunks to Gemini along with strict prompt instructions. The model generates a synthesized answer grounded in those snippets.

> RAG mode calls the LLM only after retrieval succeeds. If retrieval returns no results because scores are too low, the system refuses before ever reaching Gemini.

**What instructions do you give the LLM to keep it grounded?**  
Summarize the rules from your prompt. For example: only use snippets, say "I do not know" when needed, cite files.

> The RAG prompt tells Gemini to answer using only the provided snippets and not to invent functions, endpoints, or configuration values. It is instructed to refuse with a specific phrase when the snippets are not sufficient to answer confidently. It is also asked to briefly mention which files the answer relied on.

---

## 4. Experiments and Comparisons

Run the **same set of queries** in all three modes. Fill in the table with short notes.

You can reuse or adapt the queries from `dataset.py`.

| Query | Naive LLM: helpful or harmful? | Retrieval only: helpful or harmful? | RAG: helpful or harmful? | Notes |
|------|---------------------------------|--------------------------------------|---------------------------|-------|
| Where is the auth token generated? | Harmful. Answers from training data and may invent function names. | Helpful. Returns the correct AUTH.md section after fixes. | Helpful. Concise answer citing generate_access_token in auth_utils.py. | Required chunking and scoring fixes to surface the right AUTH.md section. |
| How do I connect to the database? | Possibly harmful. May give generic advice unrelated to this codebase. | Helpful. Surfaces the DATABASE.md config section. | Helpful. Grounded answer specific to this project. | Good example of RAG staying on topic instead of giving generic advice. |
| Which endpoint lists all users? | Harmful. May hallucinate endpoint paths. | Helpful. Returns the API_REFERENCE.md chunk directly. | Helpful. Clean answer with the correct endpoint path. | Retrieval only and RAG are close in quality here. |
| How does a client refresh an access token? | Harmful. Gives generic OAuth advice instead of project-specific steps. | Helpful. Returns the AUTH.md client workflow section. | Helpful. Synthesized answer grounded in the actual docs. | Naive LLM sounds confident but describes standard OAuth, not this app. |

**What patterns did you notice?**  

- When does naive LLM look impressive but untrustworthy?  
- When is retrieval only clearly better?  
- When is RAG clearly better than both?

> Naive LLM looks impressive but untrustworthy when the question is about common concepts like tokens, database connections, or REST endpoints. The answer sounds fluent and correct but describes generic patterns rather than this specific codebase. It may invent plausible-sounding function names or endpoint paths that do not exist.
>
> Retrieval only is clearly better when the user needs exact wording from the docs, such as environment variable names, endpoint paths, or error codes. The raw chunk is accurate because it is copied verbatim from the source.
>
> RAG is clearly better than both when the answer spans multiple files or when the raw chunk needs interpretation. It synthesizes a readable sentence from evidence, cites sources, and refuses when evidence is missing.

---

## 5. Failure Cases and Guardrails

**Describe at least two concrete failure cases you observed.**  
For each one, say:

- What was the question?  
- What did the system do?  
- What should have happened instead?

> **Failure case 1:** The query was "what is token generation". The system returned "I do not know based on the docs I have" in RAG mode. The intro paragraph of AUTH.md was retrieved instead of the Token Generation section because both scored equally and the intro appeared first in the file. Gemini correctly refused since the intro only mentions the topic without explaining it. The system should have surfaced the Token Generation section which contains the actual answer.

> **Failure case 2:** The query was "Where is the auth token generated". Early in development, all three retrieved chunks came from API_REFERENCE.md, pushing AUTH.md out of the results entirely. The answer described the login endpoint but never mentioned the generate_access_token function or auth_utils.py. The system should have included at least one chunk from AUTH.md where the actual generation logic is described.

**When should DocuBot say "I do not know based on the docs I have"?**  
Give at least two specific situations.

> - When no chunk scores high enough, meaning fewer than two meaningful query words matched any document. A question about something completely outside the docs, like a pizza recipe, would fall into this category.
> - When Gemini receives snippets that mention the topic but do not contain enough detail to answer the specific question. An intro paragraph that says "this document covers token generation" without actually explaining it is a good example.

**What guardrails did you implement?**  
Examples: refusal rules, thresholds, limits on snippets, safe defaults.

> - **Score threshold:** Retrieval refuses to return results unless at least two meaningful query words match a chunk. This prevents single-word coincidental matches from producing false confidence.
> - **Per-file cap:** Only the highest-scoring chunk per file is returned, preventing one document from filling all three result slots.
> - **LLM refusal rule:** The RAG prompt instructs Gemini to refuse with a specific phrase when the snippets are not sufficient, rather than guessing.
> - **Title chunk penalty:** Chunks that begin with a top-level document heading are penalized so section-level content wins ties over overview paragraphs.

---

## 6. Limitations and Future Improvements

**Current limitations**  
List at least three limitations of your DocuBot system.

1. **No semantic understanding:** Word matching cannot handle synonyms or paraphrasing. The words created and generated are treated as unrelated even though they mean the same thing in context.
2. **Whole-chunk retrieval:** The system retrieves entire paragraphs. For long sections, most of the returned text may be irrelevant to the query, which gives the LLM noisy context to work with.
3. **No multi-turn memory:** Each query is independent. DocuBot cannot answer follow-up questions because it has no memory of the previous exchange.

**Future improvements**  
List two or three changes that would most improve reliability or usefulness.

1. **Embedding-based retrieval:** Replace keyword scoring with vector similarity. This handles synonyms, paraphrasing, and semantic questions that keyword matching misses entirely.
2. **Sentence-level chunking:** Split on sentences rather than paragraphs so retrieved snippets are tighter and more precisely targeted to the query.
3. **Re-ranking:** After initial retrieval, run a second scoring pass that checks how well each chunk actually answers the question, not just how many words overlap.

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**  
Think about wrong answers, missing information, or over trusting the LLM.

> If a developer trusts DocuBot's answer without verifying it, incorrect information about authentication could lead to security misconfigurations. Wrong environment variable names, wrong token lifetime values, or wrong endpoint paths could all be returned confidently, especially in naive LLM mode where the model describes a generic authentication scheme rather than this specific one. A developer who does not realize the answer is ungrounded could implement it incorrectly and introduce a vulnerability.

**What instructions would you give real developers who want to use DocuBot safely?**  
Write 2 to 4 short bullet points.

- Always verify answers against the actual source files before acting on them, especially for anything security-related.
- Use RAG mode rather than naive LLM mode. Naive mode is not grounded in your actual docs.
- Treat a confident-sounding answer as a starting point for investigation, not a final source of truth.
- Keep the docs folder up to date. DocuBot can only know what is in the files it was given at startup.

---
