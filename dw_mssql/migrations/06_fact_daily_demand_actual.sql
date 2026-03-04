CREATE TABLE dw.fact_daily_demand_actual (
    close_work_date     date        NOT NULL,
    canonical_dish_id   bigint      NOT NULL,

    qty                 int         NOT NULL,
    dinein_qty          int         NOT NULL,
    reserve_qty         int         NOT NULL,

    is_zero_filled      bit         NOT NULL,
    is_shop_closed      bit         NOT NULL,
    has_unmapped_food   bit         NOT NULL,
    src_row_cnt         int         NOT NULL,

    loaded_at           datetime2(0) NOT NULL
        CONSTRAINT DF_fact_daily_demand_actual_loaded_at DEFAULT (sysdatetime()),

    CONSTRAINT PK_fact_daily_demand_actual
        PRIMARY KEY CLUSTERED (close_work_date, canonical_dish_id),

    CONSTRAINT FK_fact_daily_demand_actual_canonical
        FOREIGN KEY (canonical_dish_id) REFERENCES dw.canonical_dish(canonical_dish_id)
);
GO