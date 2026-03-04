from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ForecastRow:
    """One forecast record at grain: canonical_dish_id × origin_date × target_date × model_version (× run_id)."""
    canonical_dish_id: int
    forecast_origin_date: date
    target_date: date
    yhat: Decimal
    model_version: str
    run_id: str  # IMPORTANT: keep non-null to guarantee idempotency


class ForecastRepository:
    """
    DB access layer for: 
    - dw.fact_forecast_daily (SQL Server).
    """
    def upsert_fact_forecasts_daily(
    self,
    db: Session,
    rows: Sequence[ForecastRow],
    ) -> int:
        """
        UPSERT forecasts into dw.fact_forecast_daily (SQL Server).

        Natural uniqueness within a run is enforced by:
            (run_id, canonical_dish_id, forecast_origin_date, target_date, model_version)

        NOTE:
        - run_id should be non-null, otherwise SQL Server UNIQUE allows duplicates and MERGE cannot match NULL = NULL.
        """
        if not rows:
            return 0

        q = text(
            """
            MERGE dw.fact_forecast_daily AS tgt
            USING (
                SELECT
                    :run_id              AS run_id,
                    :canonical_dish_id    AS canonical_dish_id,
                    :forecast_origin_date AS forecast_origin_date,
                    :target_date          AS target_date,
                    :model_version        AS model_version,
                    :yhat                 AS yhat
            ) AS src
            ON (
                tgt.run_id = src.run_id
                AND tgt.canonical_dish_id = src.canonical_dish_id
                AND tgt.forecast_origin_date = src.forecast_origin_date
                AND tgt.target_date = src.target_date
                AND tgt.model_version = src.model_version
            )
            WHEN MATCHED THEN
                UPDATE SET
                    yhat = src.yhat,
                    created_at = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN
                INSERT (
                    canonical_dish_id,
                    forecast_origin_date,
                    target_date,
                    yhat,
                    model_version,
                    run_id
                )
                VALUES (
                    src.canonical_dish_id,
                    src.forecast_origin_date,
                    src.target_date,
                    src.yhat,
                    src.model_version,
                    src.run_id
                );
            """
        )

        payload = [
            {
                "canonical_dish_id": int(r.canonical_dish_id),
                "forecast_origin_date": r.forecast_origin_date,
                "target_date": r.target_date,
                "yhat": r.yhat,
                "model_version": r.model_version,
                "run_id": r.run_id,
            }
            for r in rows
        ]
        
        # executemany row-by-row MERGE; for your scale (15×6×2) is totally fine.
        db.execute(q, payload)
        return len(rows)


