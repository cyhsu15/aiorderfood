IF OBJECT_ID('dw.bridge_pos_food_to_canonical', 'U') IS NOT NULL
    DROP TABLE dw.bridge_pos_food_to_canonical;
GO

CREATE TABLE dw.bridge_pos_food_to_canonical (
    food_id                     VARCHAR(64)    NOT NULL,   -- PK: POS FoodID
    canonical_dish_id            BIGINT         NOT NULL,   -- FK -> dw.canonical_dish

    -- 這些是「當時 menu 端看到的原始語意」：用來稽核/回溯/人工修正很重要
    source_menu_food_name        NVARCHAR(200)  NULL,
    source_menu_category_raw     NVARCHAR(200)  NULL,
    source_menu_snapshot_date    DATETIME2(0)   NULL,   -- 你也可改 DATETIME2(0)，看你 menu 是日快照還是時間點

    -- POS sales 觀測到的時間範圍（用來判斷 FoodID 是否仍在使用、何時出現）
    first_seen_date              DATE           NULL,
    last_seen_date               DATE           NULL,

    is_active                    BIT            NOT NULL CONSTRAINT DF_bridge_is_active DEFAULT (1),
    created_at                   DATETIME2(0)   NOT NULL CONSTRAINT DF_bridge_created_at DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_bridge_pos_food_to_canonical PRIMARY KEY (food_id),

    CONSTRAINT FK_bridge_pos_food_to_canonical__canonical_dish
        FOREIGN KEY (canonical_dish_id)
        REFERENCES dw.canonical_dish (canonical_dish_id),

    CONSTRAINT CK_bridge_seen_dates CHECK (
        first_seen_date IS NULL OR last_seen_date IS NULL OR first_seen_date <= last_seen_date
    )
);
GO