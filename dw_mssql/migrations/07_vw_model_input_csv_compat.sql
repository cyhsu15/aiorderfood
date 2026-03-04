/*
    fact_daily_demand_actual (f) ← 每天每道菜的銷售事實
        JOIN canonical_dish (cd) ← 取 canonical_name、過濾 is_active
        LEFT JOIN rep_food (rf) ← 找代表 food_id
        LEFT JOIN menu_latest (ml) ← 用代表 food_id 查價格和分類

    price 為 NULL → IsMarketPrice = 1
*/
CREATE OR ALTER VIEW dw.vw_model_input_csv_compat
AS
WITH menu_latest AS (
    SELECT
        m.food_id,
        m.food_name,
        m.category_raw,
        m.price,
        ROW_NUMBER() OVER (
            PARTITION BY m.food_id
            ORDER BY
                CASE WHEN m.create_date IS NULL THEN 0 ELSE 1 END DESC,
                m.create_date DESC,
                m.menu_sk DESC
        ) AS rn
    FROM stg.stg_menu m
),
rep_food AS (
    SELECT
        b.canonical_dish_id,
        MIN(b.food_id) AS food_id
    FROM dw.bridge_pos_food_to_canonical b
    WHERE b.is_active = 1
    GROUP BY b.canonical_dish_id
)
SELECT
    -- 唯一識別鍵（給模型用）
    f.canonical_dish_id AS CanonicalDishId,

    -- 日期
    f.close_work_date AS CloseWorkDate,

    -- 顯示名稱
    cd.canonical_name AS FoodName,

    f.dinein_qty  AS [dinein(內用)],
    f.reserve_qty AS [reserve(預訂)],
    f.qty         AS [數量],

    f.is_shop_closed AS IsClosed,

    ml.category_raw AS category,
    ml.price        AS price,

    CAST(CASE WHEN ml.price IS NULL THEN 1 ELSE 0 END AS bit) AS IsMarketPrice

FROM dw.fact_daily_demand_actual f
JOIN dw.canonical_dish cd
  ON f.canonical_dish_id = cd.canonical_dish_id
LEFT JOIN rep_food rf
  ON f.canonical_dish_id = rf.canonical_dish_id
LEFT JOIN menu_latest ml
  ON rf.food_id = ml.food_id
 AND ml.rn = 1
WHERE cd.is_active = 1;
GO