CREATE OR REPLACE VIEW integration.vw_forecast_for_llm AS
WITH active_bridge AS (
    SELECT
        b.dish_price_id,
        b.canonical_dish_id
    FROM integration.bridge_canonical_to_oltp b
    WHERE b.is_active = TRUE
),
active_policy AS (
    -- 一個 canonical 可能有多條 policy（不同 effective_from）
    -- 這裡先把「每個 canonical、每個 target_date」應用哪條 policy 的規則留給下游 join
    SELECT
        p.canonical_dish_id,
        p.effective_from,
        p.effective_to,
        p.chosen_model_version
    FROM integration.forecast_policy p
    WHERE p.is_active = TRUE
),
joined AS (
    SELECT
        ab.dish_price_id,
        ab.canonical_dish_id,
        f.forecast_origin_date,
        f.target_date,
        f.yhat,
        f.model_version,
        f.run_id,
        ap.chosen_model_version
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
    dish_price_id,
    canonical_dish_id,
    forecast_origin_date,
    target_date,
    yhat,
    model_version,
    run_id
FROM joined;