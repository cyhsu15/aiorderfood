"""
Menu 邏輯：查詢 SQL 與組裝輸出，讓路由層保持精簡。
包含後台管理（CRUD）所需的服務函式。
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import text, select, delete, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Category, Dish, DishPrice, DishTranslation, DishDetail, SetItem


# 使用實際表名（全小寫與底線，PostgreSQL 會小寫化命名一致）
MENU_QUERY = text(
    """
    SELECT
      c.category_id,
      c.name_zh AS category_name,
      c.sort_order AS category_sort,
      d.dish_id,
      d.name_zh AS dish_name,
      d.is_set,
      dt.description AS translation_description,
      dd.description AS detail_description,
      dd.image_url AS image_url,
      dp.price_label,
      dp.price
    FROM category c
    LEFT JOIN dish d ON d.category_id = c.category_id
    LEFT JOIN dish_price dp ON dp.dish_id = d.dish_id
    LEFT JOIN dish_translation dt ON dt.dish_id = d.dish_id AND dt.lang = 'zh'
    LEFT JOIN dish_detail dd ON dd.dish_id = d.dish_id
    ORDER BY c.category_id, d.sort_order, d.dish_id, dp.price_id
    """
)


def build_menu_from_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """將查詢結果組裝為前端需要的結構。"""
    categories: Dict[int, Dict[str, Any]] = {}

    for row in rows:
        cid = row.get("category_id")
        if not cid:
            continue

        if cid not in categories:
            categories[cid] = {
                "category_id": cid,
                "category_name": row.get("category_name"),
                "sort_order": row.get("category_sort"),
                "dishes": {},
            }

        dish_id = row.get("dish_id")
        if dish_id and dish_id not in categories[cid]["dishes"]:
            categories[cid]["dishes"][dish_id] = {
                "dish_id": dish_id,
                "name": row.get("dish_name"),
                "description": row.get("detail_description") or row.get("translation_description"),
                "is_set": row.get("is_set"),
                "image_url": row.get("image_url"),
                "prices": [],
            }

        # 僅在存在價格欄位時才加入一筆價格
        if dish_id and (row.get("price_label") is not None or row.get("price") is not None):
            price_val = row.get("price")
            if price_val is not None:
                try:
                    price_val = float(price_val)
                except Exception:
                    pass
            categories[cid]["dishes"][dish_id]["prices"].append(
                {
                    "label": row.get("price_label") or None,
                    "price": price_val,
                }
            )

    result = [
        {
            "category_id": c["category_id"],
            "category_name": c["category_name"],
            "sort_order": c.get("sort_order") or 0,
            "dishes": list(c["dishes"].values()),
        }
        for c in categories.values()
    ]
    # 依照分類排序值排序
    result.sort(key=lambda x: (x.get("sort_order") or 0, x.get("category_id") or 0))
    return result


def fetch_menu(db: Session) -> List[Dict[str, Any]]:
    """執行查詢並將結果組裝為輸出結構，並為套餐附上子菜清單。"""
    rows = db.execute(MENU_QUERY).mappings().all()
    data = build_menu_from_rows(rows)

    # 收集所有套餐 dish_id
    set_ids: list[int] = []
    for cat in data:
        for d in cat.get("dishes", []):
            if d.get("is_set"):
                set_ids.append(d.get("dish_id"))

    if not set_ids:
        return data

    # 查詢套餐子項目
    ITEMS_SQL = text(
        """
        SELECT si.set_id, d.dish_id AS item_id, d.name_zh AS item_name, si.quantity, si.sort_order
        FROM set_item si
        JOIN dish d ON d.dish_id = si.item_id
        WHERE si.set_id = ANY(:set_ids)
        ORDER BY si.set_id, si.sort_order, si.item_id
        """
    )
    items_rows = db.execute(ITEMS_SQL, {"set_ids": set_ids}).mappings().all()
    mapping: Dict[int, List[Dict[str, Any]]] = {}
    for r in items_rows:
        mapping.setdefault(r["set_id"], []).append(
            {
                "item_id": r["item_id"],
                "name": r["item_name"],
                "quantity": r["quantity"],
                "sort_order": r["sort_order"],
            }
        )

    # 附加到輸出
    for cat in data:
        for d in cat.get("dishes", []):
            if d.get("is_set"):
                d["set_items"] = mapping.get(d.get("dish_id"), [])

    # 分類也依 sort_order 排序
    data.sort(key=lambda x: (x.get("sort_order") or 0, x.get("category_id") or 0))
    return data


# ----------------------
# Admin CRUD services
# ----------------------

def list_categories(db: Session) -> List[Dict[str, Any]]:
    rows = db.execute(
        select(Category.category_id, Category.name_zh, Category.name_en, Category.sort_order)
        .order_by(Category.sort_order, Category.category_id)
    )
    return [
        {"category_id": r.category_id, "name_zh": r.name_zh, "name_en": r.name_en, "sort_order": r.sort_order}
        for r in rows
    ]


def create_category(db: Session, name_zh: str, name_en: Optional[str] = None, sort_order: int | None = 0) -> Dict[str, Any]:
    cat = Category(name_zh=name_zh, name_en=name_en, sort_order=sort_order or 0)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"category_id": cat.category_id, "name_zh": cat.name_zh, "name_en": cat.name_en, "sort_order": cat.sort_order}


def update_category(db: Session, category_id: int, name_zh: Optional[str], name_en: Optional[str], sort_order: Optional[int] = None) -> Dict[str, Any]:
    cat = db.get(Category, category_id)
    if not cat:
        raise ValueError("category_not_found")
    if name_zh is not None:
        cat.name_zh = name_zh
    if name_en is not None:
        cat.name_en = name_en
    if sort_order is not None:
        cat.sort_order = int(sort_order)
    db.commit()
    db.refresh(cat)
    return {"category_id": cat.category_id, "name_zh": cat.name_zh, "name_en": cat.name_en, "sort_order": cat.sort_order}


def delete_category(db: Session, category_id: int) -> None:
    cat = db.get(Category, category_id)
    if not cat:
        raise ValueError("category_not_found")
    try:
        db.delete(cat)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("category_has_related_dishes")


def create_or_replace_prices(db: Session, dish: Dish, prices: Optional[List[Dict[str, Any]]]):
    if prices is None:
        return
    # 清空既有價格後重建（簡化處理）
    db.execute(delete(DishPrice).where(DishPrice.dish_id == dish.dish_id))
    for p in prices:
        price = p.get("price")
        label = p.get("label")
        db.add(DishPrice(dish_id=dish.dish_id, price=price, price_label=label))


def create_or_replace_translations(db: Session, dish: Dish, translations: Optional[List[Dict[str, Any]]]):
    if translations is None:
        return
    db.execute(delete(DishTranslation).where(DishTranslation.dish_id == dish.dish_id))
    for t in translations:
        lang = t.get("lang")
        name = t.get("name")
        description = t.get("description")
        if not lang or not name:
            continue
        db.add(DishTranslation(dish_id=dish.dish_id, lang=lang, name=name, description=description))


def upsert_dish_detail(
    db: Session,
    dish_id: int,
    *,
    image_url: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[str] = None,
):
    detail = db.get(DishDetail, dish_id)
    if detail is None:
        detail = DishDetail(dish_id=dish_id, image_url=image_url, description=description, tags=tags)
        db.add(detail)
    else:
        detail.image_url = image_url
        detail.description = description
        detail.tags = tags


def create_dish(
    db: Session,
    *,
    category_id: int,
    name_zh: str,
    is_set: bool = False,
    sort_order: int = 0,
    prices: Optional[List[Dict[str, Any]]] = None,
    translations: Optional[List[Dict[str, Any]]] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    dish = Dish(category_id=category_id, name_zh=name_zh, is_set=is_set, sort_order=sort_order)
    db.add(dish)
    db.flush()  # 先取得 dish_id
    create_or_replace_prices(db, dish, prices)
    create_or_replace_translations(db, dish, translations)
    if detail is not None:
        upsert_dish_detail(
            db,
            dish.dish_id,
            image_url=detail.get("image_url"),
            description=detail.get("description"),
            tags=detail.get("tags"),
        )
    db.commit()
    db.refresh(dish)
    return {
        "dish_id": dish.dish_id,
        "category_id": dish.category_id,
        "name_zh": dish.name_zh,
        "is_set": dish.is_set,
        "sort_order": dish.sort_order,
    }


def update_dish(
    db: Session,
    dish_id: int,
    *,
    category_id: Optional[int] = None,
    name_zh: Optional[str] = None,
    is_set: Optional[bool] = None,
    sort_order: Optional[int] = None,
    prices: Optional[List[Dict[str, Any]]] = None,
    translations: Optional[List[Dict[str, Any]]] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    dish = db.get(Dish, dish_id)
    if not dish:
        raise ValueError("dish_not_found")
    if category_id is not None:
        dish.category_id = category_id
    if name_zh is not None:
        dish.name_zh = name_zh
    if is_set is not None:
        dish.is_set = is_set
    if sort_order is not None:
        dish.sort_order = sort_order
    if prices is not None:
        create_or_replace_prices(db, dish, prices)
    if translations is not None:
        create_or_replace_translations(db, dish, translations)
    if detail is not None:
        upsert_dish_detail(
            db,
            dish.dish_id,
            image_url=detail.get("image_url"),
            description=detail.get("description"),
            tags=detail.get("tags"),
        )
    db.commit()
    db.refresh(dish)
    return {
        "dish_id": dish.dish_id,
        "category_id": dish.category_id,
        "name_zh": dish.name_zh,
        "is_set": dish.is_set,
        "sort_order": dish.sort_order,
    }


def list_dishes_by_category(db: Session, category_id: int) -> List[Dict[str, Any]]:
    dishes: List[Dish] = (
        db.query(Dish)
        .filter(Dish.category_id == category_id)
        .order_by(Dish.sort_order, Dish.dish_id)
        .all()
    )
    results: List[Dict[str, Any]] = []
    for d in dishes:
        prices = [
            {"label": p.price_label, "price": float(p.price) if p.price is not None else None}
            for p in d.prices
        ]
        det = d.detail
        results.append(
            {
                "dish_id": d.dish_id,
                "category_id": d.category_id,
                "name_zh": d.name_zh,
                "is_set": d.is_set,
                "sort_order": d.sort_order,
                "prices": prices,
                "detail": {
                    "image_url": det.image_url if det else None,
                    "description": det.description if det else None,
                    "tags": det.tags if det else None,
                },
            }
        )
    return results


def delete_dish(db: Session, dish_id: int) -> None:
    dish = db.get(Dish, dish_id)
    if not dish:
        raise ValueError("dish_not_found")
    # 預先檢查是否被其他表使用（例如作為套餐的子菜）
    in_sets = db.query(func.count(SetItem.item_id)).filter(SetItem.item_id == dish_id).scalar() or 0
    if in_sets > 0:
        raise ValueError("dish_in_use_in_set")
    try:
        db.delete(dish)
        db.commit()
    except IntegrityError:
        db.rollback()
        # 萬一其他 FK 限制導致失敗，回傳泛用訊息
        raise ValueError("dish_in_use")


# ----------------------
# Set (套餐) services
# ----------------------

def list_set_dishes(db: Session) -> List[Dict[str, Any]]:
    """列出 is_set = True 的菜色。"""
    rows = (
        db.execute(
            select(Dish.dish_id, Dish.name_zh, Dish.sort_order)
            .where(Dish.is_set.is_(True))
            .order_by(Dish.sort_order, Dish.dish_id)
        ).all()
    )
    return [
        {"dish_id": r.dish_id, "name_zh": r.name_zh, "sort_order": r.sort_order}
        for r in rows
    ]


def get_set_items(db: Session, set_id: int) -> List[Dict[str, Any]]:
    """取得某套餐的子菜品清單。"""
    items = (
        db.query(SetItem, Dish)
        .join(Dish, Dish.dish_id == SetItem.item_id)
        .filter(SetItem.set_id == set_id)
        .order_by(SetItem.sort_order, SetItem.item_id)
        .all()
    )
    return [
        {
            "item_id": d.dish_id,
            "name_zh": d.name_zh,
            "quantity": si.quantity,
            "sort_order": si.sort_order,
        }
        for si, d in items
    ]


def replace_set_items(db: Session, set_id: int, items: List[Dict[str, Any]]) -> None:
    """以整體覆蓋方式更新套餐內容。"""
    # 刪除既有
    db.query(SetItem).filter(SetItem.set_id == set_id).delete()
    # 插入新資料
    for idx, it in enumerate(items):
        item_id = int(it.get("item_id"))
        qty = int(it.get("quantity") or 1)
        sort_order = int(it.get("sort_order") if it.get("sort_order") is not None else idx)
        db.add(SetItem(set_id=set_id, item_id=item_id, quantity=qty, sort_order=sort_order))
    db.commit()
