BEGIN;

-- 0) 基本防呆：如果 staging 裡 run_id 全是 NULL，先停下來（避免刪不到、又一直插）
-- 你也可以先用 SELECT 檢查再決定要不要保留這段
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM integration.stg_fact_forecast_daily WHERE run_id IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'staging has no non-null run_id; abort merge to avoid duplicates';
  END IF;
END $$;

-- 1) 刪掉同一批次（同 run_id）的舊資料：確保重跑可覆蓋
DELETE FROM integration.fact_forecast_daily f
USING (
  SELECT DISTINCT run_id
  FROM integration.stg_fact_forecast_daily
  WHERE run_id IS NOT NULL
) b
WHERE f.run_id = b.run_id;

-- 2) 插入新資料
INSERT INTO integration.fact_forecast_daily
(canonical_dish_id, forecast_origin_date, target_date, yhat, model_version, run_id, created_at)
SELECT
  canonical_dish_id,
  forecast_origin_date,
  target_date,
  yhat,
  model_version,
  run_id,
  COALESCE(created_at, NOW())
FROM integration.stg_fact_forecast_daily;

-- 3) 清 staging（可選，但我建議清掉，避免下一次誤用舊資料）
TRUNCATE TABLE integration.stg_fact_forecast_daily;

COMMIT;