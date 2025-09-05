DROP TABLE IF EXISTS unified_catalog;

CREATE TABLE unified_catalog AS
WITH
  genres_limited AS (
    SELECT
      mg.movie_id AS tmdb_id,
      g.name      AS genre_name,
      ROW_NUMBER() OVER (PARTITION BY mg.movie_id ORDER BY g.name) AS rn
    FROM tmdb_movie_genres mg
    JOIN tmdb_genres g ON g.id = mg.genre_id
  ),
  genres_agg AS (
    SELECT tmdb_id, GROUP_CONCAT(genre_name, ', ') AS genres
    FROM genres_limited
    WHERE rn <= 5
    GROUP BY tmdb_id
  ),
  directors AS (
    SELECT
      mc.movie_id AS tmdb_id,
      GROUP_CONCAT(p.name, ', ') AS director
    FROM tmdb_movie_crew mc
    JOIN tmdb_people p ON p.id = mc.person_id
    WHERE mc.job = 'Director'
    GROUP BY mc.movie_id
  ),
  actors_limited AS (
    SELECT
      mc.movie_id AS tmdb_id,
      p.name,
      ROW_NUMBER() OVER (
        PARTITION BY mc.movie_id
        ORDER BY COALESCE(mc.cast_order, 999999)
      ) AS rn
    FROM tmdb_movie_cast mc
    JOIN tmdb_people p ON p.id = mc.person_id
  ),
  actors_agg AS (
    SELECT tmdb_id, GROUP_CONCAT(name, ', ') AS actors
    FROM actors_limited
    WHERE rn <= 5
    GROUP BY tmdb_id
  )
SELECT
  m.id                       AS tmdb_id,
  m.imdb_id,
  m.title,
  CASE
    WHEN m.release_date IS NOT NULL AND LENGTH(m.release_date) >= 4
    THEN CAST(SUBSTR(m.release_date, 1, 4) AS INT)
  END                        AS year,
  ROUND(m.vote_average, 1)   AS tmdb_rating,
  ROUND(ir.averageRating, 1) AS imdb_rating,
  g.genres,
  d.director,
  a.actors,
  CASE
    WHEN m.poster_path IS NOT NULL AND m.poster_path <> ''
    THEN 'https://image.tmdb.org/t/p/w500' || m.poster_path
  END                        AS poster_url,
  COALESCE(m.media_type, 'movie') AS type,
  -- duration_text: для фильмов формат Xh Ym, для сериалов оставим NULL (используем episodes)
  CASE
    WHEN COALESCE(m.media_type,'movie')='movie' AND m.runtime_minutes IS NOT NULL
    THEN
      (CAST(m.runtime_minutes/60 AS INT) || 'h ' || (m.runtime_minutes%60) || 'm')
  END AS duration_text,
  -- episodes: показываем только для сериалов
  CASE
    WHEN COALESCE(m.media_type,'movie')='tv' THEN m.episodes_count
  END AS episodes
FROM tmdb_movies m
LEFT JOIN imdb_ratings ir ON ir.tconst = m.imdb_id
LEFT JOIN genres_agg g    ON g.tmdb_id = m.id
LEFT JOIN directors d     ON d.tmdb_id = m.id
LEFT JOIN actors_agg a    ON a.tmdb_id = m.id;

CREATE INDEX IF NOT EXISTS idx_uc_year    ON unified_catalog(year);
CREATE INDEX IF NOT EXISTS idx_uc_title   ON unified_catalog(title);
CREATE INDEX IF NOT EXISTS idx_uc_rt      ON unified_catalog(tmdb_rating);
CREATE INDEX IF NOT EXISTS idx_uc_imdb    ON unified_catalog(imdb_rating);
CREATE INDEX IF NOT EXISTS idx_uc_type    ON unified_catalog(type);
