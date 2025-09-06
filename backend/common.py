# /home/skillseek/app/backend/common.py
import os, sqlite3, time

DB_PATH = "/home/skillseek/app/backend/imdb.db"  # твоя рабочая БД
JOIN_BASE_URL = os.getenv("JOIN_BASE_URL", "https://movie-vibe.online").rstrip("/")
SQLITE_TIMEOUT = 30

def conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=SQLITE_TIMEOUT, check_same_thread=False)
    con.row_factory = sqlite3.Row
    # лёгкие PRAGMA, чтобы меньше ловить "database is locked"
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA foreign_keys=ON;")
    return con

def now_ms() -> int:
    return int(time.time() * 1000)
