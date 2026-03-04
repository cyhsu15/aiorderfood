INSERT INTO integration.fact_daily_demand_actual (
  canonical_dish_id, close_work_date, qty, is_shop_closed, loaded_at
)
SELECT
  canonical_dish_id,
  close_work_date,
  qty,
  is_shop_closed,
  COALESCE(loaded_at, NOW())
FROM integration.stg_fact_daily_demand_actual
ON CONFLICT (canonical_dish_id, close_work_date)
DO UPDATE SET
  qty = EXCLUDED.qty,
  is_shop_closed = EXCLUDED.is_shop_closed,
  loaded_at = EXCLUDED.loaded_at;