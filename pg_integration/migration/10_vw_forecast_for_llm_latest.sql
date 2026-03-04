CREATE OR REPLACE VIEW integration.vw_forecast_for_llm_latest AS
WITH active_bridge AS (
    SELECT dish_price_id, canonical_dish_id
    FROM integration.bridge_canonical_to_oltp
    WHERE is_active = TRUE
),
active_policy AS (
    SELECT canonical_dish_id, effective_from, effective_to, chosen_model_version
    FROM integration.forecast_policy
    WHERE is_active = TRUE
),
candidates AS (
    SELECT
        ab.dish_price_id,
        ab.canonical_dish_id,
        f.forecast_origin_date,
        f.target_date,
        f.yhat,
        f.model_version,
        f.run_id,
        ROW_NUMBER() OVER (
            PARTITION BY ab.dish_price_id, f.target_date
            ORDER BY f.forecast_origin_date DESC, f.created_at DESC
        ) AS rn
    FROM active_bridge ab
    JOIN integration.fact_forecast_daily f
      ON f.canonical_dish_id = ab.canonical_dish_id
    JOIN active_policy ap
      ON ap.canonical_dish_id = ab.canonical_dish_id
     AND f.target_date >= ap.effective_from
     AND (ap.effective_to IS NULL OR f.target_date <= ap.effective_to)
     AND f.model_version = ap.chosen_model_version
)
SELECT
    dish_price_id AS price_id,
    canonical_dish_id,
    forecast_origin_date,
    target_date,
    yhat,
    model_version,
    run_id
FROM candidates
WHERE rn = 1;