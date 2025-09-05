import os, sqlite3, requests, time

DB = os.path.join(os.path.dirname(__file__), "..", "imdb.db")
TMDB_API = "https://api.themoviedb.org/3"
TMDB_BEARER = os.getenv("TMDB_BEARER", "").strip()
HEADERS = {"Authorization": f"Bearer {TMDB_BEARER}", "Accept": "application/json"}

def get_movie_details(mid:int):
    url = f"{TMDB_API}/movie/{mid}"
    params = {"append_to_response":"external_ids,credits","language":"en-US"}
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

con = sqlite3.connect(DB)
cur = con.cursor()

mids = [r[0] for r in cur.execute("""
SELECT m.id
FROM tmdb_movies m
LEFT JOIN tmdb_movie_genres g ON g.movie_id=m.id
LEFT JOIN tmdb_movie_cast c ON c.movie_id=m.id
LEFT JOIN tmdb_movie_crew w ON w.movie_id=m.id
WHERE m.imdb_id IS NULL OR m.runtime_minutes IS NULL OR g.movie_id IS NULL OR c.movie_id IS NULL OR w.movie_id IS NULL
GROUP BY m.id
LIMIT 400
""").fetchall()]

print(f"to fetch: {len(mids)}")
for i, mid in enumerate(mids, 1):
    try:
        j = get_movie_details(mid)

        imdb_id = (j.get("external_ids") or {}).get("imdb_id") or None
        runtime_minutes = j.get("runtime")  # int | None

        cur.execute("""
            UPDATE tmdb_movies
               SET imdb_id=?,
                   runtime_minutes=?,
                   media_type=COALESCE(media_type,'movie')
             WHERE id=?
        """, (imdb_id, runtime_minutes, mid))

        # genres
        cur.execute("DELETE FROM tmdb_movie_genres WHERE movie_id=?", (mid,))
        for g in (j.get("genres") or []):
            cur.execute("INSERT OR IGNORE INTO tmdb_genres(id,name) VALUES(?,?)", (g["id"], g["name"]))
            cur.execute("INSERT INTO tmdb_movie_genres(movie_id,genre_id) VALUES(?,?)", (mid, g["id"]))

        # crew/director + cast
        credits = j.get("credits") or {}

        cur.execute("DELETE FROM tmdb_movie_crew WHERE movie_id=?", (mid,))
        for w in (credits.get("crew") or []):
            if w.get("job") == "Director":
                cur.execute("INSERT OR IGNORE INTO tmdb_people(id,name) VALUES(?,?)", (w["id"], w["name"]))
                cur.execute("INSERT INTO tmdb_movie_crew(movie_id,person_id,job) VALUES(?,?,?)",
                            (mid, w["id"], "Director"))

        cur.execute("DELETE FROM tmdb_movie_cast WHERE movie_id=?", (mid,))
        for c in (credits.get("cast") or [])[:20]:
            cur.execute("INSERT OR IGNORE INTO tmdb_people(id,name) VALUES(?,?)", (c["id"], c["name"]))
            cur.execute("INSERT INTO tmdb_movie_cast(movie_id,person_id,character,cast_order) VALUES(?,?,?,?)",
                        (mid, c["id"], c.get("character"), c.get("order", 9999)))

        if i % 20 == 0:
            con.commit(); time.sleep(0.2)
    except Exception as e:
        print(f"[ERR] {mid}: {e}")

con.commit()
con.close()
print("done")
