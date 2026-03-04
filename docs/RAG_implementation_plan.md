# RAG 菜單語義搜尋系統實作計畫

## 📋 實作概要

建立基於 **pgvector** 的菜單語義搜尋系統，透過離線工具處理 `axia_dish_descriptions.json`（496道菜品，19.6MB），將向量嵌入整合到現有 PostgreSQL 資料庫，為前端提供智能搜尋 API。

### 技術選型
- **向量資料庫**: pgvector（PostgreSQL extension）
- **Embedding 模型**: OpenAI text-embedding-3-small (1536維)
- **應用場景**: 客戶端語義搜尋
- **整合方式**: 離線預處理 + API 端點
- **更新頻率**: 靜態（不常更新）

---

## 🔧 階段一：資料預處理工具

### 1.1 建立預處理腳本 `tool/embedding_builder.py`

**功能**：
1. 讀取 `tool/dish_describer/axia_dish_descriptions.json`
2. 資料清理與壓縮
3. 生成向量嵌入
4. 輸出處理後的資料

**資料清理邏輯**：

#### a) 移除冗餘資料
```python
# 原始結構（保留）
{
  "dish_name": "烏魚子",
  "dish_describer": "阿霞飯店的烏魚子以傳統手藝醃製...",
  "tags": ["海鮮類", "點心", "小菜", "冷食"]
}

# 移除的欄位
# - sources: 不需要用於搜尋
# - snippets: 佔用大量空間，且內容重複
```

#### b) 標籤正規化
```python
# 問題：重複標籤、分類不一致
tags_raw = ["海鮮類", "海鮮", "点心", "點心"]

# 處理邏輯
1. 繁簡轉換（統一為繁體）
2. 去除重複
3. 分類歸納（建立標籤映射表）

# 結果
tags_normalized = ["海鮮類", "點心"]
```

#### c) 建立搜尋文字
```python
# 組合格式（用於生成 embedding）
search_text = f"{dish_name} | {dish_describer} | {', '.join(tags)}"

# 範例
"烏魚子 | 阿霞飯店的烏魚子以傳統手藝醃製，鹹香濃郁... | 海鮮類, 點心, 小菜, 冷食"
```

### 1.2 生成 Embedding

```python
import openai

def generate_embedding(text: str) -> list[float]:
    """使用 OpenAI API 生成向量嵌入"""
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        encoding_format="float"
    )
    return response.data[0].embedding  # 1536 維向量
```

**成本估算**：
- 496 道菜品
- 平均 ~200 tokens/dish
- 總計：~99,200 tokens
- **預估成本：$0.02 USD**（text-embedding-3-small 定價：$0.02/1M tokens）

### 1.3 輸出格式

**CSV 格式** (`tool/output/dish_embeddings.csv`):
```csv
dish_id,dish_name,search_text,embedding,tags
1,烏魚子,"烏魚子 | 阿霞飯店的...",[0.123,-0.456,...],"海鮮類,點心,小菜,冷食"
2,紅蟳米糕,"紅蟳米糕 | ...",[0.789,...],桌菜,海鮮,台菜"
```

**或 JSON 格式** (`tool/output/dish_embeddings.json`):
```json
[
  {
    "dish_name": "烏魚子",
    "search_text": "烏魚子 | 阿霞飯店的...",
    "embedding": [0.123, -0.456, ...],
    "tags": ["海鮮類", "點心", "小菜", "冷食"]
  }
]
```

### 1.4 腳本範例結構

```python
# tool/embedding_builder.py

import json
import openai
from pathlib import Path

def load_raw_data(file_path: str):
    """載入原始 JSON"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def clean_data(raw_data: dict):
    """清理和正規化資料"""
    items = raw_data['items']
    cleaned = []

    for item in items:
        detail = item['disg_detil']  # 注意拼寫錯誤

        # 標籤正規化
        tags = normalize_tags(detail['tags'])

        # 建立搜尋文字
        search_text = build_search_text(
            detail['dish_name'],
            detail['dish_describer'],
            tags
        )

        cleaned.append({
            'dish_name': detail['dish_name'],
            'search_text': search_text,
            'tags': tags
        })

    return cleaned

def normalize_tags(tags: list[str]) -> list[str]:
    """標籤正規化"""
    # TODO: 實作繁簡轉換、去重、分類
    pass

def build_search_text(name: str, desc: str, tags: list[str]) -> str:
    """組合搜尋文字"""
    return f"{name} | {desc} | {', '.join(tags)}"

def generate_embeddings(cleaned_data: list[dict]):
    """批量生成 embedding"""
    for item in cleaned_data:
        item['embedding'] = generate_embedding(item['search_text'])
    return cleaned_data

def save_output(data: list[dict], output_path: str):
    """保存處理結果"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    # 執行流程
    raw_data = load_raw_data('tool/dish_describer/axia_dish_descriptions.json')
    cleaned = clean_data(raw_data)
    with_embeddings = generate_embeddings(cleaned)
    save_output(with_embeddings, 'tool/output/dish_embeddings.json')
```

---

## 🗄️ 階段二：資料庫遷移

### 2.1 安裝 pgvector Extension

```sql
-- 在 PostgreSQL 中執行
CREATE EXTENSION IF NOT EXISTS vector;
```

**驗證安裝**：
```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### 2.2 修改資料表結構

**方案 A：擴展現有 `dish_detail` 表**（推薦）

```sql
-- 新增欄位
ALTER TABLE dish_detail
  ADD COLUMN IF NOT EXISTS embedding vector(1536),
  ADD COLUMN IF NOT EXISTS search_text TEXT;

-- 新增註解
COMMENT ON COLUMN dish_detail.embedding IS 'OpenAI text-embedding-3-small 向量 (1536維)';
COMMENT ON COLUMN dish_detail.search_text IS '組合的搜尋文字（菜名+描述+標籤）';
```

**方案 B：建立獨立 `dish_embedding` 表**（備選）

```sql
CREATE TABLE dish_embedding (
    id SERIAL PRIMARY KEY,
    dish_id INTEGER REFERENCES dish(id) ON DELETE CASCADE,
    search_text TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(dish_id)
);
```

### 2.3 建立向量索引

**HNSW 索引**（推薦，適合靜態資料）：
```sql
CREATE INDEX dish_embedding_hnsw_idx
ON dish_detail
USING hnsw (embedding vector_cosine_ops);
```

**IVFFlat 索引**（備選，適合頻繁更新）：
```sql
CREATE INDEX dish_embedding_ivfflat_idx
ON dish_detail
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

**索引參數說明**：
- `vector_cosine_ops`: 使用餘弦相似度（最適合文字搜尋）
- `hnsw`: Hierarchical Navigable Small World（高效查詢，適合靜態資料）
- `ivfflat`: Inverted File with Flat compression（適合頻繁更新）

### 2.4 匯入資料腳本

```python
# tool/import_embeddings.py

import json
import psycopg2
from psycopg2.extras import execute_values

def import_embeddings(json_path: str, db_url: str):
    """將處理後的 embedding 匯入資料庫"""

    # 載入資料
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 連接資料庫
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # 準備批量插入資料
    values = [
        (
            item['dish_name'],
            item['search_text'],
            item['embedding'],  # pgvector 自動處理 list 轉換
            item['tags']
        )
        for item in data
    ]

    # 批量更新（假設菜品已存在）
    execute_values(
        cur,
        """
        UPDATE dish_detail
        SET search_text = data.search_text,
            embedding = data.embedding::vector
        FROM (VALUES %s) AS data(dish_name, search_text, embedding, tags)
        WHERE dish.name = data.dish_name
        """,
        values
    )

    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    import os
    from dotenv import load_dotenv

    load_dotenv()
    db_url = os.getenv('DATABASE_URL')
    import_embeddings('tool/output/dish_embeddings.json', db_url)
```

### 2.5 Alembic 遷移腳本

```python
# alembic/versions/YYYYMMDD_add_dish_embedding.py

"""Add embedding columns for semantic search

Revision ID: xxxx
Revises: yyyy
Create Date: 2025-10-23 XX:XX:XX.XXXXXX
"""
from alembic import op
import sqlalchemy as sa

revision = 'xxxx'
down_revision = 'yyyy'

def upgrade():
    # 安裝 pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # 新增欄位
    op.execute('''
        ALTER TABLE dish_detail
        ADD COLUMN IF NOT EXISTS embedding vector(1536),
        ADD COLUMN IF NOT EXISTS search_text TEXT
    ''')

    # 建立索引
    op.execute('''
        CREATE INDEX IF NOT EXISTS dish_embedding_hnsw_idx
        ON dish_detail
        USING hnsw (embedding vector_cosine_ops)
    ''')

def downgrade():
    op.execute('DROP INDEX IF EXISTS dish_embedding_hnsw_idx')
    op.execute('ALTER TABLE dish_detail DROP COLUMN IF EXISTS embedding')
    op.execute('ALTER TABLE dish_detail DROP COLUMN IF EXISTS search_text')
```

---

## 🚀 階段三：搜尋 API

### 3.1 建立語義搜尋服務

**檔案**: `app/modules/menu/semantic_search.py`

```python
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text
import openai

def semantic_search(
    db: Session,
    query: str,
    tags: Optional[List[str]] = None,
    limit: int = 10,
    similarity_threshold: float = 0.7
) -> List[Dict]:
    """
    語義搜尋菜品

    Args:
        db: 資料庫 session
        query: 搜尋查詢（自然語言）
        tags: 標籤過濾（可選）
        limit: 返回結果數量
        similarity_threshold: 相似度閾值 (0-1)

    Returns:
        List of dishes with similarity scores
    """

    # 1. 將查詢轉換為 embedding
    query_embedding = generate_query_embedding(query)

    # 2. 構建 SQL 查詢
    sql = """
        SELECT
            d.id,
            d.name,
            dd.description,
            dd.tags,
            dd.image_url,
            1 - (dd.embedding <=> :query_embedding::vector) AS similarity
        FROM dish d
        JOIN dish_detail dd ON d.id = dd.dish_id
        WHERE dd.embedding IS NOT NULL
    """

    # 3. 添加標籤過濾（如果指定）
    if tags:
        sql += " AND dd.tags && :tags"  # PostgreSQL array overlap operator

    # 4. 添加相似度閾值和排序
    sql += """
        AND (1 - (dd.embedding <=> :query_embedding::vector)) >= :threshold
        ORDER BY similarity DESC
        LIMIT :limit
    """

    # 5. 執行查詢
    params = {
        'query_embedding': query_embedding,
        'threshold': similarity_threshold,
        'limit': limit
    }
    if tags:
        params['tags'] = tags

    result = db.execute(text(sql), params).mappings().all()

    return [dict(row) for row in result]


def generate_query_embedding(query: str) -> List[float]:
    """生成查詢的 embedding 向量"""
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=query,
        encoding_format="float"
    )
    return response.data[0].embedding


def get_similar_dishes(
    db: Session,
    dish_id: int,
    limit: int = 5
) -> List[Dict]:
    """
    根據菜品 ID 找尋相似菜品（推薦功能）

    Args:
        db: 資料庫 session
        dish_id: 參考菜品 ID
        limit: 返回結果數量

    Returns:
        List of similar dishes
    """
    sql = """
        WITH target_dish AS (
            SELECT embedding
            FROM dish_detail
            WHERE dish_id = :dish_id
        )
        SELECT
            d.id,
            d.name,
            dd.description,
            dd.image_url,
            1 - (dd.embedding <=> (SELECT embedding FROM target_dish)) AS similarity
        FROM dish d
        JOIN dish_detail dd ON d.id = dd.dish_id
        WHERE d.id != :dish_id
          AND dd.embedding IS NOT NULL
        ORDER BY similarity DESC
        LIMIT :limit
    """

    result = db.execute(
        text(sql),
        {'dish_id': dish_id, 'limit': limit}
    ).mappings().all()

    return [dict(row) for row in result]
```

### 3.2 新增 API 路由

**檔案**: `app/modules/menu/router.py`（修改）

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db import get_db
from .semantic_search import semantic_search, get_similar_dishes

router = APIRouter()

# ... 現有路由 ...

@router.get("/api/menu/search")
def search_dishes(
    query: str = Query(..., description="搜尋查詢（自然語言）"),
    tags: Optional[List[str]] = Query(None, description="標籤過濾"),
    limit: int = Query(10, ge=1, le=50, description="返回結果數量"),
    db: Session = Depends(get_db)
):
    """
    語義搜尋菜品

    範例查詢：
    - "清爽的開胃菜"
    - "適合宴客的海鮮"
    - "經典台菜"
    """
    results = semantic_search(db, query, tags, limit)

    return {
        "query": query,
        "count": len(results),
        "results": results
    }


@router.get("/api/menu/dishes/{dish_id}/similar")
def get_similar(
    dish_id: int,
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    取得相似菜品推薦

    用途：在菜品詳細頁面顯示「您可能也喜歡」
    """
    similar = get_similar_dishes(db, dish_id, limit)

    return {
        "dish_id": dish_id,
        "similar_dishes": similar
    }
```

### 3.3 API 使用範例

**請求 1：自然語言搜尋**
```bash
GET /api/menu/search?query=清爽的開胃菜&limit=5

# 回應
{
  "query": "清爽的開胃菜",
  "count": 5,
  "results": [
    {
      "id": 1,
      "name": "烏魚子",
      "description": "阿霞飯店的烏魚子以傳統手藝醃製...",
      "tags": ["海鮮類", "點心", "小菜", "冷食"],
      "image_url": "...",
      "similarity": 0.87
    },
    ...
  ]
}
```

**請求 2：標籤過濾搜尋**
```bash
GET /api/menu/search?query=經典料理&tags=海鮮類&tags=熱食&limit=10
```

**請求 3：相似菜品推薦**
```bash
GET /api/menu/dishes/1/similar?limit=5

# 回應
{
  "dish_id": 1,
  "similar_dishes": [
    {
      "id": 5,
      "name": "粉腸",
      "description": "...",
      "similarity": 0.82
    },
    ...
  ]
}
```

---

## 💻 階段四：前端整合（選配）

### 4.1 Vue SPA 智能搜尋元件

**檔案**: `static/src/components/MenuSearch.vue`

```vue
<template>
  <div class="menu-search">
    <!-- 搜尋框 -->
    <div class="search-box">
      <input
        v-model="query"
        @input="onSearchInput"
        placeholder="試試看：「清爽的開胃菜」或「適合宴客的海鮮」"
        class="search-input"
      />
      <button @click="handleSearch" class="search-btn">搜尋</button>
    </div>

    <!-- 標籤篩選器 -->
    <div class="tag-filters">
      <button
        v-for="tag in availableTags"
        :key="tag"
        :class="{ active: selectedTags.includes(tag) }"
        @click="toggleTag(tag)"
      >
        {{ tag }}
      </button>
    </div>

    <!-- 搜尋結果 -->
    <div v-if="loading" class="loading">搜尋中...</div>

    <div v-else-if="results.length > 0" class="results">
      <div
        v-for="dish in results"
        :key="dish.id"
        class="dish-card"
      >
        <img :src="dish.image_url" :alt="dish.name" />
        <h3>{{ dish.name }}</h3>
        <p>{{ dish.description }}</p>
        <div class="similarity">相似度: {{ (dish.similarity * 100).toFixed(0) }}%</div>
        <div class="tags">
          <span v-for="tag in dish.tags" :key="tag" class="tag">{{ tag }}</span>
        </div>
      </div>
    </div>

    <div v-else-if="query" class="no-results">
      沒有找到符合的菜品，試試其他關鍵字？
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { debounce } from 'lodash-es'

const query = ref('')
const selectedTags = ref([])
const results = ref([])
const loading = ref(false)

const availableTags = ref([
  '海鮮類', '肉類', '蔬菜', '湯品', '點心',
  '冷食', '熱食', '桌菜', '台菜'
])

// 防抖搜尋
const onSearchInput = debounce(async () => {
  if (query.value.length >= 2) {
    await handleSearch()
  }
}, 500)

const handleSearch = async () => {
  loading.value = true

  try {
    const params = new URLSearchParams({
      query: query.value,
      limit: 10
    })

    // 添加標籤參數
    selectedTags.value.forEach(tag => {
      params.append('tags', tag)
    })

    const response = await fetch(`/api/menu/search?${params}`)
    const data = await response.json()
    results.value = data.results
  } catch (error) {
    console.error('搜尋失敗:', error)
  } finally {
    loading.value = false
  }
}

const toggleTag = (tag) => {
  const index = selectedTags.value.indexOf(tag)
  if (index > -1) {
    selectedTags.value.splice(index, 1)
  } else {
    selectedTags.value.push(tag)
  }
  handleSearch()
}
</script>

<style scoped>
.menu-search {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

.search-box {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.search-input {
  flex: 1;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  border: 2px solid #ddd;
  border-radius: 8px;
}

.search-btn {
  padding: 0.75rem 2rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.tag-filters {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 2rem;
}

.tag-filters button {
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  background: white;
  border-radius: 20px;
  cursor: pointer;
}

.tag-filters button.active {
  background: #007bff;
  color: white;
}

.results {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}

.dish-card {
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 1rem;
  transition: transform 0.2s;
}

.dish-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.similarity {
  color: #28a745;
  font-weight: bold;
  margin-top: 0.5rem;
}

.tags {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.tag {
  background: #f8f9fa;
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.875rem;
}
</style>
```

### 4.2 整合到現有菜單頁面

修改 `static/src/views/Menu.vue`，新增智能搜尋功能：

```vue
<template>
  <div class="menu-page">
    <!-- 現有分類瀏覽 -->
    <CategoryBrowser />

    <!-- 新增：智能搜尋 -->
    <div class="search-section">
      <h2>智能搜尋</h2>
      <MenuSearch />
    </div>

    <!-- 現有菜單列表 -->
    <MenuList />
  </div>
</template>

<script setup>
import CategoryBrowser from '@/components/CategoryBrowser.vue'
import MenuList from '@/components/MenuList.vue'
import MenuSearch from '@/components/MenuSearch.vue'
</script>
```

---

## 📁 完整檔案結構

```
AIOrderFood/
├── docs/
│   └── RAG_implementation_plan.md          # 本文件
│
├── tool/
│   ├── dish_describer/
│   │   └── axia_dish_descriptions.json     # 原始資料（19.6MB）
│   │
│   ├── output/
│   │   └── dish_embeddings.json            # 新增：處理後的資料
│   │
│   ├── embedding_builder.py                # 新增：預處理腳本
│   └── import_embeddings.py                # 新增：資料匯入腳本
│
├── alembic/versions/
│   └── YYYYMMDD_add_dish_embedding.py      # 新增：資料庫遷移
│
├── app/modules/menu/
│   ├── __init__.py
│   ├── router.py                           # 修改：新增搜尋路由
│   ├── menu.py                             # 現有：菜單服務
│   └── semantic_search.py                  # 新增：語義搜尋服務
│
├── static/src/
│   ├── components/
│   │   └── MenuSearch.vue                  # 新增：搜尋元件（選配）
│   └── views/
│       └── Menu.vue                        # 修改：整合搜尋功能（選配）
│
├── test/
│   └── test_semantic_search.py             # 新增：測試（建議）
│
├── requirements.txt                        # 更新：新增依賴
├── .env                                    # 更新：新增 OPENAI_API_KEY
└── CLAUDE.md                               # 可選：記錄 RAG 架構
```

---

## 📦 新增依賴

### Python 依賴

更新 `requirements.txt`:

```txt
# 現有依賴
fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1
# ...

# 新增：RAG 相關
pgvector==0.2.4              # PostgreSQL vector extension
openai==1.12.0               # OpenAI API
numpy==1.26.3                # 向量運算
python-dotenv==1.0.0         # 環境變數（如已有可忽略）
```

### JavaScript 依賴（前端選配）

如果實作前端整合：

```bash
cd static
npm install lodash-es  # 用於 debounce
```

---

## 🔑 環境變數設定

在 `.env` 中新增：

```bash
# OpenAI API（用於生成 embedding）
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx

# 可選：調整 embedding 模型
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

---

## ⏱️ 開發時程預估

### 階段一：資料預處理（2-3 小時）
- [ ] 撰寫 `embedding_builder.py` 腳本
- [ ] 實作標籤正規化邏輯
- [ ] 整合 OpenAI API
- [ ] 測試資料清理流程
- [ ] 生成 embedding 並輸出

### 階段二：資料庫遷移（1 小時）
- [ ] 建立 Alembic 遷移腳本
- [ ] 在測試環境執行遷移
- [ ] 撰寫 `import_embeddings.py`
- [ ] 匯入資料並驗證

### 階段三：搜尋 API（2-3 小時）
- [ ] 實作 `semantic_search.py` 服務
- [ ] 新增 API 路由
- [ ] 撰寫單元測試
- [ ] API 測試與調優

### 階段四：前端整合（4-6 小時，選配）
- [ ] 建立 `MenuSearch.vue` 元件
- [ ] 整合到現有菜單頁面
- [ ] UI/UX 優化
- [ ] 測試與除錯

**總計**：
- **核心功能（階段 1-3）**：1 個工作天
- **含前端整合**：2 個工作天

---

## 🎯 預期達成效果

### ✅ 功能效果

| 功能 | 效果說明 | 範例 |
|------|---------|------|
| **語義搜尋** | 理解自然語言查詢意圖 | 「清爽的開胃菜」→ 烏魚子、粉腸 |
| **標籤組合** | 多條件精準過濾 | 「海鮮 + 冷食」→ 烏魚子 |
| **相似推薦** | 基於向量相似度推薦 | 點擊「紅蟳米糕」→ 推薦「砂鍋鴨」 |
| **容錯搜尋** | 拼寫錯誤、同義詞理解 | 「乌鱼子」→ 烏魚子 |
| **跨語言** | 支援英文查詢（embedding 特性） | "seafood appetizer" → 烏魚子 |

### 📊 性能指標

- **查詢速度**: < 100ms（HNSW 索引）
- **準確率**: 85-90%（基於 embedding 相似度）
- **可擴展性**: 支援至 10 萬筆菜品
- **成本**: $0.02/次更新（僅更新時產生）

### 🔄 與現有系統整合

- ✅ 無侵入式設計（不影響現有 API）
- ✅ 共用資料庫連接池
- ✅ 相同的認證與會話機制
- ✅ 可選擇性啟用（透過 feature flag）

---

## 🧪 測試策略

### 單元測試範例

**檔案**: `test/test_semantic_search.py`

```python
import pytest
from app.modules.menu.semantic_search import semantic_search, get_similar_dishes
from app.db import get_db

def test_semantic_search_basic(test_db):
    """測試基本語義搜尋"""
    results = semantic_search(
        db=test_db,
        query="清爽的海鮮",
        limit=5
    )

    assert len(results) > 0
    assert results[0]['similarity'] > 0.7
    assert '海鮮' in str(results[0]['tags'])

def test_semantic_search_with_tags(test_db):
    """測試標籤過濾搜尋"""
    results = semantic_search(
        db=test_db,
        query="開胃菜",
        tags=["冷食"],
        limit=5
    )

    assert all("冷食" in dish['tags'] for dish in results)

def test_similar_dishes(test_db):
    """測試相似菜品推薦"""
    # 假設烏魚子的 dish_id 為 1
    similar = get_similar_dishes(
        db=test_db,
        dish_id=1,
        limit=5
    )

    assert len(similar) == 5
    assert all(dish['id'] != 1 for dish in similar)  # 不包含自己

def test_embedding_quality(test_db):
    """測試 embedding 向量品質"""
    # 檢查向量非零
    result = test_db.execute(
        "SELECT embedding FROM dish_detail WHERE embedding IS NOT NULL LIMIT 1"
    ).scalar()

    assert result is not None
    assert len(result) == 1536
    assert sum(result) != 0  # 非零向量
```

### API 整合測試

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_search_endpoint():
    """測試搜尋 API 端點"""
    response = client.get(
        "/api/menu/search",
        params={"query": "清爽的開胃菜", "limit": 5}
    )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) <= 5

def test_similar_endpoint():
    """測試相似推薦 API 端點"""
    response = client.get("/api/menu/dishes/1/similar")

    assert response.status_code == 200
    data = response.json()
    assert "similar_dishes" in data
```

---

## 🚨 常見問題與解決方案

### Q1: pgvector 安裝失敗？
**解決方案**：
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-server-dev-all
pip install pgvector

# macOS
brew install postgresql
pip install pgvector

# 或使用 Docker
docker run -d \
  -e POSTGRES_PASSWORD=yourpassword \
  -p 5432:5432 \
  ankane/pgvector
```

### Q2: Embedding 生成速度慢？
**解決方案**：
- 使用批量 API（一次最多 2048 個輸入）
- 本地快取已處理的 embedding
- 考慮使用 sentence-transformers（本地模型）

### Q3: 查詢結果不準確？
**調優方向**：
1. 調整 `similarity_threshold`（預設 0.7）
2. 改善 `search_text` 組合方式（增加權重）
3. 微調標籤分類
4. 使用混合搜尋（BM25 + Vector）

### Q4: 成本控制？
**最佳實踐**：
- 預先生成所有 embedding（一次性成本）
- 使用 prompt caching（查詢端）
- 考慮切換到本地模型（如 multilingual-e5）

---

## 🔄 未來擴展方向

### 短期（1-3 個月）
- [ ] 新增搜尋日誌分析（了解用戶搜尋習慣）
- [ ] 實作搜尋建議（autocomplete）
- [ ] 整合到 LINE Bot 對話流程

### 中期（3-6 個月）
- [ ] 多模態搜尋（上傳菜品圖片找相似菜）
- [ ] 個人化推薦（基於訂單歷史）
- [ ] A/B 測試框架（比較不同 embedding 模型）

### 長期（6-12 個月）
- [ ] 混合搜尋（Elasticsearch + pgvector）
- [ ] 實時更新索引
- [ ] 多語言支援（英文、日文菜單）

---

## 📚 參考資源

- [pgvector 官方文檔](https://github.com/pgvector/pgvector)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [PostgreSQL Vector Search Best Practices](https://github.com/pgvector/pgvector#best-practices)
- [LangChain + pgvector 整合](https://python.langchain.com/docs/integrations/vectorstores/pgvector)

---

## 📝 附錄：標籤分類建議

建議將標籤整理為以下層級：

```
食材分類：
  - 海鮮類
  - 肉類
  - 蔬菜類
  - 蛋豆類

烹飪方式：
  - 炒
  - 蒸
  - 煮
  - 炸
  - 烤

溫度：
  - 熱食
  - 冷食

菜式類型：
  - 點心
  - 小菜
  - 主菜
  - 湯品
  - 甜點

適用場合：
  - 桌菜
  - 宴席
  - 家常
```

---

**文件版本**: v1.0
**最後更新**: 2025-10-23
**維護者**: Claude Code
**狀態**: 待執行
