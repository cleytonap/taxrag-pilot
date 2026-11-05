"""List retrieved chunks that a retrieval eval case does NOT label, for human label review.

Why: a case's `acceptable_anchor_keys` must contain every official chunk that directly supports
the question. If it misses one, a correct retriever is scored as failing. This script pools the
top-k results of several strategies (TREC-style pooling) and prints each unlabelled candidate
with its title and an excerpt. A reviewer reads it and either adds it to the acceptable set or
records why it was rejected in `label_notes`. It never edits the fixture.

Usage (from the repository root; semantic/hybrid need OPENAI_API_KEY and current embeddings):

    uv run python scripts/pool-retrieval-candidates.py --strategies lexical semantic hybrid_rrf
    uv run python scripts/pool-retrieval-candidates.py --case lex-058 --k 10
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from taxrag.database import SessionLocal
from taxrag.retrieval import SUPPORTED_STRATEGIES, search_chunks

DEFAULT_FIXTURE = Path("docs/evals/lexical-retrieval-baseline.jsonl")


def main() -> None:
    """Print unlabelled pooled candidates for each selected case."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--case", action="append", help="Case id to review; repeatable")
    parser.add_argument("--k", type=int, default=5, help="Depth per strategy (default 5)")
    parser.add_argument(
        "--strategies", nargs="+", choices=SUPPORTED_STRATEGIES, default=["lexical"]
    )
    args = parser.parse_args()

    cases = [json.loads(line) for line in args.fixture.read_text().splitlines() if line.strip()]
    if args.case:
        cases = [case for case in cases if case["id"] in set(args.case)]

    with SessionLocal() as session:
        for case in cases:
            acceptable = set(case["acceptable_anchor_keys"])
            print(f"\n{case['id']}: {case['question']}")
            print(f"  acceptable: {', '.join(case['acceptable_anchor_keys'])}")
            pooled: dict[str, tuple[object, list[str]]] = {}
            for strategy in args.strategies:
                matches = search_chunks(session, case["question"], limit=args.k, strategy=strategy)
                ranks = [m.anchor_key for m in matches]
                hits = [f"{a}@{ranks.index(a) + 1}" for a in case["acceptable_anchor_keys"] if a in ranks]
                print(f"  {strategy}: acceptable ranks {', '.join(hits) or 'none in top ' + str(args.k)}")
                for rank, match in enumerate(matches, start=1):
                    if match.anchor_key not in acceptable:
                        pooled.setdefault(match.anchor_key, (match, []))[1].append(f"{strategy}@{rank}")
            for anchor_key, (match, seen) in pooled.items():
                excerpt = " ".join(match.chunk_text.split())[:240]
                print(f"  ? {anchor_key} [{', '.join(seen)}] {match.anchor_title[:90]}")
                print(f"      {excerpt}")


if __name__ == "__main__":
    main()
