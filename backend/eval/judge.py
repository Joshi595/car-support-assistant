"""LLM-as-judge: grade an answer against the passages it cites and the facts the golden set expects.

Keyword checks (run.py) are cheap and deterministic but brittle: "three years" is not "3 years", and they
cannot tell an answer that is correct but unsupported by its sources. The judge reads the question, the
answer and the cited passages and returns two verdicts with a reason. Use a strong model from a different
family than the pipeline's, so it does not share the pipeline's blind spots.
"""

from typing import Any

from pydantic import BaseModel, Field

from car_support.llm import _provider_model

JUDGE_PROMPT = """You grade answers from a car maker's customer-service assistant.

Question: {question}
Expected facts (the answer must contain these, in any wording or unit format): {facts}

Passages the answer cites:
{passages}

Answer:
{answer}

Grade two things:
- faithful: true if EVERY factual claim in the answer is supported by the cited passages above. A claim that
  is true in the real world but not stated in the passages makes the answer unfaithful.
- correct: true if the answer actually answers the question and states each expected fact (wording and
  number formats may differ: "three years" equals "3 years", "100 000 km" equals "100,000 km").
Give a one-sentence reason that names the problem if either is false."""


class Verdict(BaseModel):
    faithful: bool = Field(description="Every claim is supported by the cited passages")
    correct: bool = Field(description="Answers the question and contains every expected fact")
    reason: str = Field(description="One sentence; names the problem if either verdict is false")


def judge(model: str, question: str, answer: str, sources: list[dict[str, Any]], facts: list[str]) -> Verdict:
    passages = (
        "\n\n".join(f"[{s['n']}] {s['title']}, {s['section']}\n{s['excerpt']}" for s in sources) or "(none)"
    )
    prompt = JUDGE_PROMPT.format(
        question=question,
        facts="; ".join(f.replace("|", " or ") for f in facts) or "(none given; judge whether it answers)",
        passages=passages,
        answer=answer,
    )
    grader = _provider_model(model).with_structured_output(Verdict).with_retry(stop_after_attempt=3)
    verdict = grader.invoke([("user", prompt)])
    if not isinstance(verdict, Verdict):  # with_structured_output may return a dict for some providers
        verdict = Verdict.model_validate(verdict)
    return verdict
