import os, sqlite3, requests

DB = "imdb.db"
TMDB_API = "https://api.themoviedb.org/3"
TMDB_BEARER = os.getenv("TMDB_BEARER", "").strip()
HEADERS = {"Authorization": f"Bearer {TMDB_BEARER}", "Accept": "application/json"}

def fetch(path, params=None):
    r = requests.get(TMDB_API + path, headers=HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    # одна страница для проверки; потом просто увеличишь range(1, N)
    data = fetch("/discover/movie", {"sort_by":"popularity.desc","page":1,"language":"en-US"})
    for m in data.get("results", []):
        cur.execute("""
        INSERT OR REPLACE INTO tmdb_movies(id, imdb_id, title, release_date, vote_average, poster_path)
        VALUES(?,?,?,?,?,?)
        """, (m["id"], None, m["title"], m.get("release_date"), m.get("vote_average"), m.get("poster_path")))
    con.commit()
    con.close()
    print(f"Inserted {len(data.get('results', []))} movies")

if __name__ == "__main__":
    main()
