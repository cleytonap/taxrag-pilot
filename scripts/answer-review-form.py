"""Build a human-review form from an answer run (generation or end-to-end suite).

The form shows each case's question, the answer exactly as the user sees it (claims plus
caveats and clarification question), its citations and outcome, and the review criteria as
checkboxes. Grade the user-visible text only.

    uv run python scripts/answer-review-form.py v1_answer_semantic_openai.json
    uv run python scripts/answer-review-form.py <run>.json --output docs/evals/baselines/x.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from taxrag.eval_manager import BASELINES_DIRECTORY, get_artifact


def main() -> None:
    """Write the Markdown review form for one saved run or baseline artifact."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("artifact_name")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    run = json.loads(get_artifact(args.artifact_name)["content"])
    if run["suite_id"] not in {"answer", "generation"}:
        raise SystemExit("Review forms are for answer suites (generation or end-to-end).")
    cases = run["cases"]
    abstain = [case for case in cases if case["expected_abstain"]]
    lines = [
        f"# Human Review: {args.artifact_name}",
        "",
        (f"Suite `{run['suite_id']}` · strategy `{run['strategy']}` · provider `{run['provider']}` · "
        f"answer model `{run.get('answer_model')}` · fixture `{run['fixture_sha256'][:12]}`"),
        "",
        ("Grade only the user-visible answer below (claims, caveats and clarification question "
        "are all shown to the user). A case passes when every criterion is ticked and the "
        "automated check passed. Tick a box by replacing `[ ]` with `[x]`."),
        "",
        "Reviewer: ____  Date: ____",
        "",
        "| Summary | Value |",
        "| --- | --- |",
        f"| Cases with all criteria met | __ / {len(cases)} |",
        f"| Expected abstentions handled correctly | __ / {len(abstain)} |",
        "| Answers with a legal error (any) | __ |",
        f"| Automated structural pass | {run['summary']['passed']} / {len(cases)} |",
        f"| Unsafe answers (answered when abstention expected) | {run['summary'].get('unsafe_answers', '?')} |",
        "",
    ]
    for case in cases:
        answer = case["answer"]
        expected = "abstain" if case["expected_abstain"] else "answer"
        tag = f" · edge: {case['edge_case']}" if case.get("edge_case") else ""
        automated = "pass" if case["passed"] else "FAIL"
        lines += [
            f"## {case['case_id']} · expected {expected}{tag} · automated {automated}",
            "",
            f"> {case['question']}",
            "",
            (f"Outcome `{case['actual_outcome']}` · cited "
            f"{', '.join(case['cited_anchor_keys']) or '—'} · acceptable "
            f"{', '.join(case['acceptable_anchor_keys']) or '— (abstain)'}"),
            "",
        ]
        if case.get("context_anchor_keys"):
            lines += [f"Fixed context: {', '.join(case['context_anchor_keys'])}", ""]
        if case.get("validation_error"):
            lines += [f"Validation rejected the draft: {case['validation_error']}", ""]
        shown = (answer.get("display_text") or "(no text)").replace("\n", "\n> ")
        lines += ["**Answer shown to the user:**", "", f"> {shown}", ""]
        lines += [f"- [ ] {criterion}" for criterion in case["human_review_criteria"]]
        lines += ["- Verdict: PASS / FAIL", "- Notes:", ""]

    output = args.output or BASELINES_DIRECTORY / f"{Path(args.artifact_name).stem}-review.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
