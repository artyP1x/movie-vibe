import gzip, sqlite3, csv, os, pathlib, urllib.request
DB_PATH = pathlib.Path(__file__).with_name('imdb.db')
DATA_URL = 'https://datasets.imdbws.com/title.ratings.tsv.gz'

def ensure_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS title_ratings (
        tconst TEXT PRIMARY KEY,
        averageRating REAL,
        numVotes INTEGER
    )''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_tr_tconst ON title_ratings(tconst)')
    conn.commit()

def download():
    gz_path = pathlib.Path('title.ratings.tsv.gz')
    print('Downloading', DATA_URL)
    urllib.request.urlretrieve(DATA_URL, gz_path)
    return gz_path

def import_tsv(gz_path, conn):
    with gzip.open(gz_path, 'rt', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        rows = [(r['tconst'], float(r['averageRating']), int(r['numVotes'])) for r in reader]
    cur = conn.cursor()
    cur.execute('DELETE FROM title_ratings')
    cur.executemany('INSERT OR REPLACE INTO title_ratings (tconst, averageRating, numVotes) VALUES (?,?,?)', rows)
    conn.commit()
    print(f'Imported {len(rows):,} ratings rows')

if __name__ == '__main__':
    conn = sqlite3.connect(DB_PATH)
    ensure_db(conn)
    gz = download()
    import_tsv(gz, conn)
    print('Done. DB at', DB_PATH)
