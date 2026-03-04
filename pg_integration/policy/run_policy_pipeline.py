from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Sequence

import psycopg2


# =========================
# .env loader (very simple)
# =========================
def load_env_file(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f".env file not found: {path}")

    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def build_pg_conn_kwargs(args) -> dict:
    # 1️⃣ CLI override
    if args.pg_host:
        return {
            "host": args.pg_host,
            "port": int(args.pg_port),
            "dbname": args.pg_db,
            "user": args.pg_user,
            "password": args.pg_password,
        }

    # 2️⃣ Read from pg.env
    env_path = Path(args.pg_env).resolve()
    env = load_env_file(env_path)

    return {
        "host": env.get("PG_HOST", "localhost"),
        "port": int(env.get("PG_PORT", "5433")),
        "dbname": env.get("PG_DB"),
        "user": env.get("PG_USER"),
        "password": env.get("PG_PASSWORD"),
    }


# =========================
# SQL helpers
# =========================
def read_sql(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")
    return path.read_text(encoding="utf-8")


def split_sql(sql: str) -> Sequence[str]:
    parts = [p.strip() for p in sql.split(";")]
    return [p for p in parts if p]


# =========================
# Main logic
# =========================
def run_sanity(cur):
    cur.execute("SELECT COUNT(*) FROM integration.fact_forecast_daily;")
    n_forecast = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM integration.fact_daily_demand_actual;")
    n_actual = cur.fetchone()[0]

    if n_forecast == 0:
        raise RuntimeError("No forecast data found.")
    if n_actual == 0:
        raise RuntimeError("No actual data found.")

    print(f"[OK] forecast rows: {n_forecast}")
    print(f"[OK] actual rows:   {n_actual}")


def print_summary(cur):
    cur.execute("""
        SELECT chosen_model_version, COUNT(*)
        FROM integration.forecast_policy
        WHERE is_active = true
        GROUP BY chosen_model_version
        ORDER BY COUNT(*) DESC;
    """)
    rows = cur.fetchall()

    print("\n=== Active Policy Distribution ===")
    for mv, cnt in rows:
        print(f"{mv}: {cnt}")

    cur.execute("""
        SELECT canonical_dish_id, chosen_model_version, win_rate
        FROM integration.forecast_policy
        WHERE is_active = true
        ORDER BY win_rate DESC NULLS LAST
        LIMIT 15;
    """)
    rows = cur.fetchall()

    print("\n=== Top 15 by win_rate ===")
    for r in rows:
        print(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--pg-env",
        default="pg_integration/config/pg.env",
        help="Path to pg.env file",
    )
    ap.add_argument(
        "--apply-sql",
        default="pg_integration/policy/009_apply_policy.sql",
        help="Path to apply_policy.sql",
    )

    # optional CLI override
    ap.add_argument("--pg-host")
    ap.add_argument("--pg-port", default="5433")
    ap.add_argument("--pg-db")
    ap.add_argument("--pg-user")
    ap.add_argument("--pg-password")

    args = ap.parse_args()

    conn_kwargs = build_pg_conn_kwargs(args)
    apply_sql_path = Path(args.apply_sql).resolve()

    with psycopg2.connect(**conn_kwargs) as pg:
        with pg.cursor() as cur:

            run_sanity(cur)

            sql = read_sql(apply_sql_path)
            statements = split_sql(sql)

            for stmt in statements:
                cur.execute(stmt)

            pg.commit()
            print("[OK] Policy applied.")

            print_summary(cur)


if __name__ == "__main__":
    main()