IF OBJECT_ID('stg.stg_menu', 'U') IS NOT NULL
    DROP TABLE stg.stg_menu;
GO

CREATE TABLE stg.stg_menu (
    menu_sk             BIGINT IDENTITY(1,1) PRIMARY KEY,

    food_id             VARCHAR(64)     NOT NULL,
    food_name           NVARCHAR(200)   NULL,
    category_raw        NVARCHAR(200)   NULL,

    price               NUMERIC(12,2)   NULL,
    create_date         DATETIME2(0)            NULL,
    shop_id             NVARCHAR(64)     NULL,

    loaded_at           DATETIME2(0)    NOT NULL DEFAULT SYSDATETIME()
);
GO