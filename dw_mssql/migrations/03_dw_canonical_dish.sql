IF OBJECT_ID('dw.canonical_dish', 'U') IS NOT NULL
    DROP TABLE dw.canonical_dish;
GO

/*============================================================
dw.canonical_dish
- 穩定菜品實體（分析語意核心）
============================================================*/
CREATE TABLE dw.canonical_dish (
    canonical_dish_id   BIGINT IDENTITY(1,1) NOT NULL,
    basename            NVARCHAR(200) NOT NULL,
    price_label         NVARCHAR(50)  NOT NULL,

    -- 可選：若你想直接存 basename + price_label 的結果（方便人看/下游用）
    canonical_name      NVARCHAR(260) NULL,

    is_active           BIT NOT NULL CONSTRAINT DF_canonical_dish_is_active DEFAULT (1),
    created_at          DATETIME2(0) NOT NULL CONSTRAINT DF_canonical_dish_created_at DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_canonical_dish PRIMARY KEY (canonical_dish_id),

    -- 基本防呆：避免空字串（但允許 NULL 的 canonical_name）
    CONSTRAINT CK_canonical_dish_basename_nonempty CHECK (LEN(LTRIM(RTRIM(basename))) > 0),
    CONSTRAINT CK_canonical_dish_price_label_nonempty CHECK (LEN(LTRIM(RTRIM(price_label))) > 0)
);
GO