#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
將 axia_dish_descriptions.json 的菜色描述寫入資料庫。

更新：改為參照 dish.csv 中的 dish_id 寫入 DB。
流程：
- 讀取 dish.csv（欄位：dish_id,dish_name,category_name），建立 name -> dish_id 映射
- 讀取 JSON（items[].disg_detil/dish_detail）取得 dish_name、description、tags
- 依據映射取得 dish_id，從資料庫以 dish_id 讀取 Dish 後寫入 DishDetail

用法示例：
  python import_dish_details.py ./axia_dish_descriptions.json \
      --csv-path ./dish.csv \
      --database-url postgresql+psycopg2://user:pass@host/db \
      --dry-run
"""

import argparse
import csv
import json
import os
from typing import Dict, List, Tuple, Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import os, sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 專案模型路徑（請依實際專案結構調整）
from app.models import Category, Dish, DishDetail  # noqa: F401


def normalize_tags(tags: List[str]) -> str:
    """正規化標籤：去除重複與空白，並以「, 」串接。"""
    seen = set()
    norm: List[str] = []
    for t in tags or []:
        if t is None:
            continue
        s = str(t).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        norm.append(s)
    return ", ".join(norm)


def extract_items(payload: dict) -> List[Tuple[str, str, List[str]]]:
    """
    從 JSON 提取 (dish_name, description, tags) 清單。
    支援 key: "disg_detil"（舊 typo）與 "dish_detail"。
    """
    items: List[Tuple[str, str, List[str]]] = []
    for obj in payload.get("items", []):
        block = obj.get("disg_detil") or obj.get("dish_detail") or {}
        name = (block.get("dish_name") or "").strip()
        desc = (block.get("dish_describer") or block.get("description") or "").strip()
        tags = block.get("tags") or []
        if name:
            items.append((name, desc, tags))
    return items


def load_csv_name_to_id(csv_path: str) -> Dict[str, int]:
    """讀取 dish.csv，建立 name_zh -> dish_id 的映射。"""
    mapping: Dict[str, int] = {}
    duplicates: Dict[str, int] = {}
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("dish_name") or "").strip()
            did_raw = (row.get("dish_id") or "").strip()
            if not name or not did_raw:
                continue
            try:
                did = int(did_raw)
            except ValueError:
                continue
            if name in mapping and name not in duplicates:
                duplicates[name] = mapping[name]
                continue
            mapping[name] = did
    if duplicates:
        print(f"注意：dish.csv 存在重複名稱 {len(duplicates)} 筆，將採用首筆出現的 dish_id。")
    return mapping


def upsert_detail_for_dish(
    session: Session,
    dish: "Dish",
    description: str,
    tags_str: str,
) -> bool:
    """建立或更新 DishDetail，回傳是否有變更。"""
    changed = False
    if dish.detail is None:
        dish.detail = DishDetail(description=description or None, tags=tags_str or None)
        changed = True
    else:
        if (dish.detail.description or "") != (description or ""):
            dish.detail.description = description or None
            changed = True
        if (dish.detail.tags or "") != (tags_str or ""):
            dish.detail.tags = tags_str or None
            changed = True
    return changed


def find_dish_by_id(session: Session, dish_id: int) -> Optional["Dish"]:
    stmt = select(Dish).where(Dish.dish_id == dish_id)
    return session.scalars(stmt).first()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import dish details (description, tags) into DB.")
    parser.add_argument("json_path", help="axia_dish_descriptions.json 檔案路徑")
    parser.add_argument("--csv-path", default="dish.csv", help="dish.csv 路徑（提供 dish_id 對應）")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="SQLAlchemy DATABASE_URL，預設讀環境變數 DATABASE_URL",
    )
    parser.add_argument("--dry-run", action="store_true", help="試跑不提交")
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("請提供 --database-url 或設定環境變數 DATABASE_URL")

    # 讀取 JSON
    with open(args.json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    items = extract_items(payload)
    if not items:
        raise SystemExit("JSON 中未找到 items 或無 dish 資料")

    # 讀取 CSV 對應
    name_to_id = load_csv_name_to_id(args.csv_path)
    if not name_to_id:
        raise SystemExit("dish.csv 無有效對應，請確認檔案內容")

    engine = create_engine(args.database_url, future=True)
    updated = 0
    skipped_no_csv_map = 0
    skipped_not_in_db = 0
    missing_csv_names: List[str] = []
    missing_db_ids: List[int] = []

    with Session(engine) as session:
        for name_zh, desc, tags in items:
            tags_str = normalize_tags(tags)
            dish_id = name_to_id.get(name_zh)
            if dish_id is None:
                skipped_no_csv_map += 1
                missing_csv_names.append(name_zh)
                continue

            dish = find_dish_by_id(session, dish_id)
            if dish is None:
                skipped_not_in_db += 1
                missing_db_ids.append(dish_id)
                continue

            if upsert_detail_for_dish(session, dish, desc, tags_str):
                updated += 1

        if args.dry_run:
            session.rollback()
            action = "DRY-RUN：未提交變更"
        else:
            session.commit()
            action = "已提交變更"

    print(f"{action}")
    print(f"輸入菜色總數：{len(items)}")
    print(f"成功更新 dish_detail：{updated}")
    print(f"略過（CSV 無對應 dish_id）：{skipped_no_csv_map}")
    print(f"略過（DB 無此 dish_id）：{skipped_not_in_db}")
    if missing_csv_names:
        print("CSV 未對應到的菜名（最多 50 筆）：")
        for n in missing_csv_names[:50]:
            print(f" - {n}")
        if len(missing_csv_names) > 50:
            print(f"... 共 {len(missing_csv_names)} 筆")
    if missing_db_ids:
        print("DB 未找到的 dish_id（最多 50 筆）：")
        for i in missing_db_ids[:50]:
            print(f" - {i}")
        if len(missing_db_ids) > 50:
            print(f"... 共 {len(missing_db_ids)} 筆")


if __name__ == "__main__":
    main()

