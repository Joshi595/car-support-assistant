"""Customer routes: chat (Server-Sent Events), feedback, handoff and reading a conversation."""

import json
import logging
import time
import uuid
from collections.abc import Iterator
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from car_support.api.limits import limiter
from car_support.config import get_settings
from car_support.db.models import Conversation, Feedback, Message, Ticket
from car_support.db.session import get_session
from car_support.guardrails import redact
from car_support.pipeline.graph import build_graph, new_state
from car_support.pipeline.prompts import detect_language

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["customer"])

Market = Literal["de", "uk", "us"]
UNAVAILABLE = {
    "en": "Sorry, I can't answer right now. Would you like me to connect you with a member of our team?",
    "de": "Ich kann gerade nicht antworten. Soll ich Sie mit einem Mitarbeiter verbinden?",
}
OFFER_HANDOFF = {"refuse", "unavailable"}  # outcomes after which the UI offers a human


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    market: Market
    conversation_id: uuid.UUID | None = None


class FeedbackRequest(BaseModel):
    conversation_id: uuid.UUID
    message_id: int
    rating: Literal[1, -1]
    comment: str | None = Field(default=None, max_length=1000)


class HandoffRequest(BaseModel):
    conversation_id: uuid.UUID
    reason: Literal["customer_request", "refusal", "negative_feedback", "unavailable"] = "customer_request"


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _conversation(session: Session, conversation_id: uuid.UUID) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    return conversation


def open_ticket(session: Session, conversation: Conversation, reason: str) -> None:
    """Hand the conversation to a human; an existing ticket is reopened instead of duplicated."""
    session.execute(
        insert(Ticket)
        .values(conversation_id=conversation.id, reason=reason)
        .on_conflict_do_update(index_elements=[Ticket.conversation_id], set_={"status": "open"})
    )
    conversation.status = "handed_off"


@router.post("/chat")
@limiter.limit(lambda: get_settings().chat_rate_limit)
def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    """Stream an answer as Server-Sent Events:

    - `meta`: `{conversation_id}`
    - `token`: `{text}` while the answer is generated (draft; may still be corrected)
    - `done`: `{message_id, answer, outcome, sources, offer_handoff}`, the final, validated answer
    """
    with get_session() as session:
        if body.conversation_id:
            conversation = _conversation(session, body.conversation_id)
        else:
            conversation = Conversation(id=uuid.uuid4(), market=body.market)
            session.add(conversation)
        history = [
            (m.role, m.content)
            for m in session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.id.desc())
                .limit(6)
            )
        ][::-1]
        session.add(Message(conversation_id=conversation.id, role="user", content=redact(body.message)))
        session.commit()
        conversation_id, market = conversation.id, conversation.market

    def events() -> Iterator[str]:
        yield _sse("meta", {"conversation_id": conversation_id})
        started = time.perf_counter()
        final: dict[str, Any] = {}
        try:
            # With a list of stream modes, LangGraph yields (mode, data) pairs; its type hints do not say so.
            stream = cast(
                Iterator[tuple[str, Any]],
                build_graph().stream(
                    new_state(body.message, market, history), stream_mode=["messages", "values"]
                ),
            )
            for mode, data in stream:
                if mode == "messages":
                    chunk, meta = data
                    if meta.get("langgraph_node") == "generate" and chunk.content:
                        yield _sse("token", {"text": chunk.content})
                else:
                    final = data
        except Exception:  # the graph degrades internally; this is the last line of defence
            log.exception("chat: pipeline failed")
            final = {"answer": UNAVAILABLE[detect_language(body.message)], "outcome": "unavailable"}
        latency_ms = int(1000 * (time.perf_counter() - started))
        outcome = final.get("outcome", "unavailable")
        with get_session() as session:
            reply = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=redact(final["answer"]),
                outcome=outcome,
                citations=final.get("sources", []),
                model=get_settings().chat_model,
                latency_ms=latency_ms,
            )
            session.add(reply)
            if outcome == "handoff":
                open_ticket(session, _conversation(session, conversation_id), "customer_request")
            session.commit()
            message_id = reply.id
        log.info("chat answered", extra={"fields": {"outcome": outcome, "latency_ms": latency_ms}})
        yield _sse(
            "done",
            {
                "message_id": message_id,
                "answer": reply.content,
                "outcome": outcome,
                "sources": reply.citations,
                "offer_handoff": outcome in OFFER_HANDOFF,
            },
        )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
def feedback(body: FeedbackRequest) -> None:
    """Rate an assistant answer (+1/-1). Rating again replaces the earlier rating."""
    with get_session() as session:
        message = session.get(Message, body.message_id)
        if message is None or message.conversation_id != body.conversation_id or message.role != "assistant":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "answer not found in this conversation")
        session.execute(
            insert(Feedback)
            .values(message_id=message.id, rating=body.rating, comment=body.comment)
            .on_conflict_do_update(
                index_elements=[Feedback.message_id], set_={"rating": body.rating, "comment": body.comment}
            )
        )
        session.commit()


@router.post("/handoff", status_code=status.HTTP_201_CREATED)
def handoff(body: HandoffRequest) -> dict[str, str]:
    """The customer accepted the offer to talk to a person."""
    with get_session() as session:
        open_ticket(session, _conversation(session, body.conversation_id), body.reason)
        session.commit()
    return {"status": "handed_off"}


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: uuid.UUID) -> dict[str, Any]:
    with get_session() as session:
        conv = _conversation(session, conversation_id)
        messages = session.scalars(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
        )
        return {
            "id": conv.id,
            "market": conv.market,
            "status": conv.status,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "outcome": m.outcome,
                    "sources": m.citations,
                }
                for m in messages
            ],
        }
