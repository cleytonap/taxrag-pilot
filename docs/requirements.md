# TaxRAG Requirements

Date: 2026-08-31
Status: Draft v1

## 1. Product Vision

Build a web product that answers questions about individual income tax with reliable, source-grounded responses based on official materials.

The system should help users:

- ask tax questions in plain language
- receive clear answers with citations
- inspect the original source material
- understand uncertainty, scope limits, and recency

This is both a real product and a structured learning project about RAG and full-stack AI product development.

## 2. Primary Goals

### Learning goals

- learn modern RAG system design end to end
- learn how to build an AI product with backend, database, auth, frontend, evals, and deployment
- learn how to work spec-first and document decisions
- learn how to operate an AI system with reliability, monitoring, and iteration loops

### Product goals

- provide trustworthy tax answers for individual taxpayers
- ground every answer in verifiable official sources
- keep the knowledge base current enough for real use
- make the product usable from the web on desktop and mobile

## 3. Core Product Principles

- Official sources first
- Citation before style
- Clear uncertainty over false confidence
- Up-to-date sources matter
- Retrieval quality must be observable and testable
- The UI should help users verify, not just consume

## 4. Likely Users

### Primary user

An individual taxpayer who wants a reliable explanation of an income-tax rule and wants to verify the source.

### Secondary users

- people learning about tax rules
- freelancers or self-employed individuals with recurring tax questions
- accountants or tax preparers doing quick source lookups

## 5. Candidate MVP Scope

The first real MVP should likely support:

- one jurisdiction only
- one audience only: individuals, not companies
- text questions in a web UI
- grounded answers with citations and source links
- a retrieval flow over a curated set of official documents
- basic auth so user sessions and saved history are possible
- admin or internal tooling for re-ingestion and source checks
- an evaluation suite with representative tax questions

## 6. Functional Requirements

### Question answering

- users can submit a natural-language tax question
- the system retrieves relevant official sources
- the answer cites the sources used
- the answer distinguishes between direct legal basis and explanatory guidance
- the answer can refuse or narrow scope when the question is too ambiguous or high risk

### Source verification

- users can open the cited source
- users can inspect the relevant excerpt or section
- the system records which source version supported the answer

### Freshness

- the system can refresh source content on a repeatable schedule
- the system can detect source changes or ingestion failures
- the product can show when the supporting source was last checked

### User and product basics

- users can sign up, sign in, and manage sessions
- users can view prior questions and answers
- admins can inspect ingestion and evaluation status

### Evaluation

- maintain a benchmark set of representative questions
- measure retrieval quality, citation quality, and answer quality
- compare changes before release

## 7. Non-Functional Requirements

- reliability over maximum answer speed
- explicit source traceability
- strong observability for failures and regressions
- safe handling of user data
- architecture that is cheap enough for a learning project
- deployment path that can grow into production

## 8. RAG-Specific Requirements

- support official source ingestion from online locations when possible
- preserve metadata such as source title, URL, publication date, jurisdiction, and effective date
- support chunking and retrieval strategies that keep legal context intact
- support re-ranking or other quality improvements if baseline retrieval is weak
- keep citation mapping from generated answer back to retrieved passages
- separate source ingestion concerns from answer-generation concerns

## 9. Trust and Risk Requirements

- do not present the product as personalized tax or legal advice
- highlight when a rule may depend on user-specific facts
- prefer abstention when the retrieved support is weak
- surface conflicts or ambiguity where possible
- track which answer components are grounded vs. inferred

## 10. Open Product Decisions

These need to be settled before architecture:

1. Exact initial tax topic within IRPF: declaration rules, deductions, or another bounded topic?
2. Canonical source inventory: which initial documents and pages are admitted to the knowledge base?
3. Authentication: required for everyone, or optional for public Q&A at first?
4. Monetization: free learning project first, or design with paid plans in mind?
5. When to add calculators after the informational MVP?

## 11. Recommended First Product Boundary

To maximize learning and reduce risk, start with:

- one country
- one language
- one narrow domain inside individual income tax
- curated official sources
- scheduled ingestion rather than fully live browsing
- answer plus citations, not tax filing automation

Good examples of narrow first domains:

- deductible education expenses
- self-employment income reporting basics
- capital gains basics for individuals
- residency and filing obligations

## 11A. Confirmed V1 Decisions

- jurisdiction: Brazil
- language: Brazilian Portuguese
- tax domain: individual income tax (`IRPF`)
- product posture: informational, not individualized tax or legal advice
- source policy: primary legislation plus official Receita Federal guidance, visibly labeled by authority level
- access: public questions initially; authentication can be introduced with saved history and account features
- freshness: scheduled ingestion and source checks; no open-web browsing in the answer path
- initial scope: a narrow, high-reliability topic before broader IRPF coverage

## 11B. Source Strategy

The knowledge base is a curated source registry, not a bulk download of every tax document.

- Prefer official HTML for legislation and official web pages because it usually retains article, section, and link structure.
- Ingest official PDFs when the authoritative material is published as a PDF, such as the annual `Perguntas e Respostas IRPF` manual.
- Store the original downloaded artifact and the extracted text separately. Generate chunks and embeddings from extracted text; they are replaceable derived data.
- Give each source an authority label: `primary_legislation`, `regulation`, `tax_authority_norm`, or `official_guidance`.
- Record canonical URL, retrieval timestamp, publication/update date, effective date or tax year, content hash, extraction method, and source status.
- Do not start by crawling the whole web or every historical act. Admit a source only when it is relevant to the chosen V1 topic and has a clear official origin.

## 12. Suggested Documentation Structure

- `AGENTS.md`
- `docs/requirements.md`
- `docs/specs/`
- `docs/adrs/`
- `docs/evals/`
- `docs/source-inventory/`

## 13. Suggested Development Phases

1. Requirements and scope definition
2. Source inventory and ingestion prototype
3. Retrieval baseline
4. Answer generation with citations
5. Evaluation harness
6. Web app, auth, and history
7. Observability, deployment, and hardening

## 14. Questions To Resolve Next

1. Which narrow IRPF topic should be the first vertical slice?
2. Which exact primary legislation, Receita pages, and annual guidance apply to that topic?
3. Which tax-year or effective-period rules should V1 support?
4. What citations and source excerpts must appear in the answer UI?
5. What ten representative questions will define the first retrieval evaluation set?
