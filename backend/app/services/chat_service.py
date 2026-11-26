"""Conversations on the Scout page: kept on the server, so a chat survives a refresh and a new tab.

A conversation belongs to an account, or (before signing in) to the random number one browser keeps.
Signing in claims the browser's conversations for the account. Only the owner can read or delete one.
"""

import json

from sqlalchemy import text

TITLE_LENGTH, KEEP_SOURCE_TEXT, HISTORY_TURNS = 80, 900, 4


def _owner_sql(user_id: int | None) -> str:
    return "user_id = :user" if user_id is not None else "user_id is null and visitor = cast(:visitor as uuid)"


def claim(db, user_id: int | None, visitor: str | None) -> None:
    """Conversations started in this browser before signing in now belong to the account."""
    if user_id is not None and visitor:
        db.execute(text("update chat_conversations set user_id = :user where user_id is null and visitor = cast(:visitor as uuid)"), {"user": user_id, "visitor": visitor})
        db.commit()


def list_chats(db, user_id: int | None, visitor: str | None) -> list[dict]:
    if user_id is None and not visitor:
        return []
    claim(db, user_id, visitor)
    found = db.execute(text(f"""
        select c.id::text as id, c.title, c.updated_at::text as updated_at, count(m.id) as turns
        from chat_conversations c left join chat_messages m on m.conversation_id = c.id
        where {_owner_sql(user_id)} group by c.id order by c.updated_at desc limit 100
    """), {"user": user_id, "visitor": visitor}).mappings().all()
    return [dict(r) for r in found]


def get_chat(db, user_id: int | None, visitor: str | None, chat_id: str) -> list[dict] | None:
    owned = db.execute(text(f"select 1 from chat_conversations where id = cast(:id as uuid) and {_owner_sql(user_id)}"), {"id": chat_id, "user": user_id, "visitor": visitor}).first()
    if not owned:
        return None
    found = db.execute(text("select question, answer, created_at::text as asked_at from chat_messages where conversation_id = cast(:id as uuid) order by id"), {"id": chat_id}).mappings().all()
    return [dict(r) for r in found]


def history(db, user_id: int | None, visitor: str | None, chat_id: str) -> list[str]:
    """The last questions of the conversation as the system understood them, oldest first, for follow-ups."""
    turns = get_chat(db, user_id, visitor, chat_id) or []
    return [(t["answer"].get("understood") or t["question"]) for t in turns[-HISTORY_TURNS:]]


def append(db, user_id: int | None, visitor: str | None, chat_id: str, question: str, answer: dict) -> bool:
    """Adds a turn; starts the conversation if it is new. False when the conversation belongs to someone else."""
    exists = db.execute(text("select user_id, visitor::text from chat_conversations where id = cast(:id as uuid)"), {"id": chat_id}).first()
    if exists is None:
        db.execute(text("insert into chat_conversations (id, user_id, visitor, title) values (cast(:id as uuid), :user, cast(:visitor as uuid), :title)"),
                   {"id": chat_id, "user": user_id, "visitor": visitor, "title": question[:TITLE_LENGTH]})
    elif not (exists[0] == user_id if user_id is not None else exists[0] is None and exists[1] == visitor):
        return False
    stored = {**answer, "sources": [{**s, "source_text": s.get("source_text", "")[:KEEP_SOURCE_TEXT]} for s in answer.get("sources", [])]}
    db.execute(text("insert into chat_messages (conversation_id, question, answer) values (cast(:id as uuid), :q, cast(:a as jsonb))"), {"id": chat_id, "q": question, "a": json.dumps(stored, default=str)})
    db.execute(text("update chat_conversations set updated_at = now() where id = cast(:id as uuid)"), {"id": chat_id})
    db.commit()
    return True


def delete_chat(db, user_id: int | None, visitor: str | None, chat_id: str) -> bool:
    gone = db.execute(text(f"delete from chat_conversations where id = cast(:id as uuid) and {_owner_sql(user_id)}"), {"id": chat_id, "user": user_id, "visitor": visitor}).rowcount
    db.commit()
    return bool(gone)
