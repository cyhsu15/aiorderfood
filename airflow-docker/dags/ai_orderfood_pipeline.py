"""
DAG: ai_orderfood_weekly_pipeline
==================================
Orchestrates the AIOrderFood production data pipeline on a weekly schedule.

Pipeline stages (see PLAN.md for full design rationale):

  sync_dw_data
       │
       ▼
  generate_weekly_forecast   load_backtest_predictions   (parallel)
       │                              │
       └──────────────┬───────────────┘
                      ▼
              write_forecast_policy
                      │
                      ▼
              validate_serving_view   (data quality check)

Offline ML (EDA_v3) is treated as an external input.
The backtest CSV must exist before running the DAG.

Environment / Config
---------------------
All paths and env-file locations are driven by Airflow Variables or the
constants block below.  Adjust the constants to match your local layout.

Required Airflow Variables (set via UI or CLI):
  - ORIGIN_DATE          : ISO date string, e.g. "2026-03-30" (must be Monday)
                           If absent, the DAG auto-computes the most-recent Monday.
  - BACKTEST_CSV_PATH    : (optional) override path to backtest_predictions.csv

Usage (local / standalone Airflow):
  airflow dags trigger ai_orderfood_weekly_pipeline \
      --conf '{"origin_date": "2026-03-30"}'
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator

# ---------------------------------------------------------------------------
# Constants — adjust these to your local repo layout
# ---------------------------------------------------------------------------
# Root of the AIOrderFood-main project (where this dags/ folder lives)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Paths relative to PROJECT_ROOT
WEEKLY_FORECAST_MODULE = "app.pipeline.weekly_forecast"   # python -m <this>
LOAD_BACKTEST_SCRIPT   = PROJECT_ROOT / "pg_integration" / "offline_policy" / "04_load_backtest_predictions_csv.py"
WRITE_POLICY_SQL       = PROJECT_ROOT / "pg_integration" / "offline_policy" / "08_write_policy.sql"
DW_LOAD_EXCEL_SCRIPT   = PROJECT_ROOT / "dw_mssql" / "etl" / "02_load_excel_to_stg.py"
DW_ETL_MENU_SCRIPT     = PROJECT_ROOT / "dw_mssql" / "etl" / "03_etl_menu_to_dw.py"

# EDA_v3 outputs (external inputs — not orchestrated, must exist before DAG runs)
EDA_ROOT           = PROJECT_ROOT.parent / "EDA_v3"
DEFAULT_BACKTEST_CSV = (
    EDA_ROOT / "runs"
    / "exp_003_lgbm_tweedie_p15_lag7_14_21_28_finalfeat__20260305_223540"
    / "backtest_predictions.csv"
)

# Model artifacts from EDA_v3
BASELINE_CONFIG = EDA_ROOT / "configs" / "config_001.yaml"
MODEL_CONFIG    = EDA_ROOT / "configs" / "config_003_lgbm_final.yaml"
MODEL_PATH      = (
    EDA_ROOT / "runs"
    / "exp_003_lgbm_tweedie_p15_lag7_14_21_28_finalfeat__20260305_223540"
    / "lgbm_final.txt"
)

# PostgreSQL env file (used by write_policy task)
PG_ENV_FILE = PROJECT_ROOT / "pg_integration" / "config" / "pg_backtest.env"

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _most_recent_monday(ref: date | None = None) -> date:
    """Return the most-recent Monday on or before ref (default: today)."""
    d = ref or date.today()
    return d - timedelta(days=d.weekday())


def _run_subprocess(cmd: list[str], cwd: Path | None = None) -> None:
    """Run a command, stream stdout/stderr to Airflow task logs, raise on failure."""
    cwd = cwd or PROJECT_ROOT
    log.info("Running: %s  (cwd=%s)", " ".join(str(c) for c in cmd), cwd)
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=False,   # let stdout/stderr flow directly to Airflow logs
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Subprocess failed (exit {result.returncode}): {' '.join(str(c) for c in cmd)}"
        )


def _load_pg_env() -> None:
    """Load pg_backtest.env into os.environ (simple key=value parser)."""
    if not PG_ENV_FILE.exists():
        raise FileNotFoundError(f"PG env file not found: {PG_ENV_FILE}")
    for line in PG_ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _get_origin_date(**context) -> str:
    """
    Resolve origin_date from (in priority order):
      1. DAG run conf  {"origin_date": "YYYY-MM-DD"}
      2. Airflow Variable ORIGIN_DATE
      3. Most-recent Monday relative to logical_date
    Returns ISO string. Validates it is a Monday.
    """
    conf = context.get("dag_run") and context["dag_run"].conf or {}
    raw = (
        conf.get("origin_date")
        or Variable.get("ORIGIN_DATE", default_var=None)
    )
    if raw:
        d = date.fromisoformat(raw)
    else:
        logical_date = context["logical_date"].date()
        d = _most_recent_monday(logical_date)
        log.info("origin_date not provided; auto-resolved to %s", d)

    if d.weekday() != 0:
        raise ValueError(f"origin_date must be a Monday, got {d} ({d.strftime('%A')})")

    log.info("origin_date = %s", d)
    return str(d)


# ---------------------------------------------------------------------------
# Task functions
# ---------------------------------------------------------------------------

def task_sync_dw_data(**context) -> None:
    """
    Stage 1: Sync raw data into MSSQL DW.
    Runs existing ETL scripts in sequence:
      02_load_excel_to_stg.py   — Excel → stg.stg_sales / stg.stg_menu
      03_etl_menu_to_dw.py      — stg → dw dim/fact tables

    NOTE: 06_load_fact_daily_demand_actual.sql is a SQL script run on MSSQL.
    If you have a wrapper script for it, add it here.  Otherwise, run it
    manually or via a SqlOperator against your MSSQL connection.
    """
    log.info("=== sync_dw_data: loading Excel into MSSQL staging ===")

    for script in [DW_LOAD_EXCEL_SCRIPT, DW_ETL_MENU_SCRIPT]:
        if not script.exists():
            raise FileNotFoundError(f"DW ETL script not found: {script}")
        _run_subprocess([sys.executable, str(script)], cwd=PROJECT_ROOT)

    log.info("=== sync_dw_data: complete ===")


def task_generate_weekly_forecast(**context) -> None:
    """
    Stage 2: Generate production forecasts (baseline + LightGBM).
    Calls weekly_forecast.py as a subprocess to keep its sys.path clean.
    Writes to integration.fact_forecast_daily (PostgreSQL).
    Idempotent: uses ON CONFLICT DO UPDATE keyed on (run_id, dish, origin, target, version).
    """
    origin_date = _get_origin_date(**context)

    if not MODEL_PATH.exists():
        log.warning(
            "Model artifact not found at %s — running baseline-only forecast.", MODEL_PATH
        )
        model_args: list[str] = []
    else:
        model_args = [
            "--config", str(MODEL_CONFIG),
            "--model-path", str(MODEL_PATH),
        ]

    cmd = [
        sys.executable, "-m", WEEKLY_FORECAST_MODULE,
        "--origin-date", origin_date,
        "--baseline-config", str(BASELINE_CONFIG),
        *model_args,
    ]

    log.info("=== generate_weekly_forecast: origin_date=%s ===", origin_date)
    _run_subprocess(cmd, cwd=PROJECT_ROOT)
    log.info("=== generate_weekly_forecast: complete ===")


def task_load_backtest_predictions(**context) -> None:
    """
    Stage 3: Load EDA_v3 backtest CSV into integration.fact_backtest_forecast_daily.
    Runs in parallel with generate_weekly_forecast (independent tables).
    Idempotent: uses ON CONFLICT DO NOTHING keyed on primary key.
    """
    # Allow runtime override via DAG conf or Airflow Variable
    conf = context.get("dag_run") and context["dag_run"].conf or {}
    csv_path = Path(
        conf.get("backtest_csv_path")
        or Variable.get("BACKTEST_CSV_PATH", default_var=str(DEFAULT_BACKTEST_CSV))
    )

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Backtest CSV not found: {csv_path}\n"
            "This is an external input produced by EDA_v3. "
            "Run your offline experiment first and update BACKTEST_CSV_PATH."
        )

    log.info("=== load_backtest_predictions: csv=%s ===", csv_path)

    # Pass path via env var (matches how the script resolves it)
    env = {**os.environ, "BACKTEST_CSV_PATH": str(csv_path)}
    result = subprocess.run(
        [sys.executable, str(LOAD_BACKTEST_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        env=env,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"load_backtest_predictions failed (exit {result.returncode})")

    log.info("=== load_backtest_predictions: complete ===")


def task_write_forecast_policy(**context) -> None:
    """
    Stage 4: Compute per-dish MAE across model versions and upsert best policy.
    Reads from integration.fact_backtest_forecast_daily.
    Writes to integration.forecast_policy2.
    Idempotent: uses ON CONFLICT DO UPDATE.

    Both upstream tasks (generate_weekly_forecast, load_backtest_predictions)
    must complete before this runs.
    """
    import psycopg2
    from dotenv import load_dotenv

    _load_pg_env()
    load_dotenv(PG_ENV_FILE)  # belt-and-suspenders

    sql = WRITE_POLICY_SQL.read_text(encoding="utf-8")

    log.info("=== write_forecast_policy: connecting to PostgreSQL ===")
    conn = psycopg2.connect(
        host=os.environ["PG_HOST"],
        port=int(os.environ.get("PG_PORT", "5433")),
        dbname=os.environ["PG_DB"],
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
    )
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            log.info("Rows affected: %s", cur.rowcount)
        conn.commit()
        log.info("=== write_forecast_policy: policy upserted ===")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def task_validate_serving_view(**context) -> None:
    """
    Stage 5: Data quality gate — verify the LLM serving view has rows for
    the current origin_date before declaring the pipeline successful.

    Checks:
      1. vw_forecast_for_llm_serving has at least 1 row for origin_date
      2. forecast_policy2 has at least 1 active policy
    Raises on failure so Airflow marks the DAG run as failed.
    """
    import psycopg2
    from dotenv import load_dotenv

    _load_pg_env()
    load_dotenv(PG_ENV_FILE)

    origin_date = _get_origin_date(**context)

    conn = psycopg2.connect(
        host=os.environ["PG_HOST"],
        port=int(os.environ.get("PG_PORT", "5433")),
        dbname=os.environ["PG_DB"],
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
    )
    try:
        with conn.cursor() as cur:
            # Check 1: active policies exist
            cur.execute(
                "SELECT COUNT(*) FROM integration.forecast_policy2 WHERE is_active = TRUE"
            )
            policy_count = cur.fetchone()[0]
            log.info("Active policies: %d", policy_count)
            if policy_count == 0:
                raise AssertionError("No active policies in forecast_policy2. write_forecast_policy may have failed.")

            # Check 2: serving view has rows for this origin_date
            cur.execute(
                """
                SELECT COUNT(*)
                FROM integration.vw_forecast_for_llm_serving
                WHERE forecast_origin_date = %s
                """,
                (origin_date,),
            )
            serving_count = cur.fetchone()[0]
            log.info("Serving view rows for origin_date=%s: %d", origin_date, serving_count)
            if serving_count == 0:
                raise AssertionError(
                    f"vw_forecast_for_llm_serving has 0 rows for origin_date={origin_date}. "
                    "Check that forecast + policy are aligned (model_version must match)."
                )

        log.info("=== validate_serving_view: all checks passed ===")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Pipeline Health Validation
# ---------------------------------------------------------------------------

# Thresholds — adjust to match your production expectations
_MIN_FORECAST_DISHES    = 15     # minimum distinct dishes expected in a forecast run
_EXPECTED_HORIZON_DAYS  = 6    # number of future dates each dish should have
_HORIZON_COMPLETENESS_THRESHOLD = 0.80   # at least 80% of dishes must have full horizon
_MIN_BACKTEST_DISHES    = 15     # minimum distinct dishes in backtest table
_MIN_BACKTEST_MODEL_VERSIONS = 2  # backtest must include at least 2 model versions
                                   # (baseline + at least one ML model)
_MAX_BASELINE_ONLY_RATIO = 0.90   # fail if >90% of policies chose the baseline model
_MIN_SERVING_COVERAGE   = 0.70   # at least 70% of active bridge dishes must appear in serving view
_MAX_ZERO_YHAT_RATIO    = 0.10   # at most 10% of serving rows may have yhat == 0


def task_validate_pipeline_health(**context) -> None:
    """
    Stage 6: Comprehensive pipeline health gate.

    Validates four layers of the pipeline and raises AssertionError (→ DAG fail)
    on any anomaly.  On success, prints a human-readable summary to the task log.

    Layer checks
    ────────────
    FORECAST  F1  Row count ≥ _MIN_FORECAST_DISHES for this run's origin_date
              F2  Horizon completeness: fraction of dishes that have the full
                  _EXPECTED_HORIZON_DAYS of predictions
              F3  yhat zero-rate across all forecast rows ≤ _MAX_ZERO_YHAT_RATIO

    BACKTEST  B1  At least _MIN_BACKTEST_DISHES dishes present
              B2  At least _MIN_BACKTEST_MODEL_VERSIONS distinct model_version values
                  (ensures baseline vs. ML models both loaded)

    POLICY    P1  At least 1 active policy row exists
              P2  Baseline-only ratio ≤ _MAX_BASELINE_ONLY_RATIO
                  (guards against ML model being silently ignored)
              P3  Policy covers all dishes that exist in the forecast table

    SERVING   S1  Row count > 0 for this origin_date
              S2  Dish coverage ≥ _MIN_SERVING_COVERAGE
                  (active bridge dishes that appear in the serving view)
              S3  Zero-yhat rate in serving view ≤ _MAX_ZERO_YHAT_RATIO
    """
    import psycopg2
    from dotenv import load_dotenv

    _load_pg_env()
    load_dotenv(PG_ENV_FILE)

    origin_date = _get_origin_date(**context)

    conn = psycopg2.connect(
        host=os.environ["PG_HOST"],
        port=int(os.environ.get("PG_PORT", "5433")),
        dbname=os.environ["PG_DB"],
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
    )

    failures: list[str] = []
    summary_lines: list[str] = []

    def _q(cur, sql: str, params=None):
        cur.execute(sql, params)
        return cur.fetchone()

    try:
        with conn.cursor() as cur:

            # ── FORECAST LAYER ────────────────────────────────────────────────

            # F1: distinct dishes in this origin_date's forecast
            row = _q(cur, """
                SELECT COUNT(DISTINCT canonical_dish_id)
                FROM integration.fact_forecast_daily
                WHERE forecast_origin_date = %s
            """, (origin_date,))
            forecast_dish_count = row[0]
            summary_lines.append(f"[FORECAST] F1  distinct dishes for {origin_date}: {forecast_dish_count}")
            if forecast_dish_count < _MIN_FORECAST_DISHES:
                failures.append(
                    f"F1 FAIL: forecast has only {forecast_dish_count} dishes "
                    f"(min={_MIN_FORECAST_DISHES}) for origin_date={origin_date}. "
                    "weekly_forecast may have silently produced no output."
                )

            # F2: horizon completeness
            # For each dish, count how many distinct target_dates exist; flag
            # dishes that are missing dates.
            row = _q(cur, """
                SELECT
                    COUNT(*) FILTER (WHERE horizon_count >= %s)::float
                    / NULLIF(COUNT(*), 0)
                FROM (
                    SELECT canonical_dish_id, COUNT(DISTINCT target_date) AS horizon_count
                    FROM integration.fact_forecast_daily
                    WHERE forecast_origin_date = %s
                    GROUP BY canonical_dish_id
                ) sub
            """, (_EXPECTED_HORIZON_DAYS, origin_date))
            horizon_completeness = row[0] or 0.0
            summary_lines.append(
                f"[FORECAST] F2  horizon completeness (≥{_EXPECTED_HORIZON_DAYS}d): "
                f"{horizon_completeness:.1%}"
            )
            if horizon_completeness < _HORIZON_COMPLETENESS_THRESHOLD:
                failures.append(
                    f"F2 FAIL: only {horizon_completeness:.1%} of dishes have "
                    f"a full {_EXPECTED_HORIZON_DAYS}-day horizon "
                    f"(threshold={_HORIZON_COMPLETENESS_THRESHOLD:.0%}). "
                    "Some dishes may have missing prediction dates."
                )

            # F3: zero-yhat rate across all versions for this origin_date
            row = _q(cur, """
                SELECT
                    COUNT(*) FILTER (WHERE yhat = 0)::float
                    / NULLIF(COUNT(*), 0)
                FROM integration.fact_forecast_daily
                WHERE forecast_origin_date = %s
            """, (origin_date,))
            forecast_zero_yhat = row[0] or 0.0
            summary_lines.append(f"[FORECAST] F3  zero-yhat rate: {forecast_zero_yhat:.1%}")
            if forecast_zero_yhat > _MAX_ZERO_YHAT_RATIO:
                failures.append(
                    f"F3 FAIL: {forecast_zero_yhat:.1%} of forecast rows have yhat=0 "
                    f"(max={_MAX_ZERO_YHAT_RATIO:.0%}). "
                    "Model may have degenerated or data is missing."
                )

            # ── BACKTEST LAYER ────────────────────────────────────────────────

            # B1: distinct dishes in backtest
            row = _q(cur, """
                SELECT COUNT(DISTINCT canonical_dish_id)
                FROM integration.fact_backtest_forecast_daily
            """)
            backtest_dish_count = row[0]
            summary_lines.append(f"[BACKTEST] B1  distinct dishes: {backtest_dish_count}")
            if backtest_dish_count < _MIN_BACKTEST_DISHES:
                failures.append(
                    f"B1 FAIL: backtest has only {backtest_dish_count} dishes "
                    f"(min={_MIN_BACKTEST_DISHES}). "
                    "load_backtest_predictions may have failed or CSV is empty."
                )

            # B2: distinct model versions in backtest
            row = _q(cur, """
                SELECT COUNT(DISTINCT model_version)
                FROM integration.fact_backtest_forecast_daily
            """)
            backtest_model_versions = row[0]
            # Fetch the actual version names for the log
            cur.execute("""
                SELECT DISTINCT model_version
                FROM integration.fact_backtest_forecast_daily
                ORDER BY 1
            """)
            backtest_version_list = [r[0] for r in cur.fetchall()]
            summary_lines.append(
                f"[BACKTEST] B2  model versions ({backtest_model_versions}): "
                f"{backtest_version_list}"
            )
            if backtest_model_versions < _MIN_BACKTEST_MODEL_VERSIONS:
                failures.append(
                    f"B2 FAIL: backtest contains only {backtest_model_versions} model version(s) "
                    f"(min={_MIN_BACKTEST_MODEL_VERSIONS}). "
                    "Expected baseline + at least one ML model. "
                    "Check that the backtest CSV includes multi-model results."
                )

            # ── POLICY LAYER ──────────────────────────────────────────────────

            # P1: any active policy exists
            row = _q(cur, """
                SELECT COUNT(*)
                FROM integration.forecast_policy2
                WHERE is_active = TRUE
            """)
            active_policy_count = row[0]
            summary_lines.append(f"[POLICY]   P1  active policy rows: {active_policy_count}")
            if active_policy_count == 0:
                failures.append(
                    "P1 FAIL: forecast_policy2 has 0 active rows. "
                    "write_forecast_policy task must have failed silently."
                )

            # P2: baseline-only ratio — how many policies chose a baseline model
            # Heuristic: model_version containing 'baseline' (case-insensitive)
            row = _q(cur, """
                SELECT
                    COUNT(*) FILTER (
                        WHERE LOWER(chosen_model_version) LIKE '%baseline%'
                    )::float
                    / NULLIF(COUNT(*), 0)
                FROM integration.forecast_policy2
                WHERE is_active = TRUE
            """)
            baseline_ratio = row[0] or 0.0
            # Also get the distribution for the summary log
            cur.execute("""
                SELECT chosen_model_version, COUNT(*) AS cnt
                FROM integration.forecast_policy2
                WHERE is_active = TRUE
                GROUP BY chosen_model_version
                ORDER BY cnt DESC
            """)
            policy_dist = {r[0]: r[1] for r in cur.fetchall()}
            summary_lines.append(
                f"[POLICY]   P2  baseline ratio: {baseline_ratio:.1%}  "
                f"distribution: {policy_dist}"
            )
            if baseline_ratio > _MAX_BASELINE_ONLY_RATIO:
                failures.append(
                    f"P2 FAIL: {baseline_ratio:.1%} of active policies chose a baseline model "
                    f"(max={_MAX_BASELINE_ONLY_RATIO:.0%}). "
                    "ML model may not be influencing any dishes — "
                    "check backtest coverage and model_version alignment."
                )

            # P3: policy coverage vs forecast dishes
            # Every dish that appeared in the forecast should have a policy.
            row = _q(cur, """
                SELECT
                    COUNT(DISTINCT f.canonical_dish_id) FILTER (
                        WHERE p.canonical_dish_id IS NOT NULL
                    )::float
                    / NULLIF(COUNT(DISTINCT f.canonical_dish_id), 0)
                FROM (
                    SELECT DISTINCT canonical_dish_id
                    FROM integration.fact_forecast_daily
                    WHERE forecast_origin_date = %s
                ) f
                LEFT JOIN integration.forecast_policy2 p
                  ON p.canonical_dish_id = f.canonical_dish_id
                 AND p.is_active = TRUE
            """, (origin_date,))
            policy_coverage = row[0] or 0.0
            summary_lines.append(f"[POLICY]   P3  forecast→policy coverage: {policy_coverage:.1%}")
            if policy_coverage < 1.0:
                # Soft warning only — some dishes may legitimately lack backtest data
                summary_lines.append(
                    f"[POLICY]   P3  WARNING: {1-policy_coverage:.1%} of forecast dishes "
                    "have no active policy — they will be excluded from the serving view."
                )

            # ── SERVING LAYER ─────────────────────────────────────────────────

            # S1: row count in serving view for this origin_date
            row = _q(cur, """
                SELECT COUNT(*)
                FROM integration.vw_forecast_for_llm_serving
                WHERE forecast_origin_date = %s
            """, (origin_date,))
            serving_count = row[0]
            summary_lines.append(f"[SERVING]  S1  serving view rows for {origin_date}: {serving_count}")
            if serving_count == 0:
                failures.append(
                    f"S1 FAIL: vw_forecast_for_llm_serving has 0 rows for "
                    f"origin_date={origin_date}. "
                    "Likely cause: model_version mismatch between forecast and policy, "
                    "or bridge_canonical_to_oltp has no active mappings."
                )

            # S2: dish coverage — fraction of active-bridge dishes visible in serving
            row = _q(cur, """
                SELECT
                    COUNT(DISTINCT s.canonical_dish_id)::float
                    / NULLIF(COUNT(DISTINCT b.canonical_dish_id), 0)
                FROM (
                    SELECT DISTINCT canonical_dish_id
                    FROM integration.bridge_canonical_to_oltp
                    WHERE is_active = TRUE
                ) b
                LEFT JOIN (
                    SELECT DISTINCT canonical_dish_id
                    FROM integration.vw_forecast_for_llm_serving
                    WHERE forecast_origin_date = %s
                ) s ON s.canonical_dish_id = b.canonical_dish_id
            """, (origin_date,))
            serving_coverage = row[0] or 0.0
            summary_lines.append(f"[SERVING]  S2  dish coverage (bridge→serving): {serving_coverage:.1%}")
            if serving_coverage < _MIN_SERVING_COVERAGE:
                failures.append(
                    f"S2 FAIL: serving view covers only {serving_coverage:.1%} of active bridge dishes "
                    f"(min={_MIN_SERVING_COVERAGE:.0%}). "
                    "Many dishes that the LLM could recommend are missing from the serving view."
                )

            # S3: zero-yhat rate in serving view
            row = _q(cur, """
                SELECT
                    COUNT(*) FILTER (WHERE yhat = 0)::float
                    / NULLIF(COUNT(*), 0)
                FROM integration.vw_forecast_for_llm_serving
                WHERE forecast_origin_date = %s
            """, (origin_date,))
            serving_zero_yhat = row[0] or 0.0
            summary_lines.append(f"[SERVING]  S3  zero-yhat rate in serving: {serving_zero_yhat:.1%}")
            if serving_zero_yhat > _MAX_ZERO_YHAT_RATIO:
                failures.append(
                    f"S3 FAIL: {serving_zero_yhat:.1%} of serving rows have yhat=0 "
                    f"(max={_MAX_ZERO_YHAT_RATIO:.0%}). "
                    "The LLM will receive meaningless demand signals for those dishes."
                )

    finally:
        conn.close()

    # ── Emit summary ──────────────────────────────────────────────────────────
    log.info("=== pipeline health summary (origin_date=%s) ===", origin_date)
    for line in summary_lines:
        log.info("  %s", line)

    if failures:
        log.error("=== pipeline health FAILED — %d check(s) did not pass ===", len(failures))
        for msg in failures:
            log.error("  ✗ %s", msg)
        raise AssertionError(
            f"Pipeline health check failed ({len(failures)} issue(s)):\n"
            + "\n".join(f"  • {m}" for m in failures)
        )

    log.info("=== pipeline health OK — all checks passed ===")


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

default_args = {
    "owner": "data-engineering",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,   # set to True and configure email in Airflow if desired
}

with DAG(
    dag_id="ai_orderfood_weekly_pipeline",
    description="AIOrderFood production data pipeline: DW sync → forecast → policy → serving view",
    schedule="0 6 * * 1",          # Every Monday at 06:00
    start_date=datetime(2026, 3, 30),
    catchup=False,                  # Don't backfill historical runs
    default_args=default_args,
    tags=["production", "forecast", "aiorderfood"],
) as dag:

    sync_dw = PythonOperator(
        task_id="sync_dw_data",
        python_callable=task_sync_dw_data,
    )

    gen_forecast = PythonOperator(
        task_id="generate_weekly_forecast",
        python_callable=task_generate_weekly_forecast,
    )

    load_backtest = PythonOperator(
        task_id="load_backtest_predictions",
        python_callable=task_load_backtest_predictions,
    )

    write_policy = PythonOperator(
        task_id="write_forecast_policy",
        python_callable=task_write_forecast_policy,
    )

    validate = PythonOperator(
        task_id="validate_serving_view",
        python_callable=task_validate_serving_view,
    )

    health = PythonOperator(
        task_id="validate_pipeline_health",
        python_callable=task_validate_pipeline_health,
    )

    # Dependency graph:
    #   sync_dw >> [gen_forecast, load_backtest] >> write_policy >> validate >> health
    sync_dw >> [gen_forecast, load_backtest]
    [gen_forecast, load_backtest] >> write_policy
    write_policy >> validate >> health
