import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

SESSION_DAYS = 30
VISIT_GAP_MINUTES = 30  # a longer pause starts a new visit
_SCRYPT = {"n": 2 ** 15, "r": 8, "p": 1, "maxmem": 64 * 1024 * 1024, "dklen": 32}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt${salt.hex()}${hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT).hex()}"


def check_password(password: str, stored: str) -> bool:
    _, salt, digest = stored.split("$")
    return hmac.compare_digest(hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT), bytes.fromhex(digest))


_DUMMY = hash_password("no such user")  # keeps unknown emails as slow as wrong passwords


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_user(db, email: str, name: str, password: str):
    try:
        user = db.execute(text("insert into app_users (email, display_name, password_hash) values (:e, :n, :p) returning id, email, display_name, created_at"), {"e": email, "n": name, "p": hash_password(password)}).mappings().one()
        db.commit()
        return dict(user)
    except IntegrityError:
        db.rollback()
        return None


def authenticate(db, email: str, password: str):
    user = db.execute(text("select * from app_users where email = :e"), {"e": email}).mappings().first()
    if not check_password(password, user["password_hash"] if user else _DUMMY) or not user:
        return None
    return {k: user[k] for k in ("id", "email", "display_name", "created_at")}


def start_session(db, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.execute(text("delete from app_sessions where expires_at < now()"))
    db.execute(text("insert into app_sessions (token_hash, user_id, expires_at) values (:t, :u, :x)"), {"t": _digest(token), "u": user_id, "x": datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)})
    db.commit()
    return token


def end_session(db, token: str):
    db.execute(text("delete from app_sessions where token_hash = :t"), {"t": _digest(token)})
    db.commit()


def user_for(db, token: str | None):
    if not token:
        return None
    row = db.execute(text("select u.id, u.email, u.display_name, u.created_at, u.state from app_sessions s join app_users u on u.id = s.user_id where s.token_hash = :t and s.expires_at > now()"), {"t": _digest(token)}).mappings().first()
    return dict(row) if row else None


def save_state(db, user_id: int, state: dict):
    db.execute(text("update app_users set state = cast(:s as jsonb) where id = :u"), {"s": json.dumps(state), "u": user_id})
    db.commit()


def record_view(db, user_id: int, player_id: int):
    last = db.execute(text("select player_id, visit, viewed_at > now() - make_interval(mins => :gap) as fresh from player_views where user_id = :u order by viewed_at desc limit 1"), {"u": user_id, "gap": VISIT_GAP_MINUTES}).mappings().first()
    if last and last["fresh"] and last["player_id"] == player_id:
        return  # reloading a page is not a new view
    visit = (last["visit"] + (0 if last["fresh"] else 1)) if last else 1
    db.execute(text("insert into player_views (user_id, player_id, visit) select :u, id, :v from players where id = :p"), {"u": user_id, "p": player_id, "v": visit})
    db.commit()


def also_viewed(db, player_id: int, limit: int = 6):
    """Players opened in the same visit.

    Each user counts once per pair, weighted by recency (half after 60 days), and the total is
    divided by the root of both players' audiences, so popular players do not win everywhere.
    """
    return [dict(r) for r in db.execute(text("""
        with pairs as (
            select a.user_id, b.player_id, max(power(0.5, extract(epoch from now() - b.viewed_at)::float / 86400 / 60)) as weight
            from player_views a
            join player_views b on b.user_id = a.user_id and b.visit = a.visit and b.player_id <> a.player_id
            where a.player_id = :p
            group by a.user_id, b.player_id
        ), audience as (
            select player_id, count(distinct user_id) as users from player_views
            where player_id = :p or player_id in (select player_id from pairs) group by player_id
        )
        select pairs.player_id, count(*) as viewers, max(me.users) as audience,
               (sum(pairs.weight) / sqrt(max(audience.users) * max(me.users)))::float as score
        from pairs
        join audience on audience.player_id = pairs.player_id
        join audience me on me.player_id = :p
        group by pairs.player_id having count(*) >= 2 order by score desc, viewers desc limit :n
    """), {"p": player_id, "n": limit}).mappings()]


def activity(db, user_id: int):
    def fetch(sql):
        return [dict(r) for r in db.execute(text(sql), {"u": user_id}).mappings()]

    return {
        "views": fetch("select player_id, count(*) as views, max(viewed_at)::text as last_viewed from player_views where user_id = :u group by 1 order by views desc, max(viewed_at) desc"),
        "days": fetch("select viewed_at::date::text as day, count(*) as views from player_views where user_id = :u and viewed_at > now() - interval '30 days' group by 1 order by 1"),
        "visits": db.execute(text("select coalesce(max(visit), 0) from player_views where user_id = :u"), {"u": user_id}).scalar(),
        "suggested": fetch("""
            with mine as (select distinct player_id from player_views where user_id = :u)
            select b.player_id, count(distinct b.user_id) as viewers
            from player_views a join player_views b on b.user_id = a.user_id and b.visit = a.visit
            where a.player_id in (select player_id from mine) and b.player_id not in (select player_id from mine) and a.user_id <> :u
            group by 1 having count(distinct b.user_id) >= 2 order by viewers desc limit 6
        """),
    }


def clear_activity(db, user_id: int):
    db.execute(text("delete from player_views where user_id = :u"), {"u": user_id})
    db.commit()


def delete_user(db, user_id: int):
    db.execute(text("delete from app_users where id = :u"), {"u": user_id})
    db.commit()
