# ADR 003: Track Small Approved Source Snapshots

Date: 2026-11-04
Status: Accepted

## Context

TaxRAG preserves official source bytes by hash, but the current local object-storage directory is
ignored by Git. A fresh checkout therefore cannot reproduce the first ingestion experiment when
network access is unavailable or an upstream source has changed.

## Decision

Track the exact bytes of the three currently approved, public IRPF source snapshots under
`data/source-snapshots/`. Keep local object storage under `var/` as the runtime copy used by the
existing extraction pipeline. The registry records the snapshot path and expected SHA-256; offline
ingestion verifies the hash before copying bytes into runtime storage.

Keep databases, extracted text, chunks, embeddings, and evaluation run artifacts out of Git. These
are generated data and can be recreated from the tracked originals and versioned code/configuration.

## Alternatives Considered

- **Fetch only from the canonical URL:** avoids storing source bytes in Git, but cannot reproduce
  exact historical input offline and depends on upstream availability and immutability.
- **Track all of `var/`:** makes the checkout large and mixes source snapshots with generated
  runtime state. Not chosen.
- **Use object storage only:** appropriate for a larger deployed corpus, but adds infrastructure
  before this small learning corpus needs it.

## Consequences

- The initial corpus can be processed offline from a clean checkout.
- New source versions are added as separate hash-addressed snapshots rather than overwriting old
  inputs.
- The source inventory must distinguish the tracked original snapshot from the local object-store
  copy and document retrieval/applicability metadata.
- Revisit this decision before adding large or restricted source collections.
