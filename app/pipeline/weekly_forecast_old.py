from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import pandas as pd
import yaml
from sqlalchemy import text
from dotenv import load_dotenv
load_dotenv()

from app.db import SessionLocal
from app.forecast.repo import ForecastRow
from app.forecast.service import ForecastService
from app.forecasting.data import load_and_clean
from app.forecasting.features import build_features_for_forecast, build_horizon_dates
from app.forecasting.model import load_model, predict_lgbm
from app.forecasting.postprocess import postprocess_yhat
from app.forecasting.train import train_model, predict


"""
Usage:
  - baseline always runs + writes
  - model runs ONLY if policy_level=2 exists

Example:
python -m app.pipeline.weekly_forecast `
--config ../EDA_v3/configs/config_003_lgbm_final.yaml `
--origin-date 2025-09-29 `
--model-path ../EDA_v3/runs/exp_003_lgbm_tweedie_p15_lag7_14_21_28_finalfeat__20260126_235737/lgbm_final.txt `
--model-version exp_003_lgbm_tweedie_p15_lag7_14_21_28_finalfeat__20260126_235737 `
--dry-run
"""

BASELINE_CONFIG_PATH = Path(r"..\EDA_v3\configs\backtest_baseline.yaml")
BASELINE_VERSION = "baseline_k4_median_foodid_dow_v1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Weekly forecast production runner: origin(Mon) -> predict Tue..Sun -> upsert DB"
    )
    p.add_argument("--origin-date", required=True, help="YYYY-MM-DD (Monday)")
    
    # Model is OPTIONAL (only required if policy_level=2 exists)
    p.add_argument("--config", default=None, help="Path to LGBM config yaml")
    p.add_argument("--model-path", default=None, help="Path to lgbm_final.txt")
    p.add_argument("--model-version", default=None, help="Model version to write into DB")
    
    p.add_argument("--dry-run", action="store_true", help="Build + predict but do not write to DB")
    
    return p.parse_args()


def load_config(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def ensure_date(x: pd.Timestamp |date) -> date:
    return pd.to_datetime(x).date()


def fetch_policy_map(db) -> dict[str, int]:
    rows = db.execute(text("SELECT food_id, policy_level FROM food_forecast_policy")).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}


def main() -> None:
    args = parse_args()
    cfg_base = load_config(BASELINE_CONFIG_PATH) # Baseline config (always used)
    cfg_model = load_config(args.config)         # LGBM config (used only if policy_level=2 exists)
    origin_date = date.fromisoformat(args.origin_date)
    
    if origin_date.weekday() != 0:
        raise ValueError("origin_date must be a Monday")
    
    # 1) Decide candidate FoodIDs
    target_food_ids = ['2020F004','2020F002','2020F003','2020F010','2020F008',
            '2020F009','B2020006','B2020007','B2020005','2020D001',
            '2020D002','B2020001','2020I006','2020I005','2020I004']
    
    # 2) Load history CSV (from baseline config data.path)
    #    (model config should point to the same path; but we use baseline cfg as canonical here)
    data_cfg = cfg_base.get("data", {})

    date_col = data_cfg.get("date_col", "CloseWorkDate")
    id_col = data_cfg.get("id_col", "FoodID")
    target_col = data_cfg.get("target_col", "數量")
    
    df = load_and_clean(cfg_base)
    
    df[date_col] = pd.to_datetime(df[date_col])
    
    # Add baseline-required feature column
    df["DayOfWeek"] = df[date_col].dt.dayofweek.astype(int)
    
    # 3) Read policy from DB, decide which FoodIDs run model
    with SessionLocal() as db:
        policy_map = fetch_policy_map(db)
        
    food_ids_all = [str(x) for x in target_food_ids]
    food_ids_model = [fid for fid in food_ids_all if policy_map.get(fid, 1) == 2]

    counts = {lvl: sum(1 for fid in food_ids_all if policy_map.get(fid, 1) == lvl) for lvl in [0, 1, 2]}
    print("[DEBUG] policy_level counts:", counts)
    print("[DEBUG] policy_level=2 FoodIDs:", food_ids_model)
    
    # ==========================================================
    # A) BASELINE (ALWAYS RUN): train_model/predict using cfg_base
    # ==========================================================
    horizon_dates = build_horizon_dates(origin_date)

    # Past-only training data (strictly before origin)
    hist = df[df[date_col].dt.date < origin_date].copy()
    if hist.empty:
        raise RuntimeError("History is empty before origin_date; baseline cannot be trained.")
    
    # Build X_train for baseline: must include group_cols + date_col
    # group_cols for your baseline config are expected like [FoodID, DayOfWeek]
    Xtr_b = hist[[id_col, "DayOfWeek", date_col]].copy()
    ytr_b = hist[target_col].copy()
    
    # Build X_future for baseline: (FoodID × target_date) with required cols
    future_rows = []
    for fid in food_ids_all:
        for td in horizon_dates:
            future_rows.append({id_col: fid, date_col: pd.to_datetime(td), "DayOfWeek": pd.Timestamp(td).dayofweek})
    Xfu_b = pd.DataFrame(future_rows)
    
    # dummy valid (baseline training doesn't need it, but API requires)
    Xva_dummy = Xtr_b.head(1).copy()
    yva_dummy = ytr_b.head(1).copy()

    tr_b = train_model(Xtr_b, ytr_b, Xva_dummy, yva_dummy, cfg_base)
    yhat_b = predict(tr_b.model, Xfu_b, cfg_base)
    
    # Postprocess baseline (match production style: non-negative int)
    yhat_b_pp = pd.Series(yhat_b).fillna(0.0).clip(lower=0.0).round().astype(int)
    
    baseline_rows: List[ForecastRow] = []
    for (fid, td, yh) in zip(Xfu_b[id_col].astype(str), pd.to_datetime(Xfu_b[date_col]).dt.date, yhat_b_pp):
        baseline_rows.append(
            ForecastRow(
                food_id=str(fid),
                forecast_origin_date=origin_date,
                target_date=td,
                yhat=Decimal(int(yh)),
                model_version=BASELINE_VERSION,
            )
        )

    print("[DEBUG] baseline rows:", len(baseline_rows), "version:", BASELINE_VERSION)
    
    # ==========================================================
    # B) MODEL (OPTIONAL): only for policy_level=2
    # ==========================================================
    model_rows: List[ForecastRow] = []
    if food_ids_model:
        if not args.model_path or not args.model_version:
            raise ValueError(
                "policy_level=2 items exist, but --model-path/--model-version not provided."
            )
        
        # Load model
        model = load_model(args.model_path)
        
        # Build forecast features (Tue..Sun only)
        X_forecast, feature_cols = build_features_for_forecast(
            df,
            origin_date=origin_date,
            config=cfg_model,
            candidate_ids=food_ids_model,
        )
        
        print("[DEBUG] X_forecast(model) rows:", len(X_forecast))
        print("[DEBUG] unique FoodID(model):", X_forecast[id_col].astype(str).nunique())
        print("[DEBUG] unique target_date(model):", pd.to_datetime(X_forecast["target_date"]).dt.date.nunique())
        
        # Predict + postprocess
        yhat_m = predict_lgbm(model, X_forecast, feature_cols)
        
        yhat_m_pp = postprocess_yhat(yhat_m)
        X_forecast = X_forecast.copy()
        X_forecast["yhat"] = yhat_m_pp
        
        # Build ForecastRow list (SKU-level)
        for r in X_forecast.itertuples(index=False):
            food_id = str(getattr(r, id_col))
            target_date = ensure_date(getattr(r, "target_date"))
            yhat_int = int(getattr(r, "yhat"))
            
            model_rows.append(
                ForecastRow(
                    food_id=food_id,
                    forecast_origin_date=origin_date,
                    target_date=target_date,
                    yhat=Decimal(yhat_int),
                    model_version=args.model_version,
                )
            )
        
        print("[DEBUG] model rows:", len(model_rows), "version:", args.model_version)
        
        unique_keys = {(x.food_id, x.forecast_origin_date, x.target_date, x.model_version) for x in model_rows}
        print("[DEBUG] unique keys in model_rows:", len(unique_keys))
        
        print(f"[DEBUG] feature_cols({len(feature_cols)}): {feature_cols}")

    else:
        print("[DEBUG] No policy_level=2 items; skip model inference.")
    
    # ==========================================================
    # C) Combine rows + Upsert
    # ==========================================================
    rows: List[ForecastRow] = baseline_rows + model_rows
    
    unique_keys = {(x.food_id, x.forecast_origin_date, x.target_date, x.model_version) for x in rows}
    print("[DEBUG] total rows to upsert:", len(rows))
    print("[DEBUG] unique keys:", len(unique_keys))
    
    if args.dry_run:
        print("[DRY-RUN] skip DB upsert")
        return
    
    # UPSERT
    svc = ForecastService()
    with SessionLocal() as db:
        n = svc.upsert_forecasts(db, rows)

    # log
    print(f"[OK] upserted {n} rows into food_sales_forecast_daily")
    print(f"[OK] origin_date={origin_date}")
    print(f"[OK] baseline_version={BASELINE_VERSION} rows={len(baseline_rows)}")
    if model_rows:
        print(f"[OK] model_version={args.model_version} rows={len(model_rows)}")


if __name__ == "__main__":
    main()

