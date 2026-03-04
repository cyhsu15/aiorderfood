CREATE OR ALTER VIEW dw.vw_clean_sales
AS
WITH
------------------------------------------------------------
-- 1) A+B：排除期間 + 負值歸零 + 聚合成 日×food_id
------------------------------------------------------------
sales_ab AS (
    SELECT
        s.close_work_date,
        s.food_id,

        SUM(CASE WHEN COALESCE(s.dinein_qty, 0)  < 0 THEN 0 ELSE COALESCE(s.dinein_qty, 0)  END) AS dinein_qty_clean,
        SUM(CASE WHEN COALESCE(s.reserve_qty, 0) < 0 THEN 0 ELSE COALESCE(s.reserve_qty, 0) END) AS reserve_qty_clean,
        SUM(CASE WHEN COALESCE(s.qty, 0)        < 0 THEN 0 ELSE COALESCE(s.qty, 0)        END) AS qty_clean,

        COUNT(*) AS src_row_cnt
    FROM stg.stg_sales s
    WHERE NOT (
        s.close_work_date >= '2025-10-01'
        AND s.close_work_date <  '2026-01-01'
    )
    GROUP BY
        s.close_work_date,
        s.food_id
),

------------------------------------------------------------
-- 2) 日期範圍用 sales_ab（已排除後）
------------------------------------------------------------
date_range AS (
    SELECT
        MIN(a.close_work_date) AS min_dt,
        MAX(a.close_work_date) AS max_dt
    FROM sales_ab a
),

------------------------------------------------------------
-- 3) food_id → canonical_dish_id（用 bridge）
------------------------------------------------------------
sales_mapped AS (
    SELECT
        a.close_work_date,
        b.canonical_dish_id,
        a.food_id,
        a.dinein_qty_clean,
        a.reserve_qty_clean,
        a.qty_clean,
        a.src_row_cnt,

        CASE WHEN b.canonical_dish_id IS NULL THEN 1 ELSE 0 END AS is_unmapped_food
    FROM sales_ab a
    LEFT JOIN dw.bridge_pos_food_to_canonical b
        ON a.food_id = b.food_id
       AND b.is_active = 1
),

------------------------------------------------------------
-- 4) C：date spine（用 dim_date 切到 min/max）
------------------------------------------------------------
date_spine AS (
    SELECT
        d.[date] AS close_work_date,
        d.is_shop_closed
    FROM dw.dim_date d
    CROSS JOIN date_range r
    WHERE d.[date] >= r.min_dt
      AND d.[date] <= r.max_dt
),

------------------------------------------------------------
-- 5) C：dish spine（只取 「sales 內出現過」的那 15 道 canonical_dish）
------------------------------------------------------------
dish_spine AS (
    SELECT DISTINCT
        cd.canonical_dish_id,
        cd.basename,
        cd.price_label,
        cd.canonical_name
    FROM sales_mapped sm
    INNER JOIN dw.canonical_dish cd
        ON cd.canonical_dish_id = sm.canonical_dish_id
    WHERE sm.canonical_dish_id IS NOT NULL
      AND cd.is_active = 1
),

------------------------------------------------------------
-- 6) C：完整矩陣（日 × canonical_dish_id）
------------------------------------------------------------
grid AS (
    SELECT
        ds.close_work_date,
        ds.is_shop_closed,
        di.canonical_dish_id,
        di.basename,
        di.price_label,
        di.canonical_name
    FROM date_spine ds
    CROSS JOIN dish_spine di
),

------------------------------------------------------------
-- 7) 聚合成 日×canonical_dish_id
------------------------------------------------------------
sales_by_day_canonical AS (
    SELECT
        close_work_date,
        canonical_dish_id,

        SUM(dinein_qty_clean)  AS dinein_qty_clean,
        SUM(reserve_qty_clean) AS reserve_qty_clean,
        SUM(qty_clean)         AS qty_clean,

        SUM(src_row_cnt) AS src_row_cnt_sum,
        MAX(CASE WHEN is_unmapped_food = 1 THEN 1 ELSE 0 END) AS has_unmapped_food
    FROM sales_mapped
    WHERE canonical_dish_id IS NOT NULL
    GROUP BY close_work_date, canonical_dish_id
)

------------------------------------------------------------
-- 8) Final：補零 + 店休日 + 品質旗標
------------------------------------------------------------
SELECT
    g.close_work_date,
    g.canonical_dish_id,
    g.basename,
    g.price_label,
    g.canonical_name,

    COALESCE(s.qty_clean, 0)         AS qty,
    COALESCE(s.dinein_qty_clean, 0)  AS dinein_qty,
    COALESCE(s.reserve_qty_clean, 0) AS reserve_qty,

    CAST(CASE WHEN s.canonical_dish_id IS NULL THEN 1 ELSE 0 END AS bit) AS is_zero_filled,
    g.is_shop_closed,

    CAST(COALESCE(s.has_unmapped_food, 0) AS bit) AS has_unmapped_food,
    COALESCE(s.src_row_cnt_sum, 0) AS src_row_cnt
FROM grid g
LEFT JOIN sales_by_day_canonical s
    ON g.close_work_date     = s.close_work_date
   AND g.canonical_dish_id   = s.canonical_dish_id
;
GO