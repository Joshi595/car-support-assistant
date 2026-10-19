"""HTTP API against a real Postgres, with a fake pipeline (no models needed)."""

import json
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from car_support.config import get_settings


class FakeGraph:
    """Streams like LangGraph with stream_mode=["messages", "values"]."""

    def __init__(self, final: dict[str, Any]) -> None:
        self.final, self.calls = final, []  # type: ignore[var-annotated]

    def stream(self, state: dict[str, Any], stream_mode: list[str]) -> Iterator[tuple[str, Any]]:
        self.calls.append(state)
        for word in self.final["answer"].split(" "):
            yield "messages", (AIMessageChunk(content=word + " "), {"langgraph_node": "generate"})
        yield "messages", (AIMessageChunk(content="ignored"), {"langgraph_node": "understand"})
        yield "values", self.final


ANSWER: dict[str, Any] = {
    "answer": "The battery warranty is 8 years [1].",
    "outcome": "answer",
    "sources": [{"n": 1, "doc_id": "brand/uk/en/warranty", "title": "Warranty", "section": "Battery"}],
}


@pytest.fixture
def client(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("CS_AGENT_JWT_SECRET", "test-secret-with-at-least-32-bytes!!")
    monkeypatch.setenv("CS_CHAT_RATE_LIMIT", "1000/minute")
    get_settings.cache_clear()
    from car_support.api.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def _chat(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, final: dict[str, Any], **body: Any
) -> dict[str, Any]:
    fake = FakeGraph(final)
    monkeypatch.setattr("car_support.api.chat.build_graph", lambda: fake)
    resp = client.post("/v1/chat", json={"market": "uk", **body})
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/event-stream")
    events = [
        (
            block.split("\n")[0].removeprefix("event: "),
            json.loads(block.split("\n")[1].removeprefix("data: ")),
        )
        for block in resp.text.strip().split("\n\n")
    ]
    return {"events": events, "fake": fake, "request_id": resp.headers["X-Request-ID"]}


def _agent_headers() -> dict[str, str]:
    from car_support.api.auth import issue_token

    return {"Authorization": f"Bearer {issue_token('agent@example.com')}"}


@pytest.mark.integration
def test_chat_streams_tokens_then_the_validated_answer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _chat(client, monkeypatch, ANSWER, message="My email is jane@example.com. Battery warranty?")
    kinds = [kind for kind, _ in run["events"]]
    assert (
        kinds[0] == "meta"
        and kinds[-1] == "done"
        and kinds.count("token") == len(ANSWER["answer"].split(" "))
    )  # understand tokens skipped
    done = run["events"][-1][1]
    assert done["answer"] == ANSWER["answer"] and done["sources"][0]["n"] == 1 and not done["offer_handoff"]

    conversation = client.get(f"/v1/conversations/{run['events'][0][1]['conversation_id']}").json()
    assert [m["role"] for m in conversation["messages"]] == ["user", "assistant"]
    assert (
        conversation["messages"][0]["content"] == "My email is [email]. Battery warranty?"
    )  # stored redacted
    assert run["fake"].calls[0]["question"].startswith("My email is jane@")  # the pipeline sees the original


@pytest.mark.integration
def test_follow_up_messages_carry_the_history(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _chat(client, monkeypatch, ANSWER, message="Battery warranty?")
    cid = first["events"][0][1]["conversation_id"]
    second = _chat(client, monkeypatch, ANSWER, message="And the paint?", conversation_id=cid)
    assert second["fake"].calls[0]["history"] == [
        ("user", "Battery warranty?"),
        ("assistant", ANSWER["answer"]),
    ]


@pytest.mark.integration
def test_handoff_outcome_opens_a_ticket_agents_can_see(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _chat(
        client, monkeypatch, {"answer": "Connecting you.", "outcome": "handoff"}, message="A human please"
    )
    cid = run["events"][0][1]["conversation_id"]

    assert client.get("/v1/admin/tickets").status_code == 401
    tickets = client.get("/v1/admin/tickets", headers=_agent_headers()).json()
    ticket = next(t for t in tickets if t["conversation_id"] == cid)
    assert ticket["reason"] == "customer_request" and ticket["last_customer_message"] == "A human please"

    updated = client.patch(
        f"/v1/admin/tickets/{ticket['id']}", json={"status": "in_progress"}, headers=_agent_headers()
    ).json()
    assert updated == {"id": ticket["id"], "status": "in_progress", "assigned_to": "agent@example.com"}
    detail = client.get(f"/v1/admin/tickets/{ticket['id']}", headers=_agent_headers()).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]


@pytest.mark.integration
def test_refusal_offers_a_handoff_that_the_customer_can_accept(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _chat(
        client, monkeypatch, {"answer": "Not in our docs.", "outcome": "refuse"}, message="Drag coefficient?"
    )
    assert run["events"][-1][1]["offer_handoff"]
    cid = run["events"][0][1]["conversation_id"]
    assert client.post("/v1/handoff", json={"conversation_id": cid, "reason": "refusal"}).status_code == 201
    assert client.get(f"/v1/conversations/{cid}").json()["status"] == "handed_off"


@pytest.mark.integration
def test_feedback_belongs_to_its_conversation_and_can_be_changed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _chat(client, monkeypatch, ANSWER, message="Battery warranty?")
    cid, mid = run["events"][0][1]["conversation_id"], run["events"][-1][1]["message_id"]

    other = {"conversation_id": str(uuid.uuid4()), "message_id": mid, "rating": 1}
    assert client.post("/v1/feedback", json=other).status_code == 404  # someone else's answer
    assert (
        client.post("/v1/feedback", json={"conversation_id": cid, "message_id": mid, "rating": 1}).status_code
        == 204
    )
    body = {"conversation_id": cid, "message_id": mid, "rating": -1, "comment": "wrong"}
    assert client.post("/v1/feedback", json=body).status_code == 204

    rated = client.get("/v1/admin/feedback?rating=-1", headers=_agent_headers()).json()
    entry = next(f for f in rated if f["message_id"] == mid)
    assert entry["question"] == "Battery warranty?" and entry["comment"] == "wrong"


@pytest.mark.integration
def test_requests_are_validated_and_tagged(client: TestClient) -> None:
    assert client.post("/v1/chat", json={"market": "fr", "message": "hi"}).status_code == 422
    assert client.post("/v1/chat", json={"market": "uk", "message": ""}).status_code == 422
    resp = client.get("/healthz", headers={"X-Request-ID": "abc"})
    assert resp.json() == {"status": "ok"} and resp.headers["X-Request-ID"] == "abc"
    bad = {"Authorization": "Bearer not-a-token"}
    assert client.get("/v1/admin/tickets", headers=bad).status_code == 401


@pytest.mark.integration
def test_cache_key_ignores_case_and_punctuation_but_not_market_or_date(database_url: str) -> None:
    from datetime import date

    from car_support.db.session import get_session
    from car_support.pipeline.cache import cache_key

    with get_session() as s:
        base = cache_key("How long is the paint warranty?", "uk", "en", date(2026, 10, 20), s)
        assert cache_key("how long is the PAINT warranty", "uk", "en", date(2026, 10, 20), s) == base
        assert cache_key("How long is the paint warranty?", "us", "en", date(2026, 10, 20), s) != base
        assert cache_key("How long is the paint warranty?", "uk", "en", date(2026, 10, 21), s) != base
