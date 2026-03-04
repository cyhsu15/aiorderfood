IF OBJECT_ID('stg.stg_sales', 'U') IS NOT NULL
    DROP TABLE stg.stg_sales;
GO

CREATE TABLE stg.stg_sales (
    sales_sk            BIGINT IDENTITY(1,1) PRIMARY KEY,

    close_work_date     DATE            NOT NULL,
    food_id             VARCHAR(64)     NOT NULL,
    food_name           NVARCHAR(200)   NULL,

    dinein_qty          INT             NULL,
    reserve_qty         INT             NULL,
    qty                 INT             NULL,

    loaded_at           DATETIME2(0)    NOT NULL DEFAULT SYSDATETIME()
);
GO