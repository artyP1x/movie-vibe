import os, sqlite3, requests, statistics, time

DB = os.path.join(os.path.dirname(__file__), "..", "imdb.db")
TMDB_API = "https://api.themoviedb.org/3"
TMDB_BEARER = os.getenv("TMDB_BEARER", "").strip()
HEADERS = {"Authorization": f"Bearer {TMDB_BEARER}", "Accept": "application/json"}

def get_tv_details(tid:int):
    url = f"{TMDB_API}/tv/{tid}"
    params = {"append_to_response":"external_ids,credits","language":"en-US"}
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

con = sqlite3.connect(DB)
cur = con.cursor()

tids = [r[0] for r in con.execute("""
SELECT id FROM tmdb_movies WHERE media_type='tv'
AND (episodes_count IS NULL OR EXISTS(SELECT 1 FROM tmdb_movie_genres g WHERE g.movie_id=id) IS NULL)
LIMIT 400
""").fetchall()]

print(f"to fetch tv: {len(tids)}")
for i, tid in enumerate(tids, 1):
    try:
        j = get_tv_details(tid)
        imdb_id = (j.get("external_ids") or {}).get("imdb_id") or None
        eps = j.get("number_of_episodes")
        run_arr = j.get("episode_run_time") or []
        runtime_minutes = int(statistics.mean(run_arr)) if run_arr else None

        cur.execute("""
            UPDATE tmdb_movies
               SET imdb_id=?,
                   episodes_count=?,
                   runtime_minutes=?,
                   media_type='tv'
             WHERE id=?
        """, (imdb_id, eps, runtime_minutes, tid))

        # genres
        con.execute("DELETE FROM tmdb_movie_genres WHERE movie_id=?", (tid,))
        for g in (j.get("genres") or []):
            con.execute("INSERT OR IGNORE INTO tmdb_genres(id,name) VALUES(?,?)", (g["id"], g["name"]))
            con.execute("INSERT INTO tmdb_movie_genres(movie_id,genre_id) VALUES(?,?)", (tid, g["id"]))

        # crew/director-like (TMDB у TV показывает 'Director' per-episode, оставим как есть: show-level 'Created by' пропустим)
        con.execute("DELETE FROM tmdb_movie_cast WHERE movie_id=?", (tid,))
        credits = j.get("credits") or {}
        for c in (credits.get("cast") or [])[:20]:
            con.execute("INSERT OR IGNORE INTO tmdb_people(id,name) VALUES(?,?)", (c["id"], c["name"]))
            con.execute("INSERT INTO tmdb_movie_cast(movie_id,person_id,character,cast_order) VALUES(?,?,?,?)",
                        (tid, c["id"], c.get("character"), c.get("order", 9999)))
        # crew режиссёров можно частично подтянуть, но для TV бывают эпизодные директоры — оставим пусто/редко

        if i % 20 == 0:
            con.commit(); time.sleep(0.2)
    except Exception as e:
        print(f"[ERR] tv {tid}: {e}")

con.commit(); con.close(); print("done tv")
