from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ForecastRow:
    """One forecast record at grain: canonical_dish_id × origin_date × target_date × model_version × run_id."""
    canonical_dish_id: int
    forecast_origin_date: date
    target_date: date
    yhat: Decimal
    model_version: str
    run_id: str  # IMPORTANT: keep non-null to guarantee idempotency


class ForecastRepository:
    """
    DB access layer for:
    - integration.fact_forecast_daily (PostgreSQL).
    """

    def upsert_fact_forecasts_daily(
        self,
        db: Session,
        rows: Sequence[ForecastRow],
    ) -> int:
        """
        UPSERT forecasts into integration.fact_forecast_daily (PostgreSQL).

        Natural uniqueness within a run is enforced by:
            (run_id, canonical_dish_id, forecast_origin_date, target_date, model_version)

        NOTE:
        - run_id should be non-null to guarantee idempotency.
        - Target table must have:
            UNIQUE (run_id, canonical_dish_id, forecast_origin_date, target_date, model_version)
        """
        if not rows:
            return 0

        q = text(
            """
            INSERT INTO integration.fact_forecast_daily (
                canonical_dish_id,
                forecast_origin_date,
                target_date,
                yhat,
                model_version,
                run_id
            )
            VALUES (
                :canonical_dish_id,
                :forecast_origin_date,
                :target_date,
                :yhat,
                :model_version,
                :run_id
            )
            ON CONFLICT (run_id, canonical_dish_id, forecast_origin_date, target_date, model_version)
            DO UPDATE SET
                yhat = EXCLUDED.yhat,
                created_at = NOW();
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

        db.execute(q, payload)
        return len(rows)