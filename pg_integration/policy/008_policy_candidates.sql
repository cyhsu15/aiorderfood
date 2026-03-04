-- 你可把這些閾值做成 SQL 常數或之後改成 config table
CREATE OR REPLACE VIEW integration.vw_policy_candidates AS
WITH params AS (
  SELECT 8::int AS min_folds, 0.60::numeric AS min_win_rate
),
best_model AS (
  SELECT
    s.*,
    ROW_NUMBER() OVER (
      PARTITION BY s.canonical_dish_id
      ORDER BY s.win_rate DESC, s.avg_gain DESC, s.model_version
    ) AS rn
  FROM integration.vw_winrate_summary s, params p
  WHERE s.n_folds >= p.min_folds
    AND s.win_rate >= p.min_win_rate
)
SELECT
  b.canonical_dish_id,
  COALESCE(m.model_version, 'baseline_k4_median_canonicalid_dow_v1') AS chosen_model_version,
  m.win_rate,
  'winrate_wape'::varchar(64) AS metric_name,
  CASE
    WHEN m.model_version IS NULL THEN
      'fallback=baseline | reason=insufficient_evidence_or_low_winrate'
    ELSE
      'chosen_by=win_rate_then_avg_gain | min_folds=8 | min_win_rate=0.60'
  END AS note
FROM (
  SELECT DISTINCT canonical_dish_id
  FROM integration.bridge_canonical_to_oltp
  WHERE is_active = true
) b
LEFT JOIN best_model m
  ON m.canonical_dish_id = b.canonical_dish_id
 AND m.rn = 1;