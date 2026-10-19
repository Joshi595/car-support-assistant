"""Agent routes (signed-in agents only): handoff tickets, customer feedback, re-indexing."""

import logging
import uuid
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from car_support.api.auth import Agent
from car_support.config import get_settings
from car_support.db.models import Conversation, Feedback, Message, Ticket
from car_support.db.session import get_session
from car_support.ingest.index import index_corpus

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/admin", tags=["agent"])

TicketStatus = Literal["open", "in_progress", "resolved"]


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    assigned_to: str | None = None


def _message(m: Message) -> dict[str, Any]:
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "outcome": m.outcome,
        "sources": m.citations,
        "created_at": m.created_at,
    }


@router.get("/tickets")
def tickets(agent: Agent, status_filter: TicketStatus | None = None) -> list[dict[str, Any]]:
    with get_session() as session:
        query = select(Ticket, Conversation).join(Conversation).order_by(Ticket.created_at.desc())
        if status_filter:
            query = query.where(Ticket.status == status_filter)
        rows = session.execute(query.limit(200)).all()
        return [
            {
                "id": t.id,
                "conversation_id": c.id,
                "market": c.market,
                "reason": t.reason,
                "status": t.status,
                "assigned_to": t.assigned_to,
                "created_at": t.created_at,
                "last_customer_message": session.scalar(
                    select(Message.content)
                    .where(Message.conversation_id == c.id, Message.role == "user")
                    .order_by(Message.id.desc())
                    .limit(1)
                ),
            }
            for t, c in rows
        ]


@router.get("/tickets/{ticket_id}")
def ticket(ticket_id: int, agent: Agent) -> dict[str, Any]:
    """The ticket with the full transcript, cited sources and any feedback, so nobody asks twice."""
    with get_session() as session:
        t = session.get(Ticket, ticket_id)
        if t is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket not found")
        messages = session.scalars(
            select(Message).where(Message.conversation_id == t.conversation_id).order_by(Message.id)
        ).all()
        rows = session.execute(
            select(Feedback.message_id, Feedback.rating).where(
                Feedback.message_id.in_([m.id for m in messages])
            )
        )
        ratings = {message_id: rating for message_id, rating in rows}
        return {
            "id": t.id,
            "conversation_id": t.conversation_id,
            "reason": t.reason,
            "status": t.status,
            "assigned_to": t.assigned_to,
            "messages": [_message(m) | {"rating": ratings.get(m.id)} for m in messages],
        }


@router.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: int, body: TicketUpdate, agent: Agent) -> dict[str, Any]:
    with get_session() as session:
        t = session.get(Ticket, ticket_id)
        if t is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket not found")
        if body.status:
            t.status = body.status
            if body.status == "in_progress" and not t.assigned_to:
                t.assigned_to = agent
        if body.assigned_to is not None:
            t.assigned_to = body.assigned_to
        session.commit()
        return {"id": t.id, "status": t.status, "assigned_to": t.assigned_to}


@router.get("/feedback")
def feedback(agent: Agent, rating: int | None = None) -> list[dict[str, Any]]:
    """Rated answers with the question that preceded them: the raw material for new golden questions."""
    if rating not in (None, 1, -1):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "rating must be 1 or -1")
    with get_session() as session:
        query = select(Feedback, Message).join(Message).order_by(Feedback.created_at.desc())
        if rating is not None:
            query = query.where(Feedback.rating == rating)
        out = []
        for f, answer in session.execute(query.limit(200)).all():
            question = session.scalar(
                select(Message.content)
                .where(
                    Message.conversation_id == answer.conversation_id,
                    Message.role == "user",
                    Message.id < answer.id,
                )
                .order_by(Message.id.desc())
                .limit(1)
            )
            out.append(
                {
                    "message_id": answer.id,
                    "conversation_id": answer.conversation_id,
                    "rating": f.rating,
                    "comment": f.comment,
                    "question": question,
                    "answer": answer.content,
                    "outcome": answer.outcome,
                    "created_at": f.created_at,
                }
            )
        return out


def _reindex() -> None:
    with get_session() as session:
        report = index_corpus(session, get_settings().data_dir)
    log.info("reindex finished", extra={"fields": {"report": str(report)}})


@router.post("/reindex", status_code=status.HTTP_202_ACCEPTED)
def reindex(agent: Agent, background: BackgroundTasks) -> dict[str, str]:
    """Bring the index in line with data/ (incremental: only changed chunks are embedded)."""
    background.add_task(_reindex)
    log.info("reindex requested", extra={"fields": {"agent": agent, "request": str(uuid.uuid4())}})
    return {"status": "started"}
