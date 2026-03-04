SET NOCOUNT ON;
GO

------------------------------------------------------------
-- 1) Create table if not exists
------------------------------------------------------------
IF OBJECT_ID('dw.dim_date', 'U') IS NULL
BEGIN
    CREATE TABLE dw.dim_date (
        date_key            int           NOT NULL, -- yyyymmdd
        [date]              date          NOT NULL,

        [year]              smallint      NOT NULL,
        [quarter]           tinyint       NOT NULL,
        [month]             tinyint       NOT NULL,
        [day]               tinyint       NOT NULL,

        day_of_week_iso     tinyint       NOT NULL, -- 1=Mon ... 7=Sun
        day_name_en         varchar(9)    NOT NULL, -- Monday...
        is_weekend          bit           NOT NULL,

        iso_week            tinyint       NOT NULL,
        week_start_date     date          NOT NULL, -- Monday of that ISO-week
        month_start_date    date          NOT NULL,
        month_end_date      date          NOT NULL,

        -- ✅ add for your pipeline
        is_shop_closed      bit           NOT NULL, -- default rule: Monday closed (can override later)

        CONSTRAINT pk_dim_date PRIMARY KEY (date_key),
        CONSTRAINT uq_dim_date_date UNIQUE ([date])
    );

    CREATE INDEX ix_dim_date_year_month ON dw.dim_date([year], [month]);
    CREATE INDEX ix_dim_date_date ON dw.dim_date([date]);
END;
GO

------------------------------------------------------------
-- 2) Decide date range
------------------------------------------------------------
DECLARE @min_sales date, @max_sales date;

SELECT
    @min_sales = MIN(close_work_date),
    @max_sales = MAX(close_work_date)
FROM stg.stg_sales;

DECLARE @start_date date = COALESCE(DATEADD(day, -365, @min_sales), CONVERT(date, '2020-01-01'));
DECLARE @end_date   date = COALESCE(DATEADD(day,  365, @max_sales), CONVERT(date, '2030-12-31'));

IF (@start_date > @end_date)
BEGIN
    DECLARE @tmp date = @start_date;
    SET @start_date = @end_date;
    SET @end_date = @tmp;
END;

------------------------------------------------------------
-- 3) Insert
-- n → 產生數字序列（0, 1, 2, 3...）
-- d → 把數字變成日期
-- calc → 把日期拆成各種欄位
------------------------------------------------------------
;WITH
n AS (
    SELECT TOP (DATEDIFF(DAY, @start_date, @end_date) + 1)
           ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS i
    FROM sys.all_objects a
    CROSS JOIN sys.all_objects b
),
d AS (
    SELECT DATEADD(DAY, i, @start_date) AS [date]
    FROM n
),
calc AS (
    SELECT
        d.[date],

        -- ✅ stable yyyymmdd int without FORMAT (FORMAT is slow)
        CONVERT(int, CONVERT(char(8), d.[date], 112)) AS date_key,

        DATEPART(year, d.[date])    AS [year],
        DATEPART(quarter, d.[date]) AS [quarter],
        DATEPART(month, d.[date])   AS [month],
        DATEPART(day, d.[date])     AS [day],

        -- ✅ ISO weekday (1=Mon..7=Sun), independent of DATEFIRST
        ((DATEPART(WEEKDAY, d.[date]) + @@DATEFIRST - 2) % 7) + 1 AS day_of_week_iso,

        DATEPART(ISO_WEEK, d.[date]) AS iso_week,

        DATEFROMPARTS(DATEPART(year, d.[date]), DATEPART(month, d.[date]), 1) AS month_start_date,
        EOMONTH(d.[date]) AS month_end_date
    FROM d
)
INSERT INTO dw.dim_date (
    date_key,
    [date],
    [year], [quarter], [month], [day],
    day_of_week_iso, day_name_en, is_weekend,
    iso_week, week_start_date,
    month_start_date, month_end_date,
    is_shop_closed
)
SELECT
    c.date_key,
    c.[date],
    c.[year], c.[quarter], c.[month], c.[day],

    c.day_of_week_iso,

    -- day_name_en: generate from iso weekday (no LANGUAGE dependency)
    CASE c.day_of_week_iso
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
        ELSE 'Sunday'
    END AS day_name_en,

    CASE WHEN c.day_of_week_iso IN (6,7) THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END AS is_weekend,

    c.iso_week,

    -- ✅ week_start_date (Monday): date - (iso_dow-1)
    DATEADD(day, -(c.day_of_week_iso - 1), c.[date]) AS week_start_date,

    c.month_start_date,
    c.month_end_date,

    -- ✅ default shop closed rule: Monday closed
    CASE WHEN c.day_of_week_iso = 1 THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END AS is_shop_closed
FROM calc c
WHERE NOT EXISTS (
    SELECT 1
    FROM dw.dim_date x
    WHERE x.[date] = c.[date]
);
GO