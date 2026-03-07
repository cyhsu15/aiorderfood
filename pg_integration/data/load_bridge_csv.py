import os
import pandas as pd
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
PG_ENV_PATH = REPO_ROOT / "pg_integration" / "config" / "pg.env"
CSV_PATH = REPO_ROOT / "pg_integration" / "data" / "bridge_canonical_to_oltp.csv"

load_dotenv(PG_ENV_PATH)

df = pd.read_csv(CSV_PATH)

def _need(key: str) -> str:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        raise RuntimeError(f"Missing env var: {key}")
    return v.strip()

def build_pg_conn_kwargs() -> dict:
    return {
        "host": _need("PG_HOST"),
        "port": int(_need("PG_PORT")),
        "dbname": _need("PG_DB"),
        "user": _need("PG_USER"),
        "password": _need("PG_PASSWORD"),
    }


with psycopg2.connect(**build_pg_conn_kwargs()) as pg:
        with pg.cursor() as cur:
            for _, r in df.iterrows():
                cur.execute("""
                    INSERT INTO integration.bridge_canonical_to_oltp
                    (canonical_dish_id, dish_price_id, note)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (r.canonical_dish_id, r.dish_price_id, r.note))
        pg.commit()

print(f"[OK] Loaded {len(df)} rows from {CSV_PATH} to integration.bridge_canonical_to_oltp")


