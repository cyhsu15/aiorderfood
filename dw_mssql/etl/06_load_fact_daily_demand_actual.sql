DECLARE @from date = '1900-01-01';
DECLARE @to   date = '9999-12-31';
-- 你要回補某段日期就改這兩個變數，例如：
-- SET @from = '2025-01-01'; SET @to = '2025-12-31';

MERGE dw.fact_daily_demand_actual AS tgt
USING (
    SELECT
        close_work_date,
        canonical_dish_id,
        qty, dinein_qty, reserve_qty,
        is_zero_filled, is_shop_closed, has_unmapped_food, src_row_cnt
    FROM dw.vw_clean_sales
    WHERE close_work_date >= @from
      AND close_work_date <= @to
) AS src
ON  tgt.close_work_date   = src.close_work_date
AND tgt.canonical_dish_id = src.canonical_dish_id
WHEN MATCHED THEN
    UPDATE SET
        tgt.qty               = src.qty,
        tgt.dinein_qty        = src.dinein_qty,
        tgt.reserve_qty       = src.reserve_qty,
        tgt.is_zero_filled    = src.is_zero_filled,
        tgt.is_shop_closed    = src.is_shop_closed,
        tgt.has_unmapped_food = src.has_unmapped_food,
        tgt.src_row_cnt       = src.src_row_cnt,
        tgt.loaded_at         = sysdatetime()
WHEN NOT MATCHED BY TARGET THEN
    INSERT (
        close_work_date, canonical_dish_id,
        qty, dinein_qty, reserve_qty,
        is_zero_filled, is_shop_closed, has_unmapped_food, src_row_cnt,
        loaded_at
    )
    VALUES (
        src.close_work_date, src.canonical_dish_id,
        src.qty, src.dinein_qty, src.reserve_qty,
        src.is_zero_filled, src.is_shop_closed, src.has_unmapped_food, src.src_row_cnt,
        sysdatetime()
    )
-- 可選：如果你回補區間內「view 已經不產生某些 key」你要不要刪？
-- WHEN NOT MATCHED BY SOURCE AND tgt.close_work_date BETWEEN @from AND @to THEN DELETE
;
GO