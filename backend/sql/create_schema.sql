CREATE TABLE IF NOT EXISTS tmdb_movies (
    id INTEGER PRIMARY KEY,
    imdb_id TEXT,
    title TEXT,
    release_date TEXT,
    vote_average REAL,
    poster_path TEXT
);
CREATE TABLE IF NOT EXISTS tmdb_genres (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS tmdb_movie_genres (movie_id INTEGER, genre_id INTEGER);
CREATE TABLE IF NOT EXISTS tmdb_people (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS tmdb_movie_cast (
    movie_id INTEGER, person_id INTEGER, character TEXT, cast_order INTEGER
);
CREATE TABLE IF NOT EXISTS tmdb_movie_crew (
    movie_id INTEGER, person_id INTEGER, job TEXT
);

CREATE TABLE IF NOT EXISTS imdb_ratings (
    tconst TEXT PRIMARY KEY, averageRating REAL, numVotes INTEGER
);
CREATE INDEX IF NOT EXISTS idx_imdb_ratings_votes ON imdb_ratings(numVotes DESC);
CREATE INDEX IF NOT EXISTS idx_tmdb_movies_imdb_id ON tmdb_movies(imdb_id);
CREATE INDEX IF NOT EXISTS idx_tmdb_movie_genres_mid ON tmdb_movie_genres(movie_id);
CREATE INDEX IF NOT EXISTS idx_tmdb_movie_cast_mid ON tmdb_movie_cast(movie_id);
CREATE INDEX IF NOT EXISTS idx_tmdb_movie_crew_mid ON tmdb_movie_crew(movie_id);
