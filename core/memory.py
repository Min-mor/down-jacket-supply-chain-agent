"""会话记忆：读写数据库中的会话与消息。

graph 的 SupplyState.history 在 API 层从数据库加载，传给 Agent 做多轮上下文；
每一轮问答后再落库。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .config import settings
from .db import Conversation, Message


def get_or_create_conversation(db: Session, conversation_id: str | None = None) -> Conversation:
    if conversation_id:
        conv = db.get(Conversation, conversation_id)
        if conv:
            return conv
    conv = Conversation()
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def load_history(db: Session, conversation_id: str, limit: int | None = None) -> list[tuple[str, str]]:
    """按时间顺序返回历史 (question, answer)。limit 取最近 N 轮。"""
    q = (db.query(Message)
         .filter(Message.conversation_id == conversation_id)
         .order_by(Message.created_at.asc()))
    rows = q.all()
    if limit and len(rows) > limit * 2:
        rows = rows[-(limit * 2):]
    pairs: list[tuple[str, str]] = []
    i = 0
    while i + 1 < len(rows):
        if rows[i].role == "user" and rows[i + 1].role == "assistant":
            pairs.append((rows[i].content, rows[i + 1].content))
        i += 1
    return pairs


def append_turn(db: Session, conversation_id: str, question: str, answer: str, agent_name: str) -> None:
    db.add(Message(conversation_id=conversation_id, role="user", content=question))
    db.add(Message(conversation_id=conversation_id, role="assistant", content=answer, agent_name=agent_name))
    db.commit()


def build_llm_messages(history: list[tuple[str, str]], question: str) -> list[Any]:
    """把历史 + 当前问题转成给 LLM 的消息序列（多轮上下文）。"""
    from langchain_core.messages import AIMessage, HumanMessage

    msgs: list[Any] = []
    for q, a in history[-settings.max_history_turns:]:
        msgs.append(HumanMessage(content=q))
        if a:
            msgs.append(AIMessage(content=a))
    msgs.append(HumanMessage(content=question))
    return msgs
