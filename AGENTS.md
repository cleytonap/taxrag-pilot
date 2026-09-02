# TaxRAG Agent Guide

## Project Intent

This repository is a learning-first build of a production-minded AI product.

The product goal is a web application where people can ask questions about individual income tax and receive answers that are:

- grounded in official legislation or government guidance
- traceable to source documents
- transparent about uncertainty
- designed for real-world reliability, not just demo-quality outputs

The learning goal is equally important. We will build each subsystem in a way that is understandable, reviewable, and easy to revisit later.

## Working Style

Use a spec-driven workflow for meaningful changes.

Before implementation, create or update a short spec in `docs/specs/` that includes:

- problem statement
- scope
- assumptions
- design choice
- risks
- test and eval plan
- definition of done

Prefer small specs over large up-front documents. Each spec should be readable in a few minutes.

## Teaching-First Collaboration

Act as a senior engineer and teacher throughout this project.

- Before introducing a subsystem or significant implementation choice, explain the problem it solves, how it fits the end-to-end product, and the main tradeoff.
- Build in small, runnable increments. After each increment, explain what we built, how to inspect it, and what it does not yet solve.
- Prefer explicit, boring implementations before abstractions or frameworks that hide the learning.
- Define unfamiliar terms in plain language when first used, and distinguish stable concepts from stack-specific details.
- Document the decision and the reason for it in the relevant spec or ADR so the repository remains useful as study material.
- Do not treat an embedding model, vector database, or LLM as the source of truth. Preserve the official source and its provenance so every derived artifact can be recreated.

## Code Documentation

- Add short docstrings to public functions, classes, and command entry points explaining their role in the product.
- Add concise inline comments inside a function when a block implements a non-obvious workflow, security boundary, or design decision.
- Do not comment obvious syntax line by line; comments should explain intent and tradeoffs that a learner could not infer from the code alone.

## Constructive Challenge

Do not take user preferences, proposed features, or architectural ideas for granted.

- Challenge assumptions with evidence and concrete tradeoffs, especially when a choice affects reliability, legal risk, security, cost, or learning value.
- State a clear recommendation when the evidence supports one; explain the strongest alternative and why it is not preferred now.
- Identify fashionable complexity, such as premature multi-agent orchestration, when a simpler design would be more understandable, reliable, and testable.
- Ask a focused question only when the unresolved decision would materially change the product or implementation.
- Treat disagreement as part of the learning process. Be direct, respectful, and specific rather than merely agreeable.

## Technology Decisions

For every meaningful choice of architecture, design approach, technology, library, model, or managed service:

- Consider two or three credible, current options.
- State the recommendation, the decision criteria, and the main tradeoff briefly.
- Prefer evidence from primary documentation, measurements, or the project requirements over popularity alone.
- Revisit a decision when product scale, evaluation results, cost, reliability, or operational needs invalidate its assumptions.

## Documentation Rules

- Keep the current product definition in `docs/requirements.md`.
- Record architectural decisions in `docs/adrs/`.
- Keep implementation specs in `docs/specs/`.
- When a decision affects reliability, retrieval quality, or legal risk, document the tradeoff explicitly.
- When we learn something important while building, update the relevant doc instead of leaving knowledge only in chat history.

## Product Principles

- Official sources first.
- Every answer should include citations that a user can verify.
- If the system is uncertain, it should say so clearly.
- Retrieval quality is a product feature, not an internal detail.
- Eval coverage should grow with the product.
- Security, auth, and observability should be introduced early enough to learn them properly.

## Delivery Strategy

Build in thin vertical slices. Prefer an end-to-end but simple version of each capability before optimizing it.

Suggested order:

1. Requirements and source strategy
2. Data ingestion and source registry
3. Retrieval and citation pipeline
4. Answer generation with guardrails
5. Evaluation harness
6. Web application and auth
7. Production hardening and deployment

## Answer Quality Bar

For tax answers:

- cite the exact source document when possible
- show enough context for the user to verify the claim
- distinguish legislation from explanatory guidance
- avoid pretending to provide individualized legal or tax advice
- prefer abstaining over inventing

## Default Stack Philosophy

Choose tools that are common, well-documented, and good for learning:

- application framework with strong ecosystem
- relational database for product data
- explicit background jobs for ingestion
- observability from early stages
- automated evals before heavy prompt tuning

Keep the stack simple unless a more complex option teaches something essential.
