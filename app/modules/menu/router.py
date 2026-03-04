from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from .menu import (
    fetch_menu,
    list_categories,
    create_category,
    update_category,
    delete_category,
    create_dish,
    update_dish,
    delete_dish,
    list_dishes_by_category,
    list_set_dishes,
    get_set_items,
    replace_set_items,
)


router = APIRouter()


@router.get("/menu")
def api_menu(db: Session = Depends(get_db)):
    """前端使用的菜單查詢 API。"""
    return fetch_menu(db)


# ----------------------
# Admin Schemas
# ----------------------

class CategoryCreate(BaseModel):
    """建立類別的輸入。"""
    name_zh: str = Field(..., description="中文名稱")
    name_en: Optional[str] = Field(None, description="英文名稱")
    sort_order: Optional[int] = Field(0, description="顯示排序")


class CategoryUpdate(BaseModel):
    """更新類別的輸入。"""
    name_zh: Optional[str] = Field(None, description="中文名稱")
    name_en: Optional[str] = Field(None, description="英文名稱")
    sort_order: Optional[int] = Field(None, description="顯示排序")


class PriceItem(BaseModel):
    """單一價格設定。"""
    label: Optional[str] = Field(None, description="價格標籤")
    price: Optional[float] = Field(None, description="價格金額")


class TranslationItem(BaseModel):
    """多語名稱/描述。"""
    lang: str
    name: str
    description: Optional[str] = None


class DishCreate(BaseModel):
    """建立菜色的輸入。"""
    category_id: int
    name_zh: str
    is_set: bool = False
    sort_order: int = 0
    prices: Optional[List[PriceItem]] = None
    translations: Optional[List[TranslationItem]] = None
    detail: Optional[dict] = None  # { image_url?: str, description?: str, tags?: str }


class DishUpdate(BaseModel):
    """更新菜色的輸入。"""
    category_id: Optional[int] = None
    name_zh: Optional[str] = None
    is_set: Optional[bool] = None
    sort_order: Optional[int] = None
    prices: Optional[List[PriceItem]] = None
    translations: Optional[List[TranslationItem]] = None
    detail: Optional[dict] = None


# ----------------------
# Admin Endpoints
# ----------------------

@router.get("/admin/categories")
def admin_list_categories(db: Session = Depends(get_db)):
    """列出所有類別。"""
    return list_categories(db)


@router.post("/admin/categories", status_code=201)
def admin_create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    """建立新類別。"""
    return create_category(db, payload.name_zh, payload.name_en, payload.sort_order or 0)


@router.patch("/admin/categories/{category_id}")
def admin_update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)):
    """更新類別名稱。"""
    try:
        return update_category(db, category_id, payload.name_zh, payload.name_en, payload.sort_order)
    except ValueError as e:
        if str(e) == "category_not_found":
            raise HTTPException(status_code=404, detail="category_not_found")
        raise


@router.delete("/admin/categories/{category_id}", response_class=Response)
def admin_delete_category(category_id: int, db: Session = Depends(get_db)):
    """刪除類別。若有關聯菜色，資料庫可能因 FK 限制而拒絕。"""
    try:
        delete_category(db, category_id)
    except ValueError as e:
        if str(e) == "category_not_found":
            raise HTTPException(status_code=404, detail="category_not_found")
        if str(e) == "category_has_related_dishes":
            raise HTTPException(status_code=409, detail="category_has_related_dishes")
        raise
    return Response(status_code=204)


@router.post("/admin/dishes", status_code=201)
def admin_create_dish(payload: DishCreate, db: Session = Depends(get_db)):
    """建立新菜色（可同時設定價格與翻譯）。"""
    prices = [p.dict() for p in (payload.prices or [])]
    translations = [t.dict() for t in (payload.translations or [])]
    return create_dish(
        db,
        category_id=payload.category_id,
        name_zh=payload.name_zh,
        is_set=payload.is_set,
        sort_order=payload.sort_order,
        prices=prices or None,
        translations=translations or None,
        detail=payload.detail or None,
    )


@router.patch("/admin/dishes/{dish_id}")
def admin_update_dish(dish_id: int, payload: DishUpdate, db: Session = Depends(get_db)):
    """更新菜色資訊。未提供的欄位不變。傳入 prices/translations 會整體覆蓋。"""
    prices = [p.dict() for p in (payload.prices or [])] if payload.prices is not None else None
    translations = [t.dict() for t in (payload.translations or [])] if payload.translations is not None else None
    try:
        return update_dish(
            db,
            dish_id,
            category_id=payload.category_id,
            name_zh=payload.name_zh,
            is_set=payload.is_set,
            sort_order=payload.sort_order,
            prices=prices,
            translations=translations,
            detail=payload.detail or None,
        )
    except ValueError as e:
        if str(e) == "dish_not_found":
            raise HTTPException(status_code=404, detail="dish_not_found")
        raise


@router.delete("/admin/dishes/{dish_id}", response_class=Response)
def admin_delete_dish(dish_id: int, db: Session = Depends(get_db)):
    """刪除菜色（會連動刪除價格與翻譯）。"""
    try:
        delete_dish(db, dish_id)
    except ValueError as e:
        if str(e) == "dish_not_found":
            raise HTTPException(status_code=404, detail="dish_not_found")
        if str(e) == "dish_in_use_in_set":
            raise HTTPException(status_code=409, detail="dish_in_use_in_set")
        if str(e) == "dish_in_use":
            raise HTTPException(status_code=409, detail="dish_in_use")
        raise
    return Response(status_code=204)


@router.get("/admin/categories/{category_id}/dishes")
def admin_list_dishes(category_id: int, db: Session = Depends(get_db)):
    """列出某類別下的菜色（含價格、排序與詳細內容）。"""
    return list_dishes_by_category(db, category_id)


# ----------------------
# Set (套餐) endpoints
# ----------------------

class SetItemInput(BaseModel):
    item_id: int
    quantity: int = Field(1, ge=1)
    sort_order: int | None = None


class SetItemsPayload(BaseModel):
    items: List[SetItemInput]


@router.get("/admin/sets")
def admin_list_sets(db: Session = Depends(get_db)):
    """列出可設定的套餐（is_set=True 的菜色）。"""
    return list_set_dishes(db)


@router.get("/admin/sets/{set_id}/items")
def admin_get_set_items(set_id: int, db: Session = Depends(get_db)):
    """取得指定套餐的子菜色清單。"""
    return get_set_items(db, set_id)


@router.put("/admin/sets/{set_id}/items", response_class=Response)
def admin_replace_set_items(set_id: int, payload: SetItemsPayload, db: Session = Depends(get_db)):
    """以整體覆蓋的方式更新套餐內容。"""
    replace_set_items(db, set_id, [i.dict() for i in payload.items])
    return Response(status_code=204)
