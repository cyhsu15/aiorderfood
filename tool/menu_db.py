import csv
import re
# from sqlalchemy import create_engine, sessionmaker
# 確保已經定義或匯入 Base, Category, Dish, DishPrice 等模型類別
# from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure project root is on sys.path to import `app`
import os, sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 如果模型定義在其他模組中，使用下行匯入：
from app.models import Base, Category, Dish, DishPrice, DishTranslation, SetItem

from dotenv import load_dotenv
load_dotenv()
DATABASE_URL = str(os.getenv("DATABASE_URL"))

# 資料庫連線設定（這裡使用 SQLite 資料庫作為例子）
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

# 建立資料表（如尚未建立）
Base.metadata.create_all(engine)

# 準備容器來暫存分類和菜色資料
categories = {}  # 用於儲存 Category 物件，避免重複建立 {分類名稱: Category物件}
dish_map = {}    # 用於分組菜色資訊 { (分類名稱, 菜名主名稱): {'category': Category物件, 'name_zh': 名稱, 'variants': [(價格標籤, 價格), ...] } }

# 讀取 CSV 檔案並處理每一筆資料
with open('tool/阿霞飯店-菜單數據.csv', newline='', encoding='utf-8') as f:
    # 移除 UTF-8 BOM
    data = f.read()
    if data.startswith('\ufeff'):
        data = data.lstrip('\ufeff')
    f.seek(0)
    # 重新初始化文件內容去掉 BOM 後供 csv 解析
    reader = csv.DictReader(data.splitlines())
    for row in reader:
        # 取得並清理分類名稱（去除方括號及其內容）
        full_category = row['category']
        # 使用正則表達式去除開頭的[...]部分
        category_name = re.sub(r'^\[.*?\]', '', full_category).strip()
        if category_name == '':
            category_name = full_category  # 若沒有方括號則使用原始值

        # 建立 Category 物件（如果尚未建立過該分類）
        if category_name not in categories:
            cat_obj = Category(name_zh=category_name)
            session.add(cat_obj)
            categories[category_name] = cat_obj
        else:
            cat_obj = categories[category_name]

        # 解析菜名與價格
        dish_name = row['food_name']
        price_str = row['price']
        # 處理價格字串，將 'NULL' 或空值轉為 None，其他轉為浮點數
        if price_str is None or price_str.strip() == '' or price_str.strip().upper() == 'NULL':
            price_value = None
        else:
            try:
                # 嘗試轉為數字型態（整數或浮點數）
                price_value = float(price_str)
            except ValueError:
                price_value = None

        # 判斷菜名中是否有括號表示的份量或規格
        base_name = dish_name  # 菜色主名稱（去除括號部分）
        price_label = None     # 價格標籤（括號內的內容，如 "大", "小", "壺" 等）
        match = re.match(r'^(.*)\(([^)]+)\)$', dish_name)
        if match:
            # 抽取括號內文字
            variant_text = match.group(2)
            # 檢查括號內容是否含數字（表示可能是套餐編號或特殊代號，不作為一般份量合併）
            if any(char.isdigit() for char in variant_text):
                # 包含數字的括號內容，不拆分名稱，視為完整菜名
                base_name = dish_name
                price_label = None
            else:
                # 將括號前名稱作為菜色主名稱，括號內文字作為價格標籤
                base_name = match.group(1).strip()
                price_label = variant_text.strip()

        # 將菜色資訊加入 dish_map 分組
        key = (category_name, base_name)
        if key not in dish_map:
            dish_map[key] = {
                'category': cat_obj,
                'name_zh': base_name,
                'variants': set()
            }
        dish_map[key]['variants'].add((price_label, price_value))

# 將分組好的菜色資料寫入資料庫
for (category_name, base_name), info in dish_map.items():
    # 判斷是否為套餐類菜色
    name_zh = info['name_zh']
    is_set_flag = False
    if '桌菜' in name_zh or '套餐' in name_zh:
        is_set_flag = True

    # 建立 Dish 紀錄
    dish_obj = Dish(
        category=info['category'],
        name_zh=name_zh,
        is_set=is_set_flag,
        sort_order=0  # 若需要特定排序，可在此調整
    )
    session.add(dish_obj)
    # 建立對應的 DishPrice 紀錄（一個 Dish 可能有多個價位）
    for price_label, price_val in info['variants']:
        dish_price_obj = DishPrice(
            dish=dish_obj,
            price_label=price_label,
            price=price_val
        )
        session.add(dish_price_obj)

# 提交所有變更到資料庫
session.commit()

print("資料匯入完成！共建立 {} 個分類，{} 道菜色，以及對應的價格資料。".format(
    len(categories), len(dish_map)
))
