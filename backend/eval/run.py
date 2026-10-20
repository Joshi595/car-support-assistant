"""Evaluation against eval/golden.jsonl.

    uv run python eval/run.py retrieval   # Hit@k / MRR per retrieval setup, off-topic gate analysis
    uv run python eval/run.py answers     # full pipeline: routing, facts, citations, latency
    uv run python eval/run.py answers --judge groq:qwen/qwen3.8-27b   # + LLM judge verdicts
    uv run python eval/run.py retrieval --min-hit4 0.9 --min-mrr 0.78 # fail (exit 1) below thresholds

Needs the indexed database and Ollama. Reports go to eval/results/.
"""

import argparse
import json
import os
import re
import statistics
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

os.environ.setdefault("CS_ANSWER_CACHE", "false")  # every run measures the pipeline, not the cache

from car_support.config import get_settings, relevance_threshold
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


def retrieval_report(setups: dict[str, Setup]) -> tuple[str, dict[str, dict[str, float]]]:
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
    scores: dict[str, dict[str, float]] = {}
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
            scores[name] = {"hit1": sum(hit1) / len(hit1), "hit4": sum(hit4) / len(hit4), "mrr": mrr}
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
    threshold = relevance_threshold(settings)
    refused = sum(s < threshold for s in negative.values())
    listed = ", ".join(f"{i} {s:.2f}" for i, s in sorted(negative.items(), key=lambda x: x[1]))
    lines += ["", "Category columns show Hit@1. Not at rank 1 (rank in brackets, None = not in top 10):", ""]
    lines += [f"- **{n}**: {', '.join(m) or 'none'}" for n, m in misses.items()]
    lines += [
        "",
        f"### Off-topic gate (`{settings.retrieval_mode}`, threshold {threshold})",
        "",
        f"- Answerable questions: top similarity min {min(positive):.3f}, "
        f"median {statistics.median(positive):.3f}; wrongly refused: {sum(s < threshold for s in positive)}",
        f"- Out-of-scope questions refused by the gate: {refused} of {len(negative)} ({listed}). "
        "The rest must be refused by the grounded answer step.",
    ]
    return "\n".join(lines) + "\n", scores


def setup(mode: Mode, keyword_weight: float = 0.0, k: int = 10) -> Setup:
    def run(session: Any, case: dict[str, Any], vector: list[float]) -> list[Passage]:
        return search(session, case["question"], vector, filters_for(case), k, mode, 30, keyword_weight)

    return run


# ── End-to-end answers ─────────────────────────────────────────────────────────

# Which pipeline outcomes satisfy each expected route of the golden set.
ROUTE_OUTCOMES = {
    "kb": {"answer"},
    "refuse": {"refuse", "off_topic", "blocked"},
    "recall": {"recall"},
    "charger": {"chargers", "unavailable"},  # "unavailable" when no Open Charge Map key is configured
    "handoff": {"handoff"},
}


_SPACES = str.maketrans(
    {"\u202f": " ", "\u00a0": " ", "\u2009": " ", "\u2011": "-", "\u2010": "-", "\u2019": "'"}
)


def normalize(text: str) -> str:
    """Make equivalent spellings comparable: "100.000", "100,000" and "100 000" all become "100000";
    "70 %" becomes "70%"; typographic spaces, hyphens and apostrophes become plain ones."""
    text = text.translate(_SPACES).lower()
    text = re.sub(r"(?<=\d)[ ,.](?=\d{3}\b)", "", text)
    return re.sub(r"(?<=\d) %", "%", text)


def has_fact(answer: str, fact: str) -> bool:
    text = normalize(answer)
    return any(normalize(alt) in text for alt in fact.split("|"))


def grade(case: dict[str, Any], out: dict[str, Any]) -> dict[str, Any]:
    """Deterministic checks; the LLM judge (Phase 9) adds faithfulness and correctness on top."""
    answer = out["answer"]
    routed = out["outcome"] in ROUTE_OUTCOMES[case["route"]]
    facts_ok = routed and all(has_fact(answer, f) for f in case["facts"])
    leaked = [f for f in case.get("forbidden", []) if has_fact(answer, f)]
    cited = [out["passages"][n - 1] for n in out.get("citations", [])]
    cites_relevant = bool(cited) and first_relevant_rank(case, cited) is not None
    return {
        "routed": routed,
        "correct": facts_ok and not leaked,
        "leaked": leaked,
        "cites_relevant": cites_relevant if case["route"] == "kb" else None,
    }


def answers_report(part: int = 1, parts: int = 1, judge_model: str | None = None) -> str:
    from car_support.pipeline.graph import build_graph, new_state

    graph = build_graph()
    rows: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], float]] = []
    # Free cloud tiers cap tokens per day: --part 1/2 and 2/2 split one run across days.
    for case in GOLDEN[part - 1 :: parts]:
        state = new_state(case["question"], case["market"], [tuple(t) for t in case.get("history", [])])
        state["as_of"] = filters_for(case).as_of
        started = time.perf_counter()
        try:
            out = graph.invoke(state)
        except Exception as exc:  # a crash is a failed question, not a failed evaluation
            out = {"answer": f"ERROR: {exc}", "outcome": "error", "passages": [], "citations": []}
        g = grade(case, out)
        if judge_model and case["route"] == "kb" and out["outcome"] == "answer":
            from judge import judge  # eval/judge.py

            try:
                g["verdict"] = judge(
                    judge_model, case["question"], out["answer"], out.get("sources", []), case["facts"]
                )
            except Exception as exc:  # quota or provider error: count as not judged
                g["judge_error"] = str(exc)[:120]
        rows.append((case, out, g, time.perf_counter() - started))

    settings = get_settings()
    latencies = sorted(r[3] for r in rows)
    lines = [
        f"## End to end: {len(rows)} golden questions, {date.today()}",
        "",
        f"Chat model `{settings.chat_model}`, embeddings `{settings.embed_model}`, retrieval "
        f"`{settings.retrieval_mode}`. *Routed*: the pipeline took the expected path (answer, refuse, tool, "
        "handoff). *Correct*: routed, every expected fact present, no forbidden fact (e.g. another market's "
        "number). *Cites relevant*: an answer cites a passage from the expected section.",
        "",
        f"Latency per question: median {statistics.median(latencies):.1f} s, "
        f"p95 {latencies[int(0.95 * (len(latencies) - 1))]:.1f} s.",
        "",
        "| Category | n | Routed | Correct | Cites relevant |"
        + (" Judge: faithful | Judge: correct |" if judge_model else ""),
        "|---|---|---|---|---|" + ("---|---|" if judge_model else ""),
    ]
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case, _, g, _ in rows:
        by_cat[case["category"]].append(g)
    for cat, grades in [*sorted(by_cat.items()), ("**all**", [r[2] for r in rows])]:
        cites = [g["cites_relevant"] for g in grades if g["cites_relevant"] is not None]
        verdicts = [g["verdict"] for g in grades if "verdict" in g]
        judged = (
            f" {pct([v.faithful for v in verdicts])} | {pct([v.correct for v in verdicts])} |"
            if judge_model
            else ""
        )
        lines.append(
            f"| {cat} | {len(grades)} | {pct([g['routed'] for g in grades])} | "
            f"{pct([g['correct'] for g in grades])} | {pct(cites)} |" + judged
        )
    if judge_model:
        judged_rows = [(c, g) for c, _, g, _ in rows if "verdict" in g]
        errors = sum("judge_error" in g for _, _, g, _ in rows)
        lines += [
            "",
            f"Judge `{judge_model}` graded {len(judged_rows)} answered knowledge-base questions"
            + (f" ({errors} could not be judged: quota or provider errors)." if errors else "."),
            "",
            "### Judge: unfaithful or incorrect",
            "",
        ]
        for case, g in judged_rows:
            v = g["verdict"]
            if not (v.faithful and v.correct):
                flags = ", ".join(
                    n for n, ok in [("unfaithful", v.faithful), ("incorrect", v.correct)] if not ok
                )
                lines.append(f"- **{case['id']}** ({flags}) {case['question']}  \n  → {v.reason}")
    lines += ["", "### Failures (deterministic checks)", ""]
    for case, out, g, _ in rows:
        if not g["correct"]:
            why = (
                "wrong route"
                if not g["routed"]
                else f"leaked {g['leaked']}"
                if g["leaked"]
                else "missing fact"
            )
            answer = out["answer"].replace("\n", " ")[:220]
            lines.append(
                f"- **{case['id']}** ({why}; outcome `{out['outcome']}`, expected `{case['route']}`) "
                f"{case['question']}  \n  → {answer}"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=["retrieval", "answers"])
    parser.add_argument("--part", default="1/1", help="answers only: run every n-th question, e.g. 2/3")
    parser.add_argument("--judge", help="answers only: LLM judge model, e.g. groq:qwen/qwen3.8-27b")
    parser.add_argument("--min-hit4", type=float, help="retrieval only: fail if dense Hit@4 is lower")
    parser.add_argument("--min-mrr", type=float, help="retrieval only: fail if dense MRR@10 is lower")
    args = parser.parse_args()
    suite = args.suite
    part, parts = map(int, args.part.split("/"))
    settings = get_settings()
    if suite == "retrieval":
        report, scores = retrieval_report(
            {
                "dense": setup("dense"),
                "keyword (Postgres full-text)": setup("keyword"),
                "hybrid, keyword weight 0.1": setup("hybrid", 0.1),
                "hybrid, keyword weight 0.5": setup("hybrid", 0.5),
            }
        )
        name = f"retrieval-{settings.embed_model}"
        dense = scores["dense"]
        failed = [
            f"{metric} {dense[key]:.3f} < {minimum}"
            for metric, key, minimum in [("Hit@4", "hit4", args.min_hit4), ("MRR@10", "mrr", args.min_mrr)]
            if minimum is not None and dense[key] < minimum
        ]
    else:
        report = answers_report(part, parts, args.judge)
        failed = []
        name = f"answers-{settings.chat_model}" + (f"-part{part}of{parts}" if parts > 1 else "")
    out = EVAL_DIR / "results" / (name.replace(":", "-").replace("/", "-") + ".md")
    out.parent.mkdir(exist_ok=True)
    out.write_text(report, encoding="utf-8")
    sys.stdout.write(report)
    if failed:
        sys.exit("Retrieval gate failed: " + "; ".join(failed))


if __name__ == "__main__":
    main()
