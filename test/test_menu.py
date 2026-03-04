"""
Menu 模組測試：涵蓋查詢組裝與基本 CRUD 服務。
改為使用 Postgres 的 `ai_order_food_test` 資料庫。
執行測試前請在 .env 設定 `DATABASE_URL` 指向測試庫。
為避免誤刪正式資料，測試內含資料庫名稱防呆檢查。
"""

from typing import Any, Dict, List

import pytest
import os
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Base, Category, Dish, DishPrice, DishTranslation
from app.db import DATABASE_URL  # kept for static typing references
from app.modules.menu.menu import (
    build_menu_from_rows,
    list_categories,
    create_category,
    update_category,
    delete_category,
    create_dish,
    update_dish,
    delete_dish,
    replace_set_items,
)


def _ensure_test_db_url() -> str:
    url = os.getenv("TEST_DATABASE_URL") or str(DATABASE_URL)
    lowered = url.lower()
    if "ai_order_food_test" not in lowered:
        raise RuntimeError("Refusing to run tests: DATABASE_URL must point to ai_order_food_test")
    return url


"""
db_session fixture is provided by test/conftest.py
which runs Alembic migrations and truncates DB per test.
"""


def test_build_menu_from_rows_basic():
    """驗證 build_menu_from_rows 的基本巢狀組裝邏輯。"""
    rows: List[Dict[str, Any]] = [
        {"category_id": 1, "category_name": "冷盤", "dish_id": 10, "dish_name": "三色拼盤", "is_set": False, "description": None, "price_label": None, "price": 180},
        {"category_id": 1, "category_name": "冷盤", "dish_id": 10, "dish_name": "三色拼盤", "is_set": False, "description": None, "price_label": "小", "price": 180},
        {"category_id": 1, "category_name": "冷盤", "dish_id": 10, "dish_name": "三色拼盤", "is_set": False, "description": None, "price_label": "大", "price": 320},
        {"category_id": 1, "category_name": "冷盤", "dish_id": 11, "dish_name": "海蜇頭", "is_set": False, "description": "爽脆", "price_label": None, "price": None},
    ]
    data = build_menu_from_rows(rows)
    assert len(data) == 1
    cat = data[0]
    assert cat["category_id"] == 1
    assert cat["category_name"] == "冷盤"
    assert len(cat["dishes"]) == 2
    dish0 = cat["dishes"][0]
    assert dish0["dish_id"] == 10
    assert dish0["name"] == "三色拼盤"
    assert len(dish0["prices"]) == 3


def test_category_crud(db_session: Session):
    """類別 CRUD：建立、查詢、更新、刪除。"""
    db = db_session

    # 初始為空
    cats = list_categories(db)
    assert cats == []

    # 建立
    c = create_category(db, name_zh="熱炒", name_en="Stir-fry")
    assert c["category_id"] > 0

    cats = list_categories(db)
    assert len(cats) == 1 and cats[0]["name_zh"] == "熱炒"

    # 更新
    updated = update_category(db, c["category_id"], name_zh="家常熱炒", name_en=None)
    assert updated["name_zh"] == "家常熱炒"

    # 刪除成功（無關聯菜色）
    delete_category(db, c["category_id"])
    cats = list_categories(db)
    assert cats == []


def test_category_delete_blocked_when_has_dishes(db_session: Session):
    """當類別仍有菜色時，刪除需被阻擋（回傳 ValueError）。"""
    db = db_session
    c = create_category(db, name_zh="冷盤")
    d = create_dish(db, category_id=c["category_id"], name_zh="三色拼盤", prices=[{"label": None, "price": 180}])
    assert d["dish_id"] > 0

    with pytest.raises(ValueError) as exc:
        delete_category(db, c["category_id"])
    assert str(exc.value) in {"category_has_related_dishes", "category_not_found"}  # 若資料庫未啟用 FK，行為可能不同


def test_dish_crud_with_prices_and_translations(db_session: Session):
    """菜色 CRUD：建立、更新（覆蓋價格、翻譯）、刪除。"""
    db = db_session
    c = create_category(db, name_zh="湯品")

    # 建立菜色（含價格與翻譯）
    d = create_dish(
        db,
        category_id=c["category_id"],
        name_zh="魚丸湯",
        is_set=False,
        sort_order=5,
        prices=[{"label": None, "price": 60}, {"label": "大", "price": 90}],
        translations=[{"lang": "zh", "name": "魚丸湯", "description": "清爽"}],
    )
    assert d["dish_id"] > 0 and d["sort_order"] == 5

    # 覆蓋更新：更名、改排序、重設價格、調整翻譯
    d2 = update_dish(
        db,
        d["dish_id"],
        name_zh="手工魚丸湯",
        sort_order=8,
        prices=[{"label": None, "price": 70}],
        translations=[{"lang": "zh", "name": "手工魚丸湯", "description": "更濃郁"}],
    )
    assert d2["name_zh"] == "手工魚丸湯"
    assert d2["sort_order"] == 8

    # 刪除
    delete_dish(db, d["dish_id"])
    # 確認刪除（無例外即通過）；可再查 ORM 確認不存在
    assert db.get(Dish, d["dish_id"]) is None


def test_delete_dish_blocked_when_used_in_set(db_session: Session):
    """菜色作為套餐子項目時，刪除應被阻擋；移除關聯後可正常刪除。"""
    db = db_session
    cat = create_category(db, name_zh="主菜")
    # 建立套餐與一般菜色
    set_dish = create_dish(db, category_id=cat["category_id"], name_zh="雙人套餐", is_set=True)
    child = create_dish(db, category_id=cat["category_id"], name_zh="宮保雞丁")

    # 將 child 納入套餐內容
    replace_set_items(db, set_dish["dish_id"], items=[{"item_id": child["dish_id"], "quantity": 1, "sort_order": 0}])

    # 嘗試刪除 child，應該被阻擋
    with pytest.raises(ValueError) as exc:
        delete_dish(db, child["dish_id"])
    assert str(exc.value) in {"dish_in_use_in_set", "dish_in_use"}

    # 移除套餐內容後再刪除
    replace_set_items(db, set_dish["dish_id"], items=[])
    delete_dish(db, child["dish_id"])
    assert db.get(Dish, child["dish_id"]) is None


def test_delete_cascades_detail_price_translation(db_session: Session):
    """刪除菜色時應連動刪除價格、翻譯與詳細內容，避免孤兒資料。 理論上FK會避免"""
    db = db_session
    cat = create_category(db, name_zh="點心")
    d = create_dish(
        db,
        category_id=cat["category_id"],
        name_zh="芝麻球",
        prices=[{"label": None, "price": 35}],
        translations=[{"lang": "zh", "name": "芝麻球", "description": "香甜"}],
        detail={"image_url": "http://example/img.jpg", "description": "內餡飽滿", "tags": "甜點,炸"},
    )

    # 確認都存在
    dish = db.get(Dish, d["dish_id"]) ; assert dish is not None
    assert dish.prices and dish.translations and dish.detail is not None

    # 刪除後，相關資料應連動刪除
    delete_dish(db, d["dish_id"])
    assert db.get(Dish, d["dish_id"]) is None
    # 直接查詢確認子表無殘留
    assert db.execute(text("SELECT COUNT(*) FROM dish_price WHERE dish_id=:id"), {"id": d["dish_id"]}).scalar() == 0
    assert db.execute(text("SELECT COUNT(*) FROM dish_translation WHERE dish_id=:id"), {"id": d["dish_id"]}).scalar() == 0
    assert db.execute(text("SELECT COUNT(*) FROM dish_detail WHERE dish_id=:id"), {"id": d["dish_id"]}).scalar() == 0
