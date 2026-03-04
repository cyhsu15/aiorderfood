#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ETL: stg.stg_menu -> dw.canonical_dish + dw.bridge_pos_food_to_canonical
- Parse rule aligns with menu_db.py:
    1) Only split if pattern: "xxx(yyy)" at the END
    2) If "(yyy)" contains any digit -> do NOT split
    3) price_label is NOT NULL (Version B): None -> "single"
- Backfill first_seen_date / last_seen_date from stg.stg_sales
- Idempotent: uses temp tables + MERGE (upsert)
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import pyodbc  # type: ignore
except ImportError as e:
    raise SystemExit(
        "Missing dependency: pyodbc. Install it in your venv.\n"
        "Example: pip install pyodbc"
    ) from e


# ---- Paths (match your repo style) ----
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # dw_mssql/
DEFAULT_ENV = PROJECT_ROOT / "config" / "dw.env"

# ---- Targets ----
STG_MENU_TABLE = "stg.stg_menu"
STG_SALES_TABLE = "stg.stg_sales"
CANONICAL_TABLE = "dw.canonical_dish"
BRIDGE_TABLE = "dw.bridge_pos_food_to_canonical"


# ------------------ env / connection (same style as load_excel_to_stg.py) ------------------
def load_env_file(env_path: Path) -> Dict[str, str]:
    if not env_path.exists():
        raise FileNotFoundError(f"Env file not found: {env_path}")

    env: Dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def pick_driver() -> str:
    drivers = pyodbc.drivers()
    if "ODBC Driver 18 for SQL Server" in drivers:
        return "ODBC Driver 18 for SQL Server"
    if "ODBC Driver 17 for SQL Server" in drivers:
        return "ODBC Driver 17 for SQL Server"

    raise RuntimeError(
        "Please install ODBC Driver 18 for SQL Server."
    )


def build_conn_str(env: Dict[str, str]) -> str:
    host = env.get("DW_MSSQL_HOST", "localhost")
    port = env.get("DW_MSSQL_PORT", "1433")
    db = env.get("DW_MSSQL_DB", "")
    user = env.get("DW_MSSQL_USER", "")
    pwd = env.get("DW_MSSQL_PASSWORD", "")

    driver = pick_driver()
    encrypt = env.get("DW_MSSQL_ENCRYPT", "no")
    trust_cert = env.get("DW_MSSQL_TRUST_SERVER_CERT", "yes")

    if not db or not user:
        raise ValueError("Missing required env vars: DW_MSSQL_DB / DW_MSSQL_USER")

    server = f"tcp:{host},{port}"
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={db};"
        f"UID={user};"
        f"PWD={pwd};"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate={trust_cert};"
        f"Connection Timeout=30;"
    )


# ------------------ parsing (align with menu_db.py, then force Version B) ------------------
_END_PAREN_RE = re.compile(r"^(.*)\(([^)]+)\)$")


def parse_food_name(food_name: Optional[str]) -> Tuple[Optional[str], str]:
    """
    Return (basename, price_label) with Version B guarantee: price_label NOT NULL.
    Rules:
      - Trim
      - If ending "(...)" AND (...) has no digit -> split into base + label
      - Else -> no split
      - price_label NULL -> "single"
    """
    if food_name is None:
        return None, "single"

    dish_name = str(food_name).strip()
    if dish_name == "":
        return None, "single"

    m = _END_PAREN_RE.match(dish_name)
    if not m:
        return dish_name, "single"

    base_name = m.group(1).strip()
    label = m.group(2).strip()

    # if label contains any digit -> do NOT split
    if any(ch.isdigit() for ch in label):
        return dish_name, "single"

    if base_name == "" or label == "":
        return dish_name, "single"

    return base_name, label


# ------------------ DB helpers ------------------
def chunked(lst: List[Tuple], size: int) -> List[List[Tuple]]:
    return [lst[i : i + size] for i in range(0, len(lst), size)]


def create_temp_tables(cur: "pyodbc.Cursor") -> None:
    cur.execute(
        """
        IF OBJECT_ID('tempdb..#canonical_src') IS NOT NULL DROP TABLE #canonical_src;
        CREATE TABLE #canonical_src (
            basename        NVARCHAR(200) NOT NULL,
            price_label     NVARCHAR(50)  NOT NULL,
            canonical_name  NVARCHAR(260) NULL
        );

        IF OBJECT_ID('tempdb..#bridge_src') IS NOT NULL DROP TABLE #bridge_src;
        CREATE TABLE #bridge_src (
            food_id                   VARCHAR(64)    NOT NULL,
            basename                  NVARCHAR(200)  NOT NULL,
            price_label               NVARCHAR(50)   NOT NULL,
            source_menu_food_name     NVARCHAR(200)  NULL,
            source_menu_category_raw  NVARCHAR(200)  NULL,
            source_menu_snapshot_date DATE          NULL
        );
        """
    )


def insert_many(cur, sql: str, rows: List[Tuple], batch_size: int, inputsizes=None) -> int:
    if not rows:
        return 0

    total = 0
    cur.fast_executemany = True

    if inputsizes is not None:
        cur.setinputsizes(inputsizes)

    for part in chunked(rows, batch_size):
        cur.executemany(sql, part)
        total += len(part)

    # 重要：避免後續 execute 也被 inputsizes 影響
    if inputsizes is not None:
        cur.setinputsizes([])

    return total


def extract_latest_menu_rows(cur: "pyodbc.Cursor") -> List[Tuple[str, Optional[str], Optional[str], Optional[str]]]:
    """
    For each food_id, pick the latest row by create_date (desc), fallback loaded_at.
    Return: (food_id, food_name, category_raw, snapshot_date 'YYYY-MM-DD' or None)
    """
    sql = f"""
    WITH ranked AS (
        SELECT
            food_id,
            food_name,
            category_raw,
            CAST(create_date AS date) AS snapshot_date,
            loaded_at,
            ROW_NUMBER() OVER (
                PARTITION BY food_id
                ORDER BY
                    CASE WHEN create_date IS NULL THEN 1 ELSE 0 END,
                    create_date DESC,
                    loaded_at DESC
            ) AS rn
        FROM {STG_MENU_TABLE}
        WHERE food_id IS NOT NULL
    )
    SELECT
        food_id,
        food_name,
        category_raw,
        CONVERT(varchar(10), snapshot_date, 23) AS snapshot_date
    FROM ranked
    WHERE rn = 1;
    """
    cur.execute(sql)
    return cur.fetchall()


def build_sources(
    menu_rows: List[Tuple[str, Optional[str], Optional[str], Optional[str]]]
) -> Tuple[List[Tuple[str, str, str]], List[Tuple]]:
    """
    canonical_rows: (basename, price_label, canonical_name)
    bridge_rows:
      (food_id, basename, price_label, source_menu_food_name, source_menu_category_raw, snapshot_date)
    """
    canonical_set = set()
    bridge_rows: List[Tuple] = []

    for food_id, food_name, category_raw, snapshot_date in menu_rows:
        basename, price_label = parse_food_name(food_name)
        if basename is None:
            # skip empty name -> cannot form canonical
            continue

        if price_label == "single":
            canonical_name = basename
        else:
            canonical_name = f"{basename}({price_label})"

        canonical_set.add((basename, price_label, canonical_name))

        bridge_rows.append(
            (
                food_id,
                basename,
                price_label,
                food_name,
                category_raw,
                snapshot_date,
            )
        )

    canonical_rows = sorted(list(canonical_set))
    return canonical_rows, bridge_rows


def merge_canonical(cur: "pyodbc.Cursor") -> None:
    cur.execute(
        f"""
        MERGE {CANONICAL_TABLE} AS tgt
        USING (
            SELECT DISTINCT basename, price_label, canonical_name
            FROM #canonical_src
        ) AS src
        ON  tgt.basename = src.basename
        AND tgt.price_label = src.price_label
        WHEN NOT MATCHED THEN
            INSERT (basename, price_label, canonical_name, is_active, created_at)
            VALUES (src.basename, src.price_label, src.canonical_name, 1, SYSDATETIME());
        """
    )


def merge_bridge(cur: "pyodbc.Cursor") -> None:
    cur.execute(
        f"""
        MERGE {BRIDGE_TABLE} AS tgt
        USING (
            SELECT
                bs.food_id,
                cd.canonical_dish_id,
                bs.source_menu_food_name,
                bs.source_menu_category_raw,
                bs.source_menu_snapshot_date
            FROM #bridge_src bs
            JOIN {CANONICAL_TABLE} cd
              ON cd.basename = bs.basename
             AND cd.price_label = bs.price_label
        ) AS src
        ON tgt.food_id = src.food_id
        WHEN MATCHED THEN
            UPDATE SET
                tgt.canonical_dish_id = src.canonical_dish_id,
                tgt.source_menu_food_name = src.source_menu_food_name,
                tgt.source_menu_category_raw = src.source_menu_category_raw,
                tgt.source_menu_snapshot_date = src.source_menu_snapshot_date,
                tgt.is_active = 1
        WHEN NOT MATCHED THEN
            INSERT (
                food_id, canonical_dish_id,
                source_menu_food_name, source_menu_category_raw, source_menu_snapshot_date,
                first_seen_date, last_seen_date,
                is_active, created_at
            )
            VALUES (
                src.food_id, src.canonical_dish_id,
                src.source_menu_food_name, src.source_menu_category_raw, src.source_menu_snapshot_date,
                NULL, NULL,
                1, SYSDATETIME()
            );
        """
    )


def backfill_seen_dates(cur: "pyodbc.Cursor") -> None:
    cur.execute(
        f"""
        WITH sales_span AS (
            SELECT
                food_id,
                MIN(close_work_date) AS first_seen_date,
                MAX(close_work_date) AS last_seen_date
            FROM {STG_SALES_TABLE}
            WHERE food_id IS NOT NULL
            GROUP BY food_id
        )
        UPDATE b
        SET
            b.first_seen_date = COALESCE(b.first_seen_date, ss.first_seen_date),
            b.last_seen_date  = COALESCE(b.last_seen_date,  ss.last_seen_date)
        FROM {BRIDGE_TABLE} b
        JOIN sales_span ss
          ON b.food_id = ss.food_id;
        """
    )


def report_unmapped_sales_food_ids(cur: "pyodbc.Cursor", limit: int = 200) -> List[str]:
    cur.execute(
        f"""
        SELECT DISTINCT TOP ({limit}) s.food_id
        FROM {STG_SALES_TABLE} s
        LEFT JOIN {BRIDGE_TABLE} b
          ON s.food_id = b.food_id
        WHERE s.food_id IS NOT NULL
          AND b.food_id IS NULL
        ORDER BY s.food_id;
        """
    )
    return [r[0] for r in cur.fetchall()]


def print_counts(cur: "pyodbc.Cursor") -> None:
    for t in [STG_MENU_TABLE, CANONICAL_TABLE, BRIDGE_TABLE]:
        cur.execute(f"SELECT COUNT(*) FROM {t};")
        n = cur.fetchone()[0]
        print(f"[INFO] {t} rows: {n:,}")


# ------------------ main ------------------
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="ETL: stg_menu -> dw.canonical_dish + dw.bridge_pos_food_to_canonical (Version B: price_label NOT NULL)"
    )
    parser.add_argument("--env", type=str, default=str(DEFAULT_ENV), help="Path to dw.env")
    parser.add_argument("--batch-size", type=int, default=2000, help="executemany batch size")
    parser.add_argument(
        "--only",
        choices=["canonical", "bridge", "all"],
        default="all",
        help="Run only a subset (canonical/bridge/all). Note: bridge requires canonical to exist.",
    )
    parser.add_argument("--skip-backfill", action="store_true", help="Skip backfill first/last seen dates from stg_sales")
    parser.add_argument("--skip-counts", action="store_true", help="Skip printing row counts after ETL")
    args = parser.parse_args(argv)

    env_path = Path(args.env)
    print(f"[INFO] Env: {env_path}")
    print(f"[INFO] Source: {STG_MENU_TABLE} -> Targets: {CANONICAL_TABLE}, {BRIDGE_TABLE}")
    print(f"[INFO] Mode: only={args.only}, batch_size={args.batch_size}, backfill={'no' if args.skip_backfill else 'yes'}")

    try:
        env = load_env_file(env_path)
        conn_str = build_conn_str(env)

        with pyodbc.connect(conn_str) as conn:            
            conn.autocommit = False
            cur = conn.cursor()

            print("[INFO] Extracting latest stg_menu rows per food_id ...")
            menu_rows = extract_latest_menu_rows(cur)
            print(f"[INFO] stg_menu distinct food_id rows: {len(menu_rows):,}")

            canonical_rows, bridge_rows = build_sources(menu_rows)
            print(f"[INFO] canonical candidates: {len(canonical_rows):,}")
            print(f"[INFO] bridge rows: {len(bridge_rows):,}")

            print("[INFO] Creating temp tables ...")
            create_temp_tables(cur)

            if args.only in ("canonical", "all"):
                print("[INFO] Loading #canonical_src ...")
                inserted = insert_many(
                    cur,
                    "INSERT INTO #canonical_src (basename, price_label, canonical_name) VALUES (?, ?, ?);",
                    canonical_rows,
                    batch_size=args.batch_size,
                    inputsizes=[
                        (pyodbc.SQL_WVARCHAR, 200),  # basename NVARCHAR(200)
                        (pyodbc.SQL_WVARCHAR, 50),   # price_label NVARCHAR(50)
                        (pyodbc.SQL_WVARCHAR, 260),  # canonical_name NVARCHAR(260)
                    ],
                )
                print(f"[OK] #canonical_src inserted: {inserted:,}")

                print(f"[INFO] MERGE -> {CANONICAL_TABLE} ...")
                merge_canonical(cur)
                print("[OK] canonical MERGE done.")

            if args.only in ("bridge", "all"):
                print("[INFO] Loading #bridge_src ...")
                inserted = insert_many(
                    cur,
                    """
                    INSERT INTO #bridge_src (
                        food_id, basename, price_label,
                        source_menu_food_name, source_menu_category_raw, source_menu_snapshot_date
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    bridge_rows,
                    batch_size=args.batch_size,
                    inputsizes=[
                        (pyodbc.SQL_VARCHAR, 64),    # food_id VARCHAR(64)
                        (pyodbc.SQL_WVARCHAR, 200),  # basename NVARCHAR(200)
                        (pyodbc.SQL_WVARCHAR, 50),   # price_label NVARCHAR(50)
                        (pyodbc.SQL_WVARCHAR, 200),  # source_menu_food_name NVARCHAR(200)
                        (pyodbc.SQL_WVARCHAR, 200),  # source_menu_category_raw NVARCHAR(200)
                        (pyodbc.SQL_TYPE_DATE, 0),   # DATE
                    ],
                )
                print(f"[OK] #bridge_src inserted: {inserted:,}")

                print(f"[INFO] MERGE -> {BRIDGE_TABLE} ...")
                merge_bridge(cur)
                print("[OK] bridge MERGE done.")

                if not args.skip_backfill:
                    print("[INFO] Backfill first/last seen dates from stg_sales ...")
                    backfill_seen_dates(cur)
                    print("[OK] backfill done.")

            conn.commit()
            print("[OK] Commit.")

            if not args.skip_counts:
                print_counts(cur)

            unmapped = report_unmapped_sales_food_ids(cur, limit=200)
            if unmapped:
                print("[WARN] Found food_id in sales but not in bridge (showing up to 200):")
                for x in unmapped:
                    print("  -", x)
                print("[HINT] Usually means stg_menu lacks those food_id, or food_name is NULL/empty.")
            else:
                print("[INFO] All sales food_id are mapped in bridge. ✅")

        return 0

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())