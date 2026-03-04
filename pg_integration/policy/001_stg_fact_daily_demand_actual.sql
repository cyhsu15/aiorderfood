CREATE TABLE IF NOT EXISTS integration.stg_fact_daily_demand_actual (
  canonical_dish_id   BIGINT NOT NULL,
  close_work_date     DATE   NOT NULL,
  qty                 INTEGER NOT NULL,
  is_shop_closed      BOOLEAN NOT NULL,
  loaded_at           TIMESTAMPTZ NULL
);