# Eval Workshop Workflow

Date: 2026-11-04
Status: Implementing

## Problem

The local workshop can edit fixtures and run one diagnostic answer, but cannot run an entire
evaluation suite from the UI. Diagnostic questions must be copied into JSONL by hand, run results
are not saved by the UI, and retrieved chunks link only to the document root rather than their
page or section.

## Scope

- Run the selected retrieval or cited-answer suite using an explicit strategy and provider.
- Persist one JSON artifact per run, including fixture hash, configuration, aggregate metrics,
  per-case outcomes, and evidence links; show the artifact in the archive.
- Turn a diagnostic question into a fixture case, letting the developer select retrieved anchors
  and set abstention/review criteria before validating and saving it.
- Link PDF evidence to its source page and HTML evidence to a browser text fragment when a stable
  DOM section ID is unavailable; always display the document and section label.
- Keep the existing local-only, closed-suite, explicit paid-provider boundary.
- Bound UI API requests with a timeout and offer a retry action when initial workspace loading fails.

## Assumptions

- Retrieval scores should be comparable only when suite, strategy, and corpus are shown together.
- The deterministic answer provider is useful for structural smoke checks, not human answer quality.
- OpenAI answer or embedding requests may incur cost and must require explicit confirmation in the UI.
- Government HTML pages do not expose durable DOM IDs for every extracted heading, so a text fragment
  is a best-effort section jump; the section title remains visible as a fallback.

## Design Choice

Add a suite-run endpoint to the existing local FastAPI API and persist immutable JSON run artifacts
under `var/eval-runs/`. Keep suite fixtures as Git-tracked JSONL. The UI offers one selected
strategy per run, visible pass/recall summaries, failed-case inspection, and a Question Lab action
to append a reviewed diagnostic case to the selected fixture.

Alternative: run evaluations in the browser or add a separate job/database subsystem. The API
already owns database access and the current suites are small, so synchronous local execution plus
file artifacts is the simplest inspectable approach. Revisit background jobs if runs become slow.

## Risks

- Large answer runs can take time; show progress state and keep the first implementation synchronous.
- Text-fragment linking depends on browser support and source text stability; preserve the canonical
  document link and exact section label even when the jump cannot resolve.
- Fixture writes modify tracked files; validate before writing and report the path for Git review.
- This unauthenticated workshop must remain bound to localhost.
- A stale browser tab can keep old client code until it is refreshed; errors should still become
  visible instead of leaving the initial loading label indefinitely.

## Test And Eval Plan

- Unit-test run artifact serialization, aggregate metrics, and anchor-aware source URLs.
- API-test suite execution, validation failures, and persisted artifact listing.
- UI typecheck/lint/build and manual smoke review of run, inspect, add-case, and evidence links.
- Run the lexical retrieval suite and deterministic answer suite through the same API path used by
  the UI; compare displayed metrics with CLI results.

## Definition Of Done

- A developer can run either fixture suite from the workshop and inspect the saved per-case result.
- A diagnostic query can be selected as an acceptable case, validated, and saved into a chosen suite.
- Every retrieved chunk exposes a document link plus a page/section-specific locator where possible.
- Run artifacts include fixture hash, strategy/provider, timestamp, aggregate outcome, and case data.
- Initial workspace loading fails visibly after the request timeout and can be retried from the UI.
