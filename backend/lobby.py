# /home/skillseek/app/backend/lobby.py
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
import sqlite3

from common import conn, JOIN_BASE_URL, now_ms
from core import gen_lobby_code, make_qr_png_base64

router = APIRouter(prefix="/lobby", tags=["lobby"])

def ensure_lobby_schema():
    con = conn()
    try:
        cur = con.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS lobbies(
            id            TEXT PRIMARY KEY,         -- код = id
            created_at_ms INTEGER NOT NULL,
            active        INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS lobby_members(
            lobby_id  TEXT NOT NULL,
            user_id   TEXT NOT NULL,
            nickname  TEXT,
            joined_ms INTEGER NOT NULL,
            PRIMARY KEY(lobby_id, user_id),
            FOREIGN KEY(lobby_id) REFERENCES lobbies(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS lobby_swipes(
            lobby_id  TEXT NOT NULL,
            user_id   TEXT NOT NULL,
            item_id   INTEGER NOT NULL,             -- tmdb_id
            decision  TEXT NOT NULL CHECK(decision IN ('like','skip')),
            ts_ms     INTEGER NOT NULL,
            PRIMARY KEY(lobby_id, user_id, item_id),
            FOREIGN KEY(lobby_id) REFERENCES lobbies(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS lobby_matches(
            lobby_id  TEXT NOT NULL,
            item_id   INTEGER NOT NULL,
            matched_ms INTEGER NOT NULL,
            PRIMARY KEY(lobby_id, item_id),
            FOREIGN KEY(lobby_id) REFERENCES lobbies(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_swipes_item ON lobby_swipes(lobby_id, item_id);
        """)
        con.commit()
    finally:
        con.close()

ensure_lobby_schema()

# ----------- pydantic -----------
class CreateLobbyIn(BaseModel):
    user_id: str
    nickname: Optional[str] = None

class JoinLobbyIn(BaseModel):
    code: str
    user_id: str
    nickname: Optional[str] = None

class SwipeIn(BaseModel):
    lobby_id: str
    user_id: str
    item_id: int
    decision: Literal["like","skip"]

# ----------- routes -----------
@router.post("/create")
def create_lobby(data: CreateLobbyIn):
    code = gen_lobby_code(16)
    tnow = now_ms()
    con = conn()
    try:
        cur = con.cursor()
        cur.execute("INSERT INTO lobbies(id, created_at_ms, active) VALUES(?,?,1)", (code, tnow))
        cur.execute("""INSERT OR REPLACE INTO lobby_members(lobby_id, user_id, nickname, joined_ms)
                       VALUES(?,?,?,?)""", (code, data.user_id, data.nickname, tnow))
        con.commit()
    finally:
        con.close()

    join_url = f"{JOIN_BASE_URL}/lobby/{code}/join"
    qr_b64 = make_qr_png_base64(join_url)
    return {
        "lobby_id": code,
        "code": code,
        "join_url": join_url,
        "qr_png_base64": qr_b64
    }

@router.post("/join")
def join_lobby(data: JoinLobbyIn):
    code = (data.code or "").lower()
    con = conn()
    try:
        cur = con.cursor()
        row = cur.execute("SELECT id, active FROM lobbies WHERE id=?", (code,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Lobby not found")
        if row["active"] != 1:
            raise HTTPException(status_code=410, detail="Lobby inactive")

        cur.execute("""INSERT OR REPLACE INTO lobby_members(lobby_id, user_id, nickname, joined_ms)
                       VALUES(?,?,?,?)""", (code, data.user_id, data.nickname, now_ms()))
        con.commit()
        return {"ok": True, "lobby_id": code}
    finally:
        con.close()

@router.get("/{code}/info")
def lobby_info(code: str):
    con = conn()
    try:
        cur = con.cursor()
        lob = cur.execute("SELECT id, created_at_ms, active FROM lobbies WHERE id=?", (code,)).fetchone()
        if not lob:
            raise HTTPException(status_code=404, detail="Lobby not found")

        members = [dict(r) for r in cur.execute(
            "SELECT user_id, nickname, joined_ms FROM lobby_members WHERE lobby_id=? ORDER BY joined_ms ASC",
            (code,))]
        matches = [dict(r) for r in cur.execute(
            "SELECT item_id, matched_ms FROM lobby_matches WHERE lobby_id=? ORDER BY matched_ms DESC LIMIT 50",
            (code,))]

        return {
            "lobby_id": lob["id"],
            "active": bool(lob["active"]),
            "created_at_ms": lob["created_at_ms"],
            "members": members,
            "matches": matches,
        }
    finally:
        con.close()

@router.get("/{code}/qr")
def lobby_qr(code: str):
    # отдаём PNG прямо байтами
    join_url = f"{JOIN_BASE_URL}/lobby/{code}/join"
    png_b64 = make_qr_png_base64(join_url)
    import base64
    png = base64.b64decode(png_b64)
    return Response(content=png, media_type="image/png")

@router.post("/swipe")
def lobby_swipe(data: SwipeIn):
    con = conn()
    try:
        cur = con.cursor()
        # проверка членства
        m = cur.execute("""SELECT 1 FROM lobby_members WHERE lobby_id=? AND user_id=?""",
                        (data.lobby_id, data.user_id)).fetchone()
        if not m:
            raise HTTPException(status_code=403, detail="User is not in lobby")

        cur.execute("""INSERT OR REPLACE INTO lobby_swipes(lobby_id,user_id,item_id,decision,ts_ms)
                       VALUES(?,?,?,?,?)""",
                    (data.lobby_id, data.user_id, data.item_id, data.decision, now_ms()))

        matched = False
        # если лайк — проверить, лайкнул ли кто-то ещё
        if data.decision == "like":
            liked_count = cur.execute("""
                SELECT COUNT(*) AS c FROM lobby_swipes
                 WHERE lobby_id=? AND item_id=? AND decision='like'
            """, (data.lobby_id, data.item_id)).fetchone()["c"]
            # два и более лайков → матч фиксируем
            if liked_count >= 2:
                cur.execute("""INSERT OR IGNORE INTO lobby_matches(lobby_id,item_id,matched_ms)
                               VALUES(?,?,?)""", (data.lobby_id, data.item_id, now_ms()))
                matched = True

        con.commit()
        return {"ok": True, "matched": matched}
    finally:
        con.close()
