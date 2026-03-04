from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.orm import Session

from .repo import ForecastRepository, ForecastRow


class ForecastService:
    """Write forecasts to dw.fact_forecast_daily"""

    def __init__(self, repo: Optional[ForecastRepository] = None) -> None:
        self.repo = repo or ForecastRepository()
    
    def upsert_forecasts(
        self,
        db: Session,
        rows: Sequence[ForecastRow],
        *,
        commit: bool = True,
    ) -> int:
        """
        UPSERT forecast rows. Returns number of attempted rows (payload length).
        """
        n = self.repo.upsert_fact_forecasts_daily(db, rows)
        if commit:
            db.commit()
        return n
