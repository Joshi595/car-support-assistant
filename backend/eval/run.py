"""Evaluation against eval/golden.jsonl.

    uv run python eval/run.py retrieval      # Hit@k / MRR per retrieval setup, relevance-gate analysis

Needs the indexed database and Ollama. Writes eval/results/retrieval.md.
"""

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from car_support.config import get_settings
from car_support.db.session import get_session
from car_support.llm import embed_queries
from car_support.retrieval import Filters, Passage, retrieve
from car_support.retrieval.search import Mode, search

EVAL_DIR = Path(__file__).resolve().parent
GOLDEN = [json.loads(line) for line in (EVAL_DIR / "golden.jsonl").open(encoding="utf-8")]


def filters_for(case: dict[str, Any]) -> Filters:
    as_of = date.fromisoformat(case["as_of"]) if case.get("as_of") else date.today()
    return Filters(market=case["market"], as_of=as_of)


def first_relevant_rank(case: dict[str, Any], passages: list[Passage]) -> int | None:
    """1-based rank of the first passage matching any `doc#section` reference, None if absent."""
    for rank, p in enumerate(passages, 1):
        path = " › ".join(p.heading_path).lower()
        for ref in case["relevant"]:
            doc_id, _, section = ref.partition("#")
            if p.doc_id == doc_id and section.lower() in path:
                return rank
    return None


def pct(values: list[bool]) -> str:
    return f"{100 * sum(values) / len(values):.0f}%" if values else "–"


Setup = Callable[[Any, dict[str, Any], list[float]], list[Passage]]


def retrieval_report(setups: dict[str, Setup]) -> str:
    # Follow-ups need the condense step (Phase 4); they are evaluated end to end, not here.
    cases = [c for c in GOLDEN if c["route"] == "kb" and c["category"] != "followup"]
    negatives = [c for c in GOLDEN if c["category"] == "out_of_scope"]
    questions = cases + negatives
    vectors = dict(
        zip([c["id"] for c in questions], embed_queries([c["question"] for c in questions]), strict=True)
    )
    settings = get_settings()
    instruction = "with" if settings.embed_query_instruction else "without"
    lines = [
        f"## Retrieval: {len(cases)} answerable questions (follow-ups excluded), {date.today()}",
        "",
        f"Embeddings `{settings.embed_model}`, {instruction} query instruction. "
        "Hit@k = a relevant section is among the top k; "
        "MRR@10 = mean of 1/rank of the first relevant section. "
        "Query embedding time is not included in ms/query.",
        "",
    ]
    categories = sorted({c["category"] for c in cases})
    lines.append("| Setup | Hit@1 | Hit@4 | MRR@10 | " + " | ".join(categories) + " | ms/query |")
    lines.append("|" + "---|" * (len(categories) + 5))
    misses: dict[str, list[str]] = {}
    with get_session() as session:
        for name, fn in setups.items():
            ranks: list[int | None] = []
            by_cat: dict[str, list[bool]] = defaultdict(list)
            started = time.perf_counter()
            for case in cases:
                rank = first_relevant_rank(case, fn(session, case, vectors[case["id"]]))
                ranks.append(rank)
                by_cat[case["category"]].append(rank == 1)
            ms = 1000 * (time.perf_counter() - started) / len(cases)
            hit1, hit4 = [r == 1 for r in ranks], [r is not None and r <= 4 for r in ranks]
            mrr = statistics.mean(1 / r if r else 0 for r in ranks)
            lines.append(
                f"| {name} | {pct(hit1)} | {pct(hit4)} | {mrr:.3f} | "
                + " | ".join(pct(by_cat[c]) for c in categories)
                + f" | {ms:.0f} |"
            )
            misses[name] = [f"{c['id']} ({r})" for c, r in zip(cases, ranks, strict=True) if r != 1]

        # Off-topic gate on the default setup: highest cosine similarity among the retrieved passages.
        def top_similarity(case: dict[str, Any]) -> float:
            passages = retrieve(
                session, case["question"], filters_for(case), query_vector=vectors[case["id"]]
            )
            return max((p.similarity for p in passages), default=0.0)

        positive = [top_similarity(c) for c in cases]
        negative = {c["id"]: top_similarity(c) for c in negatives}
    threshold = settings.relevance_threshold
    refused = sum(s < threshold for s in negative.values())
    scores = ", ".join(f"{i} {s:.2f}" for i, s in sorted(negative.items(), key=lambda x: x[1]))
    lines += ["", "Category columns show Hit@1. Not at rank 1 (rank in brackets, None = not in top 10):", ""]
    lines += [f"- **{n}**: {', '.join(m) or 'none'}" for n, m in misses.items()]
    lines += [
        "",
        f"### Off-topic gate (`{settings.retrieval_mode}`, threshold {threshold})",
        "",
        f"- Answerable questions: top similarity min {min(positive):.3f}, "
        f"median {statistics.median(positive):.3f}; wrongly refused: {sum(s < threshold for s in positive)}",
        f"- Out-of-scope questions refused by the gate: {refused} of {len(negative)} ({scores}). "
        "The rest must be refused by the grounded answer step.",
    ]
    return "\n".join(lines) + "\n"


def setup(mode: Mode, keyword_weight: float = 0.0, k: int = 10) -> Setup:
    def run(session: Any, case: dict[str, Any], vector: list[float]) -> list[Passage]:
        return search(session, case["question"], vector, filters_for(case), k, mode, 30, keyword_weight)

    return run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=["retrieval"])
    parser.parse_args()
    report = retrieval_report(
        {
            "dense": setup("dense"),
            "keyword (Postgres full-text)": setup("keyword"),
            "hybrid, keyword weight 0.1": setup("hybrid", 0.1),
            "hybrid, keyword weight 0.5": setup("hybrid", 0.5),
        }
    )
    model = get_settings().embed_model.replace(":", "-")
    out = EVAL_DIR / "results" / f"retrieval-{model}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(report, encoding="utf-8")
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
