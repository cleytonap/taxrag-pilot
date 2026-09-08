# IN RFB 2.312/2026: DOU Ingestion And Legal Anchors

Date: 2026-09-04
Status: Implemented

## Problem

The IRPF 2026 filing-obligation rule needs a normative source with article-level citations. The
Receita Normas URL is a JavaScript application shell and cannot safely be treated as the text of
the act. An official DOU publication URL was identified, but the development environment is
currently disconnected by that host before it receives an HTTP response.

## Scope

- record the official DOU publication as the canonical public URL for IN RFB 2.312/2026
- prove one reproducible, automated method to obtain the raw official document
- preserve the downloaded raw artifact and its content hash
- extract `Art. 2`, its incisos, and its paragraphs as distinct legal citation anchors
- add a fixture that represents the obtained source and tests legal-structure preservation

## Out Of Scope

- answering tax questions with an LLM or adding embeddings
- ingesting every article of the instruction before an evaluation case requires it
- treating the JavaScript Normas interface as a text source

## Assumptions

- The official DOU publication is a valid representation of the published act.
- A later consolidated version may be needed if the act is amended; raw DOU text remains useful
  as immutable publication evidence.
- The current access failure is environment-specific until reproduced from another network or
  verified with an official alternate delivery mechanism.

## Options Considered

| Option | Strength | Tradeoff | Decision |
| --- | --- | --- | --- |
| Static DOU publication | Official, stable, user-verifiable URL; likely semantic HTML | Must solve automated-host access | Chosen, pending access proof |
| Receita Normas SPA | May expose a consolidated presentation | Browser shell is not the legal text and needs a dedicated adapter | Not chosen now |
| Manually downloaded copy | Can unblock local parser work | Cannot prove the worker can refresh it and adds custody risk | Fixture-only fallback |

## Design Choice

Use the DOU publication as the public canonical URL and retain its raw response unchanged in
object storage. The extraction adapter will make legal structure explicit: an article is a parent
context, while each inciso and paragraph becomes a separately retrievable anchor. A citation must
show at least `Art. 2` and, where applicable, the inciso or paragraph, rather than a generic page
heading.

The source must not be added to `APPROVED_SOURCES` until the worker can retrieve it automatically.
This protects freshness: a source that only works when a developer downloads it by hand is not yet
a production ingestion source.

## Risks

- DOU may block generic HTTP clients or require a different official delivery route.
- HTML structure may change, invalidating a selector-based parser.
- Amendments can make the original DOU text historically correct but no longer current.
- Splitting incisos too aggressively can omit the conditions stated in the article lead-in.

## Test And Eval Plan

- Add a captured, minimal fixture only after successful official retrieval.
- Test that article, inciso, and paragraph labels survive extraction and remain in anchor text.
- Confirm the raw artifact hash, source version, and canonical DOU URL are persisted.
- Add retrieval cases that prefer the normative `Art. 2` anchor over guidance when both support a
  filing-obligation question.

## Definition Of Done

- The worker retrieves the official DOU source reproducibly and validates its declared format.
- The immutable raw artifact is stored and linked to a source version.
- `Art. 2` legal subdivisions produce stable, user-visible citation anchors.
- Tests cover the parser using a captured official fixture and processing is idempotent.

## Implementation Evidence

Validated locally on 2026-09-08:

- The DOU URL returned `200` with `text/html;charset=UTF-8` when the source-specific,
  browser-compatible request headers were supplied. The generic client disconnect was therefore
  an access-policy behavior, not a missing document.
- The worker stored the official raw HTML at
  `raw/irpf-2026-in-rfb-2312/f0a12419b3a23a768ceece8e0413e811fcfc63543457fd145ea13e2f9cefaf58/original.html`.
- Processing created eighteen legal anchors: the `Art. 2` caput, twelve caput incisos, three
  paragraphs, and the two incisos of `§ 1º`. A second processing run returned `unchanged`.
- Fixture tests verify that alíneas remain attached to their parent inciso and that every inciso
  retains the article caput and, for `§ 1º`, its paragraph lead-in.
- A lexical query about the `R$ 35.584,00` threshold retrieved `Art. 2, inciso I` at rank five.
  The normative source is present, but the current lexical ranking does not yet prefer higher
  authority sources; this is intentionally deferred to the next retrieval-evaluation slice.
