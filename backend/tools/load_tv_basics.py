import os, sqlite3, requests

DB = os.path.join(os.path.dirname(__file__), "..", "imdb.db")
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
    inserted = 0
    for page in range(1, 3):  # возьми 2 страницы для примера
        data = fetch("/discover/tv", {"sort_by": "popularity.desc", "page": page, "language":"en-US"})
        for tv in data.get("results", []):
            cur.execute("""
                INSERT OR REPLACE INTO tmdb_movies(id, imdb_id, title, release_date, vote_average, poster_path, media_type)
                VALUES(?,?,?,?,?,?, 'tv')
            """, (
                tv["id"],
                None,
                tv.get("name"),
                tv.get("first_air_date"),
                tv.get("vote_average"),
                tv.get("poster_path"),
            ))
            inserted += 1
    con.commit(); con.close()
    print(f"Inserted {inserted} tv rows")

if __name__ == "__main__":
    main()
