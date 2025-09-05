CREATE TABLE IF NOT EXISTS tmdb_movies (
    id INTEGER PRIMARY KEY,
    imdb_id TEXT,
    title TEXT,
    release_date TEXT,
    vote_average REAL,
    poster_path TEXT
);

CREATE TABLE IF NOT EXISTS tmdb_genres (
    id INTEGER PRIMARY KEY,
    name TEXT
);

CREATE TABLE IF NOT EXISTS tmdb_movie_genres (
    movie_id INTEGER,
    genre_id INTEGER
);

CREATE TABLE IF NOT EXISTS tmdb_people (
    id INTEGER PRIMARY KEY,
    name TEXT
);

CREATE TABLE IF NOT EXISTS tmdb_movie_cast (
    movie_id INTEGER,
    person_id INTEGER,
    character TEXT
);

CREATE TABLE IF NOT EXISTS tmdb_movie_crew (
    movie_id INTEGER,
    person_id INTEGER,
    job TEXT
);
