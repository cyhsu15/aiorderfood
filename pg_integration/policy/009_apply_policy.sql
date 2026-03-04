-- 先關掉舊 active，再插入新 active
-- （用同一天跑多次也 OK：先關舊，再插新的；或你也可以加去重條件）
WITH c AS (
  SELECT * FROM integration.vw_policy_candidates
),
deactivate AS (
  UPDATE integration.forecast_policy p
  SET
    is_active = false,
    effective_to = CURRENT_DATE - INTERVAL '1 day',
    updated_at = NOW()
  FROM c
  WHERE p.canonical_dish_id = c.canonical_dish_id
    AND p.is_active = true
    AND (
      p.chosen_model_version IS DISTINCT FROM c.chosen_model_version
      OR p.win_rate IS DISTINCT FROM c.win_rate
    )
  RETURNING p.canonical_dish_id
)
INSERT INTO integration.forecast_policy (
  canonical_dish_id,
  effective_from,
  effective_to,
  chosen_model_version,
  win_rate,
  metric_name,
  note,
  is_active
)
SELECT
  c.canonical_dish_id,
  CURRENT_DATE,
  NULL,
  c.chosen_model_version,
  c.win_rate,
  c.metric_name,
  c.note,
  true
FROM c
-- 如果同一道菜今日已插入過一條 active（你重跑），靠唯一索引擋住；
-- 你也可以改成 ON CONFLICT (canonical_dish_id) WHERE is_active=true DO UPDATE，但 partial unique index 不支援直接 conflict target
;