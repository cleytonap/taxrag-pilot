# Project Foundation Spec

Date: 2026-08-31
Status: Draft

## Problem

We need a clean foundation for a learning-first RAG project that can mature into a production web product for grounded individual income-tax Q&A.

## Scope

This spec covers:

- project intent
- documentation structure
- initial product requirements
- the first set of open questions that should guide architecture

This spec does not yet choose the technical stack or source-ingestion strategy.

## Assumptions

- the system should rely on official government sources whenever possible
- correctness and traceability matter more than speed
- the product should eventually be accessible on the web
- the project should teach end-to-end AI product development, not only RAG

## Decisions

- use a spec-driven workflow from the beginning
- maintain a living requirements document
- record architectural decisions separately from implementation specs
- keep the first product boundary narrow before expanding coverage

## Risks

- trying to cover too many tax topics too early
- confusing learning goals with production goals and overbuilding
- using live web retrieval too early and making reliability harder
- underinvesting in evals and source quality

## Test And Eval Plan

For this phase, success means the project has:

- a documented product vision
- a documented development workflow
- a clear list of open product decisions

## Definition Of Done

- `AGENTS.md` exists and captures how we want to work
- `docs/requirements.md` exists with draft product requirements
- the next conversation can focus on architecture using these docs as input
