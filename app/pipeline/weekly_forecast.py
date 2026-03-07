"""Weekly forecast runner (DW history -> baseline + model -> PG integration.fact_forecast_daily).

Responsibilities:
- Read history from dw.vw_model_input_csv_compat via load_and_clean(config)
- Produce BOTH baseline and model forecasts (policy is downstream)
- Write all results directly into PostgreSQL integration.fact_forecast_daily

Origin rule:
- origin_date must be Monday
- horizon is Tue..Sun (6 days)

Usage example:
    python -m app.pipeline.weekly_forecast \
    --origin-date 2025-09-29 \
    --baseline-config ../EDA_v3/configs/config_001.yaml \
    --config ../EDA_v3/configs/config_003_lgbm_final.yaml \
    --model-path ../EDA_v3/runs/.../lgbm_final.txt
"""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

import pandas as pd
import yaml

import os
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from app.forecast_pg.repo import ForecastRow
from app.forecast_pg.service import ForecastService
from app.forecasting.data import load_and_clean
from app.forecasting.features import build_features_for_forecast, build_horizon_dates
from app.forecasting.model import load_model, predict_lgbm
from app.forecasting.postprocess import postprocess_yhat
from app.forecasting.train import train_model, predict

# Keep as CLI override-able for portability
DEFAULT_BASELINE_CONFIG_PATH = Path(r"..\EDA_v3\configs\config_001.yaml")



def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Weekly forecast runner: origin(Mon) -> predict Tue..Sun -> upsert dw.fact_forecast_daily"
    )
    p.add_argument("--origin-date", required=True, help="YYYY-MM-DD (must be Monday)")

    p.add_argument(
        "--baseline-config",
        default=str(DEFAULT_BASELINE_CONFIG_PATH),
        help="Path to baseline config yaml (must point to dw.vw_model_input_csv_compat for production)",
    )
    p.add_argument(
        "--baseline-version",
        default=None,
        help="model_version string for baseline rows. If omitted, use baseline config's experiment.model_version",
    )

    # Model is optional: if provided, we run model inference + write rows
    p.add_argument("--config", default=None, help="Path to model config yaml (feature set + schema)")
    p.add_argument("--model-path", default=None, help="Path to trained model artifact (e.g., lgbm_final.txt)")
    p.add_argument(
        "--model-version",
        default=None,
        help="model_version string for model rows. If omitted, use model config's experiment.model_version",
    )

    p.add_argument(
        "--run-id",
        default=None,
        help="Optional run id for idempotency. If omitted, a UUID will be generated.",
    )

    p.add_argument("--dry-run", action="store_true", help="Build + predict but do not write to DB")
    return p.parse_args()


def load_config(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def ensure_date(x) -> date:
    return pd.to_datetime(x).date()


def get_pg_session():
    """Create SQLAlchemy Session for PostgreSQL using pg_integration/config/pg.env"""
    from pathlib import Path
    
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    ENV_PATH = PROJECT_ROOT / "pg_integration" / "config" / "pg.env"

    if not ENV_PATH.exists():
        raise RuntimeError(f"pg.env not found: {ENV_PATH}")

    load_dotenv(ENV_PATH)
    
    host = os.getenv("PG_HOST")
    port = os.getenv("PG_PORT")
    db   = os.getenv("PG_DB")
    user = os.getenv("PG_USER")
    pwd  = os.getenv("PG_PASSWORD")

    if not all([host, port, db, user, pwd]):
        raise RuntimeError(
            "PG env vars missing. Need: PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD"
        )

    conn_str = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    engine = sa.create_engine(conn_str, pool_pre_ping=True, future=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def main() -> None:
    args = parse_args()

    origin_date = date.fromisoformat(args.origin_date)
    if origin_date.weekday() != 0:
        raise ValueError("origin_date must be a Monday")

    run_id = args.run_id or str(uuid4())

    # 1) Load history (single source of truth)
    cfg_base = load_config(args.baseline_config)
    df = load_and_clean(cfg_base)
    
    baseline_version = args.baseline_version or cfg_base.get("experiment", {}).get("model_version")
    if not baseline_version:
        raise ValueError("baseline_version missing: provide --baseline-version or set experiment.model_version in baseline config")

    data_cfg = cfg_base.get("data", {})
    date_col = data_cfg.get("date_col", "CloseWorkDate")
    id_col = data_cfg.get("id_col", "CanonicalDishId")
    target_col = data_cfg.get("target_col", "數量")

    df[date_col] = pd.to_datetime(df[date_col])

    # Baseline requires DayOfWeek
    df["DayOfWeek"] = df[date_col].dt.dayofweek.astype(int)

    # Candidate IDs come from the model-input domain (vw_model_input_csv_compat)
    candidate_ids = (
        df[id_col]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    candidate_ids.sort()

    horizon_dates = [ensure_date(d) for d in build_horizon_dates(origin_date)]

    # Past-only training data (strictly before origin)
    hist = df[df[date_col].dt.date < origin_date].copy()
    if hist.empty:
        raise RuntimeError("History is empty before origin_date; cannot forecast.")

    # ==========================================================
    # A) BASELINE (ALWAYS RUN)
    # ==========================================================
    # Baseline expects group cols like [CanonicalDishId, DayOfWeek]
    Xtr_b = hist[[id_col, "DayOfWeek", date_col]].copy()
    Xtr_b[id_col] = Xtr_b[id_col].astype(str)
    ytr_b = hist[target_col].copy()

    future_rows = []
    for cid in candidate_ids:
        for td in horizon_dates:
            future_rows.append(
                {
                    id_col: str(cid),
                    date_col: pd.to_datetime(td),
                    "DayOfWeek": pd.Timestamp(td).dayofweek,
                }
            )
    Xfu_b = pd.DataFrame(future_rows)

    # dummy valid set (API requires)
    Xva_dummy = Xtr_b.head(1).copy()
    yva_dummy = ytr_b.head(1).copy()

    tr_b = train_model(Xtr_b, ytr_b, Xva_dummy, yva_dummy, cfg_base)
    yhat_b = predict(tr_b.model, Xfu_b, cfg_base)

    yhat_b_pp = pd.Series(yhat_b).fillna(0.0).clip(lower=0.0).round().astype(int)

    baseline_rows: List[ForecastRow] = []
    for (cid, td, yh) in zip(Xfu_b[id_col].astype(str), pd.to_datetime(Xfu_b[date_col]).dt.date, yhat_b_pp):
        baseline_rows.append(
            ForecastRow(
                canonical_dish_id=int(str(cid)),
                forecast_origin_date=origin_date,
                target_date=ensure_date(td),
                yhat=Decimal(int(yh)),
                model_version=baseline_version,
                run_id=run_id,
            )
        )

    print("[DEBUG] run_id:", run_id)
    print("[DEBUG] baseline rows:", len(baseline_rows), "version:", baseline_version)

    # ==========================================================
    # B) MODEL (OPTIONAL)
    # ==========================================================
    model_rows: List[ForecastRow] = []
    if args.model_path:
        if not args.config:
            raise ValueError("--model-path provided; you must also provide --config")

        cfg_model = load_config(args.config)
        
        model_version = args.model_version or cfg_model.get("experiment", {}).get("model_version")
        if not model_version:
            raise ValueError("model_version missing: provide --model-version or set experiment.model_version in model config")
        
        model = load_model(args.model_path)

        X_forecast, feature_cols = build_features_for_forecast(
            df,
            origin_date=origin_date,
            config=cfg_model,
            candidate_ids=candidate_ids,
        )

        print("[DEBUG] X_forecast(model) rows:", len(X_forecast))
        print("[DEBUG] unique IDs(model):", X_forecast[id_col].astype(str).nunique())
        print("[DEBUG] unique target_date(model):", pd.to_datetime(X_forecast["target_date"]).dt.date.nunique())
        print(f"[DEBUG] feature_cols({len(feature_cols)}): {feature_cols}")

        yhat_m = predict_lgbm(model, X_forecast, feature_cols)
        yhat_m_pp = postprocess_yhat(yhat_m)

        X_forecast = X_forecast.copy()
        X_forecast["yhat"] = yhat_m_pp

        for r in X_forecast.itertuples(index=False):
            cid_raw = getattr(r, id_col)  # may be category/str
            cid = int(str(cid_raw))
            td = ensure_date(getattr(r, "target_date"))
            yh = int(getattr(r, "yhat"))

            model_rows.append(
                ForecastRow(
                    canonical_dish_id=cid,
                    forecast_origin_date=origin_date,
                    target_date=td,
                    yhat=Decimal(yh),
                    model_version=model_version,
                    run_id=run_id,
                )
            )

        print("[DEBUG] model rows:", len(model_rows), "version:", model_version)
    else:
        print("[DEBUG] --model-path not provided; skip model inference.")

    # ==========================================================
    # C) Combine rows + Upsert
    # ==========================================================
    rows: List[ForecastRow] = baseline_rows + model_rows

    unique_keys = {(x.run_id, x.canonical_dish_id, x.forecast_origin_date, x.target_date, x.model_version) for x in rows}
    print("[DEBUG] total rows to upsert:", len(rows))
    print("[DEBUG] unique keys:", len(unique_keys))

    if args.dry_run:
        print("[DRY-RUN] skip DB upsert")
        return

    svc = ForecastService()
    with get_pg_session() as db:
        n = svc.upsert_forecasts(db, rows)

    print(f"[OK] upserted {n} rows into integration.fact_forecast_daily")
    print(f"[OK] origin_date={origin_date}")
    print(f"[OK] baseline_version={args.baseline_version} rows={len(baseline_rows)}")
    if model_rows:
        print(f"[OK] model_version={args.model_version} rows={len(model_rows)}")


if __name__ == "__main__":
    main()
