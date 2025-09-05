from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, sqlite3, json, time
import requests
from dotenv import load_dotenv
from typing import List, Optional, Dict, Any, Literal

load_dotenv()
TMDB_BEARER = os.getenv('TMDB_BEARER')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
PORT = int(os.getenv('PORT', '8000'))
CORS_ORIGINS = [o.strip() for o in os.getenv('CORS_ORIGINS', '*').split(',') if o]
DB_PATH = "/home/skillseek/app/backend/imdb.db" 
TMDB_API = 'https://api.themoviedb.org/3'

app = FastAPI(title='Movie Night API — Enriched TMDB + IMDb')
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS or ['*'], allow_methods=['*'], allow_headers=['*'])

# --- SQLite helpers

def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def ensure_schema():
    c = conn(); cur = c.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS title_ratings (
        tconst TEXT PRIMARY KEY,
        averageRating REAL,
        numVotes INTEGER
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS movies_enriched (
        tmdb_id INTEGER PRIMARY KEY,
        imdb_id TEXT,
        title TEXT,
        release_date TEXT,
        genre_ids TEXT,    -- JSON array of ints
        tmdb_vote REAL,
        imdb_rating REAL,
        imdb_votes INTEGER,
        poster_path TEXT,
        overview TEXT,
        updated_at INTEGER
    )''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_movies_imdb_id ON movies_enriched(imdb_id)')
    c.commit(); c.close()

ensure_schema()

# --- TMDB client

def tmdb_headers() -> Dict[str, str]:
    if TMDB_BEARER:
        return {'Authorization': f'Bearer {TMDB_BEARER}', 'Accept': 'application/json'}
    return {}

def tmdb_get(path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    params = params or {}
    if TMDB_API_KEY and 'api_key' not in params and not TMDB_BEARER:
        params['api_key'] = TMDB_API_KEY
    r = requests.get(TMDB_API + path, params=params, headers=tmdb_headers(), timeout=20)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()

# --- Models
class DiscoverFilters(BaseModel):
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    genre_ids: Optional[List[int]] = None
    vote_average_min: Optional[float] = None  # TMDB rating filter
    people: Optional[List[str]] = None        # names to resolve to person IDs
    page: int = 1

class MovieOut(BaseModel):
    id: int
    title: str
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    release_date: Optional[str] = None
    genres: Optional[List[int]] = None
    tmdb_vote: Optional[float] = None
    imdb_rating: Optional[float] = None
    imdb_votes: Optional[int] = None
    imdb_id: Optional[str] = None

class CatalogFilters(BaseModel):
    title: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    tmdb_min: Optional[float] = None
    imdb_min: Optional[float] = None
    genres: Optional[List[str]] = None
    genres_mode: Literal["any","all"] = "any"
    director: Optional[str] = None
    actor: Optional[str] = None
    type: Optional[Literal["movie","tv"]] = None   # <--- новое
    sort_by: Literal["imdb","tmdb","year","title"] = "imdb"
    order: Literal["desc","asc"] = "desc"
    page: int = 1
    page_size: int = 20

class CatalogItem(BaseModel):
    tmdb_id: int
    imdb_id: Optional[str]
    title: str
    year: Optional[int]
    tmdb_rating: Optional[float]
    imdb_rating: Optional[float]
    genres: Optional[str]
    director: Optional[str]
    actors: Optional[str]
    poster_url: Optional[str]
    type: Literal["movie","tv"]                 # <--- новое
    duration_text: Optional[str]                # <--- новое
    episodes: Optional[int] 

# --- Utils

def now_ms() -> int:
    return int(time.time()*1000)

# IMDb lookup
def imdb_lookup(imdb_id: str | None) -> Dict[str, Any] | None:
    if not imdb_id:
        return None
    c = conn(); cur = c.cursor()
    cur.execute('SELECT averageRating, numVotes FROM title_ratings WHERE tconst=?', (imdb_id,))
    row = cur.fetchone(); c.close()
    if row:
        return {'imdb_rating': row['averageRating'], 'imdb_votes': row['numVotes']}
    return None

# Persist/Cache enriched movie row

def upsert_movie_enriched(m: Dict[str, Any], imdb_id: str | None, imdb: Dict[str, Any] | None):
    c = conn(); cur = c.cursor()
    cur.execute('''INSERT INTO movies_enriched(
        tmdb_id, imdb_id, title, release_date, genre_ids, tmdb_vote,
        imdb_rating, imdb_votes, poster_path, overview, updated_at
    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(tmdb_id) DO UPDATE SET
        imdb_id=excluded.imdb_id,
        title=excluded.title,
        release_date=excluded.release_date,
        genre_ids=excluded.genre_ids,
        tmdb_vote=excluded.tmdb_vote,
        imdb_rating=excluded.imdb_rating,
        imdb_votes=excluded.imdb_votes,
        poster_path=excluded.poster_path,
        overview=excluded.overview,
        updated_at=excluded.updated_at''', (
        m['id'], imdb_id, m.get('title') or m.get('original_title') or '',
        m.get('release_date'), json.dumps(m.get('genre_ids') or []),
        m.get('vote_average'),
        (imdb or {}).get('imdb_rating'), (imdb or {}).get('imdb_votes'),
        m.get('poster_path'), m.get('overview'), now_ms()
    ))
    c.commit(); c.close()

# Try cache first

def get_cached_enriched(tmdb_id: int) -> Dict[str, Any] | None:
    c = conn(); cur = c.cursor()
    cur.execute('SELECT * FROM movies_enriched WHERE tmdb_id=?', (tmdb_id,))
    row = cur.fetchone(); c.close()
    if not row:
        return None
    return dict(row)

# --- Routes
@app.post("/catalog/search", response_model=CatalogResponse)
def catalog_search(filters: CatalogFilters):
    where = ["1=1"]
    params: List[object] = []

    if filters.title:
        where.append("title LIKE ?")
        params.append(f"%{filters.title}%")

    if filters.year_from is not None:
        where.append("year >= ?")
        params.append(filters.year_from)

    if filters.year_to is not None:
        where.append("year <= ?")
        params.append(filters.year_to)

    if filters.tmdb_min is not None:
        where.append("tmdb_rating >= ?")
        params.append(filters.tmdb_min)

    if filters.imdb_min is not None:
        where.append("imdb_rating >= ?")
        params.append(filters.imdb_min)

    if filters.director:
        where.append("director LIKE ?")
        params.append(f"%{filters.director}%")

    if filters.actor:
        where.append("actors LIKE ?")
        params.append(f"%{filters.actor}%")

    # жанры лежат строкой "Action, Comedy, ..."
    if filters.genres:
        if filters.genres_mode == "all":
            # все жанры должны встречаться
            for g in filters.genres:
                where.append("genres LIKE ?")
                params.append(f"%{g}%")
        else:
            # хотя бы один из жанров
            ors = []
            for g in filters.genres:
                ors.append("genres LIKE ?")
                params.append(f"%{g}%")
            where.append("(" + " OR ".join(ors) + ")")

    where_sql = " AND ".join(where)

    sort_map = {
        "imdb": "imdb_rating",
        "tmdb": "tmdb_rating",
        "year": "year",
        "title": "title"
    }
    order_by = sort_map[filters.sort_by]
    order_dir = "DESC" if filters.order.lower() == "desc" else "ASC"

    # пагинация
    page = max(1, filters.page)
    page_size = min(100, max(1, filters.page_size))
    offset = (page - 1) * page_size

    # считаем total
    count_sql = f"SELECT COUNT(*) AS cnt FROM unified_catalog WHERE {where_sql}"
    con = _connect()
    try:
        total = con.execute(count_sql, params).fetchone()["cnt"]

        # основная выборка
        select_sql = f"""
        SELECT tmdb_id, imdb_id, title, year, tmdb_rating, imdb_rating, genres, director, actors, poster_url
        FROM unified_catalog
        WHERE {where_sql}
        ORDER BY {order_by} {order_dir}, title ASC
        LIMIT ? OFFSET ?
        """
        rows = con.execute(select_sql, (*params, page_size, offset)).fetchall()

        results = [CatalogItem(**dict(r)) for r in rows]
        return CatalogResponse(total=total, page=page, page_size=page_size, results=results)
    finally:
        con.close()

@app.get('/health')
def health():
    return {'ok': True}

@app.get('/genres')
def genres():
    j = tmdb_get('/genre/movie/list', params={'language':'en-US'})
    return j.get('genres', [])

@app.post('/discover', response_model=Dict[str, Any])
def discover(filters: DiscoverFilters):
    # resolve people -> person ids
    person_ids: List[int] = []
    for name in (filters.people or []):
        j = tmdb_get('/search/person', params={'query': name, 'include_adult': False, 'page': 1})
        if j.get('results'):
            person_ids.append(j['results'][0]['id'])

    params: Dict[str, Any] = {
        'page': max(1, filters.page),
        'include_adult': False,
        'sort_by': 'popularity.desc'
    }
    if filters.year_from:
        params['primary_release_date.gte'] = f"{filters.year_from}-01-01"
    if filters.year_to:
        params['primary_release_date.lte'] = f"{filters.year_to}-12-31"
    if filters.vote_average_min:
        params['vote_average.gte'] = filters.vote_average_min
    if filters.genre_ids:
        params['with_genres'] = ','.join(map(str, filters.genre_ids))
    if person_ids:
        params['with_people'] = ','.join(map(str, person_ids))

    data = tmdb_get('/discover/movie', params=params)

    out: List[MovieOut] = []
    for m in data.get('results', []):
        # check cache first
        cached = get_cached_enriched(m['id'])
        if cached and cached.get('imdb_id'):
            out.append(MovieOut(
                id=m['id'],
                title=cached['title'] or (m.get('title') or ''),
                overview=cached.get('overview') or m.get('overview'),
                poster_path=cached.get('poster_path') or m.get('poster_path'),
                release_date=cached.get('release_date') or m.get('release_date'),
                genres=json.loads(cached.get('genre_ids') or '[]'),
                tmdb_vote=cached.get('tmdb_vote') or m.get('vote_average'),
                imdb_rating=cached.get('imdb_rating'),
                imdb_votes=cached.get('imdb_votes'),
                imdb_id=cached.get('imdb_id')
            ).model_dump())
            continue
            
        # fetch external_ids -> imdb_id
        ext = tmdb_get(f"/movie/{m['id']}/external_ids")
        imdb_id = ext.get('imdb_id')
        imdb = imdb_lookup(imdb_id)

        # persist enriched row for future cache & return
        upsert_movie_enriched(m, imdb_id, imdb)

        out.append(MovieOut(
            id=m['id'],
            title=m.get('title') or m.get('original_title') or '',
            overview=m.get('overview'),
            poster_path=m.get('poster_path'),
            release_date=m.get('release_date'),
            genres=m.get('genre_ids'),
            tmdb_vote=m.get('vote_average'),
            imdb_rating=(imdb or {}).get('imdb_rating'),
            imdb_votes=(imdb or {}).get('imdb_votes'),
            imdb_id=imdb_id
        ).model_dump())

    return {
        'page': data.get('page', 1),
        'total_pages': data.get('total_pages', 1),
        'results': out
    }
