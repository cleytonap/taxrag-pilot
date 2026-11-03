# Eval Manager Foundation

Status: Implemented

## Problem Statement

Retrieval and cited-answer fixtures, their configurations, and their local run artifacts are
becoming hard to inspect from terminal output alone. Developers need one local place to inspect
and edit the versioned fixtures, review past output, and ask a diagnostic question.

## Scope

- Provide a local FastAPI API for the retrieval and cited-answer JSONL fixtures.
- Provide a local Next.js dashboard to inspect and edit those fixtures, browse saved artifacts,
  and run a single diagnostic question.
- Return the final answer, citations, retrieved chunks, ranking scores, and rejection diagnostics
  from the diagnostic question endpoint.
- Require an explicit request flag before a diagnostic request can use OpenAI.

## Assumptions

- This is a developer-only tool running on localhost.
- Git-tracked JSONL remains the canonical fixture store; saving through the UI changes the local
  working tree and still requires normal review and commit.
- Existing text and JSON artifacts in `var/eval-runs/` remain read-only history in this slice.

## Design Choice

Use a small in-repository manager rather than adopting an external platform now. The manager
understands TaxRAG's specific fixture contracts and application-controlled citations, while
keeping the workflow visible for learning. It exposes only known fixture paths and artifact file
names; it does not accept arbitrary filesystem paths.

The Next.js app forwards its Eval Workshop requests through a same-origin route to FastAPI. This
keeps the browser away from cross-origin API calls, while the proxy only permits the manager's
known endpoints. The API remains local and diagnostic retrieval still requires the Postgres
service and migrated schema.

## Risks

- The edit API has no authentication and must never be exposed beyond local development.
- A debug query can disclose its question and retrieved chunks to OpenAI when the OpenAI provider
  is selected. The UI requires an explicit billable confirmation, but it cannot replace operator
  judgment about sensitive data.
- Text artifact browsing is useful but is not a replacement for durable, queryable run storage.

## Test And Eval Plan

- Unit-test fixture validation, bounded artifact access, and debug payload serialization.
- API-test the local routes and paid-provider confirmation boundary with fakes.
- Run Python tests and Ruff, then Next.js lint and production build.

## Definition Of Done

- A local user can list and edit both fixture suites, view saved artifacts, and inspect a fake
  diagnostic answer with all retrieval metadata.
- Selecting OpenAI without confirmation is rejected before any provider call.
- The UI clearly marks fixture edits as local working-tree changes and history as read-only.
