INSERT INTO integration.forecast_policy
(canonical_dish_id, chosen_model_version, effective_from, effective_to, is_active, note)
SELECT DISTINCT
  b.canonical_dish_id,
  'baseline_k4_median_canonicalid_dow_v1' AS chosen_model_version,
  DATE '2000-01-01' AS effective_from,
  NULL::DATE AS effective_to,   -- 👈 這行是關鍵
  TRUE AS is_active,
  'bootstrap: route-through baseline' AS note
FROM integration.bridge_canonical_to_oltp b
WHERE b.is_active = TRUE
ON CONFLICT DO NOTHING;