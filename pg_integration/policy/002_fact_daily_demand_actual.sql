CREATE TABLE IF NOT EXISTS integration.fact_daily_demand_actual (
  canonical_dish_id   BIGINT NOT NULL,
  close_work_date     DATE   NOT NULL,
  qty                 INTEGER NOT NULL,
  is_shop_closed      BOOLEAN NOT NULL,
  loaded_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (canonical_dish_id, close_work_date)
);