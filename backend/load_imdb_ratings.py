import gzip, sqlite3, os, csv, sys

# База: можно передать 1-м аргументом или через env DB_PATH
DB_PATH = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DB_PATH", "imdb.db")
DB_PATH = os.path.abspath(DB_PATH)

# TSV: можно передать 2-м аргументом или через env IMDB_TSV
TSV_PATH = sys.argv[2] if len(sys.argv) > 2 else os.getenv("IMDB_TSV", "backend/title.ratings.tsv.gz")
TSV_PATH = os.path.abspath(TSV_PATH)

print(f"DB:  {DB_PATH}")
print(f"TSV: {TSV_PATH}")

con = sqlite3.connect(DB_PATH)
cur = con.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS imdb_ratings (
  tconst TEXT PRIMARY KEY,
  averageRating REAL,
  numVotes INTEGER
)""")
cur.execute("PRAGMA synchronous=OFF")
cur.execute("PRAGMA journal_mode=OFF")

count=0
with gzip.open(TSV_PATH, "rt", encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter="\t")
    batch=[]
    for row in reader:
        tconst = row["tconst"]
        rating = None if row["averageRating"]=="\\N" else float(row["averageRating"])
        votes  = 0    if row["numVotes"]=="\\N"       else int(row["numVotes"])
        batch.append((tconst, rating, votes))
        if len(batch) >= 5000:
            cur.executemany(
              "INSERT OR REPLACE INTO imdb_ratings(tconst,averageRating,numVotes) VALUES(?,?,?)",
              batch
            )
            con.commit(); count += len(batch); batch.clear()
    if batch:
        cur.executemany(
          "INSERT OR REPLACE INTO imdb_ratings(tconst,averageRating,numVotes) VALUES(?,?,?)",
          batch
        )
        con.commit(); count += len(batch)

con.close()
print(f"Loaded {count} rows into imdb_ratings")
