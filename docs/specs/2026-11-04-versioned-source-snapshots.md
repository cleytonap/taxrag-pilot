# Versioned Source Snapshots For Offline Ingestion

Date: 2026-11-04
Status: Implemented

## Problem

The three approved public source artifacts are currently stored only under ignored `var/`. A fresh
checkout therefore cannot reproduce extraction without fetching mutable upstream URLs, which is
unavailable in the offline task environment.

## Scope

- track the exact original bytes for the three currently approved sources in a dedicated data
  directory
- record each snapshot's relative path and expected SHA-256 in the approved source registry
- allow the existing ingestion command to copy a verified snapshot into local object storage
  without network access
- document the distinction between tracked source snapshots and ignored runtime/derived data

## Assumptions

- the current three approved sources are public, small enough for ordinary Git storage, and useful
  as a fixed learning corpus
- upstream fetching remains available for future refreshes
- generated extracted documents, chunks, embeddings, database files, and evaluation runs remain
  reproducible runtime data rather than Git assets

## Design Choice

Keep immutable source snapshots under `data/source-snapshots/<source-key>/<sha256>/original.*`.
The allow-listed registry records the path and hash. An explicit `--from-snapshot` option reads
those bytes, checks the expected hash, and writes the verified bytes through the same local object
storage and PostgreSQL versioning path as a fetched source. Normal ingestion continues to fetch
the canonical URL.

## Risks

- A committed snapshot can become stale; its retrieval date and applicable period must remain
  visible in the source inventory.
- Tracking future large or restricted sources in Git may be inappropriate; revisit storage when
  the corpus or source terms change.
- A registry path/hash mismatch must fail ingestion rather than silently use different bytes.

## Test And Eval Plan

- verify the checked-in files match their registry SHA-256 values
- exercise snapshot ingestion without making an HTTP request
- verify a missing or altered snapshot is recorded as a failed ingestion
- verify fetched-source ingestion still uses the canonical URL
- verify runtime artifacts remain under ignored `var/`

## Definition Of Done

- a fresh checkout contains all three exact source snapshots
- each source can be ingested into local object storage from its snapshot with no network access
- the original fetch path remains available for updates
- requirements, source inventory, ingestion guidance, and ADR describe the policy consistently
