"""
AI 聊天與推薦核心邏輯（最終穩定版 v8-service）
- 支援 LLM 意圖判斷 / 忌口記憶 / 多輪推薦
- 完全相容 router.py
"""

import os, re, json, sqlite3, tempfile
from contextvars import ContextVar
from typing import TypedDict, Annotated, Any, Dict, List, Literal, Optional, Tuple
from datetime import date, timedelta
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from sqlalchemy import text
from sqlalchemy.orm import Session
from loguru import logger

from .exceptions import DatabaseConnectionError, AIServiceError, WhisperServiceError

load_dotenv()


# ==========================================================
# 🔧 Context Variables（用於傳遞 db session）
# ==========================================================
_db_context: ContextVar[Optional[Session]] = ContextVar('db_context', default=None)

def set_db_context(db: Session) -> None:
    """
    設置當前上下文的數據庫 session

    使用 contextvars 傳遞 db session，支援異步和多線程環境。

    Args:
        db: SQLAlchemy Session 實例
    """
    _db_context.set(db)

def get_db_context() -> Optional[Session]:
    """
    獲取當前上下文的數據庫 session

    Returns:
        當前的 SQLAlchemy Session，如果未設置則返回 None
    """
    return _db_context.get()


# ==========================================================
# 🔧 模型初始化（延遲載入以避免 Pydantic 初始化問題）
# ==========================================================
_llm = None
_llm_intent = None

def get_llm():
    """取得主要 LLM 模型（延遲載入）"""
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.6)
    return _llm

def get_llm_intent():
    """取得意圖分析 LLM 模型（延遲載入）"""
    global _llm_intent
    if _llm_intent is None:
        _llm_intent = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return _llm_intent


# ==========================================================
# 🗃️ 數據庫查詢函數
# ==========================================================
def fetch_dish_by_name(db: Session, dish_name: str) -> Optional[Dict[str, Any]]:
    """
    根據菜名從數據庫查詢完整的菜品資訊（便捷包裝函數）

    此函數是 fetch_dishes_by_names() 的便捷包裝，
    內部統一使用批量查詢邏輯，避免代碼重複。

    Args:
        db: SQLAlchemy Session
        dish_name: 菜品名稱

    Returns:
        菜品資訊字典，如果找不到則返回 None

    Note:
        對於查詢多個菜品，直接使用 fetch_dishes_by_names() 以獲得更好性能

    Example:
        >>> dish_info = fetch_dish_by_name(db, "紅燒魚")
        >>> if dish_info:
        ...     print(dish_info["price"])
        280.0
    """
    dish_map = fetch_dishes_by_names(db, [dish_name])
    return dish_map.get(dish_name)


def fetch_dishes_by_names(db: Session, dish_names: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    批量查詢多個菜品資訊（優化版，避免 N+1 查詢問題）

    此函數使用單次 SQL 查詢獲取多個菜品的完整資訊，
    相比於在循環中多次調用 fetch_dish_by_name()，可顯著提升性能。

    Args:
        db: SQLAlchemy Session
        dish_names: 菜名列表

    Returns:
        菜名到菜品資訊的映射字典
        格式: {
            "菜名": {
                "id": int,
                "dish_id": int,
                "name": str,
                "price": float,
                "size": str,
                "image_url": str
            }
        }

    Performance:
        - N queries → 1 query
        - 對於 3 道菜: 3 次查詢 → 1 次查詢
        - 預期性能提升: 50-70%

    Example:
        >>> dish_names = ["紅燒魚", "炒青菜", "雞湯"]
        >>> dish_map = fetch_dishes_by_names(db, dish_names)
        >>> dish_map["紅燒魚"]["price"]
        280.0
    """
    if not dish_names:
        return {}

    # 使用 CTE 和窗口函數選擇每個菜品的第一個價格
    query = text("""
        WITH ranked_prices AS (
            SELECT
                d.dish_id,
                d.name_zh,
                dd.image_url,
                dp.price_id,
                dp.price_label,
                dp.price,
                ROW_NUMBER() OVER (PARTITION BY d.dish_id ORDER BY dp.price_id) as rn
            FROM dish d
            LEFT JOIN dish_detail dd ON dd.dish_id = d.dish_id
            LEFT JOIN dish_price dp ON dp.dish_id = d.dish_id
            WHERE d.name_zh = ANY(:dish_names)
        )
        SELECT
            dish_id,
            name_zh,
            image_url,
            price_id,
            price_label,
            price
        FROM ranked_prices
        WHERE rn = 1
    """)

    results = db.execute(query, {"dish_names": dish_names}).mappings().all()

    # 建立 name -> dish_info 的映射
    dish_map = {}
    for r in results:
        dish_map[r["name_zh"]] = {
            "id": r["dish_id"],
            "dish_id": r["dish_id"],
            "name": r["name_zh"],
            "price": float(r["price"]) if r["price"] else 0.0,
            "size": r["price_label"],
            "image_url": f"/images/dish/{r['dish_id']}.webp" if r["dish_id"] else "/images/default.png",
            "price_id": int(r["price_id"]) if r["price_id"] is not None else None
        }

    logger.debug(f"批量查詢菜品: 請求 {len(dish_names)} 道，找到 {len(dish_map)} 道")

    return dish_map


def fetch_forecast_coverage(db: Session) -> Tuple[Optional[date], Optional[date]]:
    r = db.execute(text("""
        SELECT
          MIN(target_date) AS min_target_date,
          MAX(target_date) AS max_target_date
        FROM integration.vw_forecast_for_llm_latest
    """)).mappings().first()
    if not r or (r["max_target_date"] is None):
        return None, None
    return r["min_target_date"], r["max_target_date"]


def fetch_forecast_for_prices(
    db: Session,
    price_ids: List[int],
    start_date: date,
    end_date: date
) -> Dict[int, List[Dict[str, Any]]]:
    if not price_ids:
        return {}
    
    rows = db.execute(text("""
        SELECT
          price_id,
          target_date,
          yhat,
          model_version,
          forecast_origin_date
        FROM integration.vw_forecast_for_llm_latest
        WHERE price_id = ANY(:price_ids)
          AND target_date BETWEEN :start_date AND :end_date
        ORDER BY price_id, target_date
    """), {
        "price_ids": price_ids,
        "start_date": start_date,
        "end_date": end_date
    }).mappings().all()
    
    out: Dict[int, List[Dict[str, Any]]] = {}
    for r in rows:
        pid = int(r["price_id"])
        out.setdefault(pid, []).append({
            "target_date": r["target_date"].isoformat(),
            "yhat": float(r["yhat"]),
            "model_version": r["model_version"],
            "forecast_origin_date": r["forecast_origin_date"].isoformat(),
        })
    return out


def enrich_recommendations_with_db_data(
    db: Session,
    recommendations: List[Dict],
    default_reason: str = "精選推薦"
) -> List[Dict]:
    """
    從數據庫查詢完整菜品資訊並豐富推薦列表

    此函數會：
    1. 批量查詢所有推薦菜品的完整資訊
    2. 過濾掉數據庫中不存在的菜品
    3. 保留 LLM 生成的原始推薦理由
    4. 記錄詳細的 debug 日誌

    Args:
        db: SQLAlchemy Session
        recommendations: LLM 生成的推薦列表，每項至少包含 {"name": str, "reason": str}
        default_reason: 當推薦理由為空時使用的預設值

    Returns:
        包含完整數據庫資訊的推薦列表（只保留存在於數據庫中的菜品）

    Example:
        >>> recs = [{"name": "紅燒魚", "reason": "美味"}]
        >>> enriched = enrich_recommendations_with_db_data(db, recs)
        >>> enriched[0].keys()
        dict_keys(['name', 'reason', 'id', 'dish_id', 'price', 'size', 'image_url'])
    """
    if not recommendations:
        return []

    # 批量查詢所有菜品
    dish_names = [r.get("name", "") for r in recommendations]
    dish_map = fetch_dishes_by_names(db, dish_names)

    valid_recommendations = []
    for r in recommendations:
        dish_name = r.get("name", "")
        dish_info = dish_map.get(dish_name)

        if dish_info:
            # 保存原始推薦理由
            original_reason = r.get("reason", default_reason)

            # 創建新的推薦字典（避免修改原始參數）
            enriched = {
                **dish_info,
                "reason": original_reason if original_reason else default_reason
            }

            valid_recommendations.append(enriched)
            logger.debug(
                f"菜品資訊已載入: {enriched['name']} → "
                f"id={enriched['id']}, price={enriched['price']}, size={enriched.get('size', 'N/A')}, "
                f"reason='{enriched['reason']}'"
            )
        else:
            logger.warning(f"找不到菜品: {dish_name} (已從推薦中移除)")

    return valid_recommendations


def fetch_existing_forecast_price_ids(db: Session, price_ids: List[int]) -> set[int]:
    if not price_ids:
        return set()

    rows = db.execute(text("""
        SELECT DISTINCT price_id
        FROM integration.vw_forecast_for_llm_latest
        WHERE price_id = ANY(:price_ids)
    """), {"price_ids": price_ids}).mappings().all()

    return {int(r["price_id"]) for r in rows}


def attach_forecast_to_recommendations(
    db: Session,
    recs: List[Dict[str, Any]],
    *,
    horizon_days: int = 6,
    start_from: Optional[date] = None,
) -> List[Dict[str, Any]]:
    if not recs:
        return recs

    # 1) 決定推薦日（先用 today；你也可以改成 tomorrow）
    start = start_from or date.today()
    end = start + timedelta(days=horizon_days - 1)

    # 2) 用 coverage gate，避免超出你現有 forecast 範圍
    _, max_td = fetch_forecast_coverage(db)
    if max_td is None:
        # view 裡完全沒有任何 forecast
        for r in recs:
            r["forecast_status"] = "missing"
        return recs

    # ✅ 如果今天已經超出 forecast coverage：
    #    - 有出現在 view 的 price_id：代表「曾有預測，但不覆蓋今天」→ stale
    #    - 沒出現在 view 的 price_id：代表「根本沒有預測」→ missing
    if start > max_td:
        price_ids = [int(r["price_id"]) for r in recs if r.get("price_id") is not None]
        existing = fetch_existing_forecast_price_ids(db, price_ids)

        for r in recs:
            pid = r.get("price_id")
            if pid is None:
                r["forecast_status"] = "missing"
            else:
                r["forecast_status"] = "stale" if int(pid) in existing else "missing"
        return recs

    # clamp end
    if end > max_td:
        end = max_td

    # 3) 批次查 forecast（coverage 內）
    price_ids = [int(r["price_id"]) for r in recs if r.get("price_id") is not None]
    fc_map = fetch_forecast_for_prices(db, price_ids, start, end)

    # 4) attach
    for r in recs:
        pid = r.get("price_id")
        if pid is None:
            r["forecast_status"] = "missing"
            continue

        series = fc_map.get(int(pid))
        if series:
            r["forecast_6d"] = series
            r["forecast_status"] = "ok"
        else:
            # 在 coverage 內查不到，通常代表：policy/mapping/資料缺漏
            r["forecast_status"] = "missing"

    return recs

# ==========================================================
# 🧠 狀態結構
# ==========================================================
class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str | None
    intent: str | None
    memory_context: dict | None
    response: dict | None
    menu: list | None


# ==========================================================
# 🎯 節點 1：語意意圖分析（LLM 驅動）
# ==========================================================
def analyze_intent_node(state: GraphState) -> GraphState:
    msg: str = state["messages"][-1].content.strip()

    # === 🔹 直接處理「我不吃什麼」查詢，不交給 LLM ===
    if re.fullmatch(r"我不吃什麼", msg):
        memory: Dict[str, Any] = state.get("memory_context", {}) or {}
        avoid: List[str] = memory.get("avoid", [])
        if avoid:
            reply = f"目前記得您不吃：{'、'.join(avoid)}。"
        else:
            reply = "目前沒有記錄任何忌口喔。"
        logger.debug(f"查詢忌口清單: {avoid}")
        return {
            "messages": [AIMessage(content=reply)],
            "response": {"message": reply},
            "intent": "CHAT",
            "memory_context": memory
        }

    system_prompt = f"""
                      你是錦霞樓的智能推薦助理。
                      請判斷使用者輸入的意圖類別，只能選擇以下之一：
                      FILTER / BUDGET / RECOMMEND / QUERY / CHAT, 並以 JSON 格式輸出。
                      請分類為以下之一：
                      1. FILTER（忌口或記憶管理）：
                        - 使用者說「我不吃X」、「不喜歡X」、「對X過敏」。
                        - 或是詢問「我不吃什麼」、「我不吃啥」、「有哪些忌口」。
                        - 或是要求「忘記一切」、「清除記憶」、「重置忌口」。
                        以上所有都屬於 FILTER。
                      2. BUDGET — 使用者提到「預算、每人幾元、幾個人」等。
                      3. RECOMMEND — 想要餐點推薦。
                      4. QUERY — 詢問某道菜的資訊。
                      5. CHAT — 一般對話。
                      輸入訊息：「{msg}」
                      輸出範例：
                      {{"intent": "FILTER", "reasoning": "使用者提到不吃牛肉"}}
                      """
    try:
        result: Any = get_llm_intent().invoke([{"role": "system", "content": system_prompt}])
        data: Dict[str, Any] = json.loads(result.content)
        intent: str = data.get("intent", "CHAT").upper()
    except Exception:
        intent: str = "CHAT"

    logger.info(f"意圖檢測: {intent} | 訊息: {msg}")
    return {"intent": intent}


# ==========================================================
# 🚫 節點 2：忌口處理
# ==========================================================
def filter_node(state: GraphState) -> GraphState:
    msg: str = state["messages"][-1].content.strip()
    msg_lower: str = msg.lower()

    memory: Dict[str, Any] = state.get("memory_context", {}) or {}
    avoid: List[str] = memory.get("avoid", [])

    # === ① 忘記所有/忘記一切/清除記憶 ===
    if re.search(r"(忘記|清除|重置)(所有|一切|記憶|忌口)", msg_lower):
        memory.clear()
        reply = "好的，已經清空所有忌口記錄。"
        logger.info("記憶已清除")
        return {
            "memory_context": memory,
            "intent": "CHAT",
            "messages": [AIMessage(content=reply)],
            "response": {"message": reply},
        }

    # === ② 查詢目前忌口：「我不吃什麼 / 我不吃啥 / 我有哪些忌口」===
    if re.search(r"(我)?不吃(什麼|啥)|有(哪些|什麼)忌口", msg_lower):
        if avoid:
            reply = f"目前記得您不吃：{'、'.join(avoid)}。"
        else:
            reply = "目前沒有記錄任何忌口喔。"
        logger.debug(f"查詢忌口清單: {avoid}")
        return {
            "memory_context": memory,
            "intent": "CHAT",
            "messages": [AIMessage(content=reply)],
            "response": {"message": reply},
        }

    # === ③ 一般新增忌口 ===
    # 找出「不吃X」結構，但排除上面查詢情況
    matches = re.findall(r"不吃([A-Za-z0-9\u4e00-\u9fff]+)", msg)
    if matches:
        avoid.extend(matches)
        memory["avoid"] = list(set(avoid))
        reply = f"好的，我會記得您不吃 {'、'.join(memory['avoid'])}。"
        logger.info(f"更新忌口清單: {memory['avoid']}")
        return {
            "memory_context": memory,
            "intent": "RECOMMEND",
            "messages": [AIMessage(content=reply)],
            "response": {"message": reply},
        }

    # === ④ 萬一沒有抓到任何關鍵字，回預設 ===
    return {
        "memory_context": memory,
        "intent": "CHAT",
        "messages": [AIMessage(content='了解～')],
        "response": {"message": '了解～'}
    }



# ==========================================================
# 🔢 輔助函數：中文數字解析
# ==========================================================
def parse_num(txt: str) -> Optional[int]:
    """
    強化版中文數字轉換器

    支援純數字、中文數字和混合格式。優先提取第一個找到的數字。

    Args:
        txt: 包含數字的字串（可能包含其他文字）

    Returns:
        解析出的數字，失敗時返回 None

    Examples:
        >>> parse_num("3")
        3
        >>> parse_num("三")
        3
        >>> parse_num("十")
        10
        >>> parse_num("我要3份")
        3
        >>> parse_num("沒有數字")
        None
        >>> parse_num("0")
        0
        >>> parse_num("零")
        0
    """
    if not txt:
        return None

    txt = txt.strip()
    txt = txt.replace("兩", "二")

    # 優先嘗試提取純數字（阿拉伯數字）
    arabic_match = re.search(r'\d+', txt)
    if arabic_match:
        return int(arabic_match.group())

    # 特殊處理 "零"
    if txt == "零":
        return 0

    # 若無阿拉伯數字，則解析中文數字
    map_ = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    unit_map = {"十": 10, "百": 100, "千": 1000, "萬": 10000}

    # 檢查是否包含中文數字字符
    has_chinese_num = any(ch in map_ or ch in unit_map for ch in txt)
    if not has_chinese_num:
        return None

    # 檢測是否有單位字符（如十、百、千、萬）
    has_unit = any(ch in unit_map for ch in txt)

    # 如果沒有單位字符，只是連續的中文數字（如"一二三"），返回第一個
    if not has_unit:
        for ch in txt:
            if ch in map_:
                return map_[ch]

    # 有單位字符時，進行完整解析
    num = 0
    current = 0
    for ch in txt:
        if ch in map_:
            current = map_[ch]
        elif ch in unit_map:
            if current == 0:
                current = 1
            num += current * unit_map[ch]
            current = 0
    num += current

    # 例如 "兩萬五" -> 20000 + 5
    if "萬" in txt and not txt.endswith("萬"):
        m = re.search(r"萬([一二三四五六七八九\d]+)", txt)
        if m:
            tail = m.group(1)
            tail_num = parse_num(tail)
            if tail_num:
                num += tail_num

    return num if num >= 0 else None


# ==========================================================
# 💰 節點 3：預算推薦
# ==========================================================
def budget_node(state: GraphState) -> GraphState:
    msg: str = state["messages"][-1].content.strip()
    menu: List[Dict[str, Any]] = state.get("menu", []) or []

    # === 1️⃣ 判斷語意屬性 ===
    has_total_budget: bool = bool(re.search(r"(\d+|[一二兩三四五六七八九十萬千]+)\s*(?:元|塊|NT|新台幣)", msg))
    has_people: bool = bool(re.search(r"([一二兩三四五六七八九十\d]+)\s*(?:位|個)?人", msg))
    has_per_person: bool = bool(re.search(r"(?:每人|人均|人)\s*([一二兩三四五六七八九十\d]+)", msg))


    # === 2️⃣ 根據語意自動選路線 ===
    if has_total_budget and not has_per_person:
        # 🎯 總預算模式
        m_total: Optional[re.Match[str]] = re.search(r"([一二兩三四五六七八九十\d萬千]+)\s*(?:元|塊|NT|新台幣)", msg)
        total: int = parse_num(m_total.group(1)) if m_total else 1000
        people: int = 4  # 給模型參考的預設人數
        per_person: int = total // people
        plan_mode: str = "總預算模式"
    else:
        # 👥 人均預算模式
        m_people: Optional[re.Match[str]] = re.search(r"([一二兩三四五六七八九十\d]+)\s*(?:位|個)?人", msg)
        m_budget: Optional[re.Match[str]] = re.search(r"(?:每人|人均|人)\s*([一二兩三四五六七八九十\d]+)", msg)
        people: int = parse_num(m_people.group(1)) if m_people else 2
        per_person: int = parse_num(m_budget.group(1)) if m_budget else 200
        total: int = people * per_person
        plan_mode: str = "人均預算模式"

    # === 3️⃣ 組合菜單摘要 ===
    menu_summary: str = "\n".join(
        "、".join(d.get("name", "") for d in cat.get("dishes", [])[:10])
        for cat in menu
    )

    # === 4️⃣ 呼叫 LLM 生成推薦 ===
    system_prompt = f"""
你是錦霞樓的智能餐點規劃師。
目前使用【{plan_mode}】：
人數：{people} 人
每人預算：約 {per_person} 元
總預算：約 {total} 元

請根據以下菜單（節錄）：
{menu_summary}

挑選出三道最合適的菜，禁止虛構菜名。
輸出 JSON：
{{"message": "string", "recommendations": [{{"name": "string", "reason": "string"}}]}}
"""
    llm_json = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.4,
        model_kwargs={"response_format": {"type": "json_object"}}
    )

    try:
        result = llm_json.invoke([{"role": "system", "content": system_prompt}])
        data = json.loads(result.content)
    except Exception as e:
        data = {"message": f"預算推薦失敗：{e}", "recommendations": []}

    # === 5️⃣ 從數據庫查詢完整菜品資訊 ===
    db = get_db_context()
    if not db:
        logger.error("數據庫連接未設置", extra={"node": "budget_node"})
        raise DatabaseConnectionError(
            "數據庫連接錯誤：Session 未正確傳遞至 budget_node。"
            "請檢查 process_chat_request() 中的 set_db_context() 調用。"
        )

    # 從數據庫查詢完整菜品資訊並豐富推薦列表
    data["recommendations"] = enrich_recommendations_with_db_data(
        db,
        data.get("recommendations", []),
        default_reason="超值推薦"
    )
    logger.info(f"預算推薦 [{plan_mode}]: {people}人 × {per_person}元 = {total}元 | 推薦 {len(data['recommendations'])} 道菜")
    logger.debug(f"推薦數據結構: {json.dumps(data, ensure_ascii=False, indent=2)}")
    
    data["recommendations"] = attach_forecast_to_recommendations(db, data["recommendations"])

    # === 6️⃣ 回傳結果 ===
    return {
        "messages": [AIMessage(content=data.get("message", "完成預算推薦"))],
        "response": data,
    }



# ==========================================================
# 🍽️ 節點 4：智能推薦
# ==========================================================
def recommend_node(state: GraphState) -> GraphState:
    msg = state["messages"][-1].content
    menu = state.get("menu", []) or []
    memory = state.get("memory_context", {}) or {}
    avoid_terms = memory.get("avoid", [])

    # 過濾菜單
    filtered_menu = []
    for cat in menu:
        dishes = [
            d for d in cat.get("dishes", [])
            if not any(term in (d.get("name") or "") for term in avoid_terms)
        ]
        if dishes:
            filtered_menu.append({**cat, "dishes": dishes})

    # 若全部被過濾
    if not filtered_menu:
        reply = f"由於您不吃 {', '.join(avoid_terms)}，目前菜單中沒有可推薦的菜色。"
        return {"response": {"message": reply, "recommendations": []},
                "messages": [AIMessage(content=reply)]}

    # 建立摘要
    menu_summary = "\n".join(
        "、".join(d.get("name", "") for d in cat.get("dishes", [])[:10])
        for cat in filtered_menu
    )

    system_prompt = f"""
你是錦霞樓的餐點推薦助理。
使用者訊息：「{msg}」
忌口：{', '.join(avoid_terms) or '無'}
菜單如下（節錄）：
{menu_summary}

請選出三道推薦菜，禁止虛構菜名。
輸出 JSON：
{{"message": "string",
  "recommendations": [{{"name":"string","reason":"string"}}]
}}
"""
    llm_json = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    try:
        result = llm_json.invoke([{"role": "system", "content": system_prompt}])
        data = json.loads(result.content)
    except Exception as e:
        data = {"message": f"推薦失敗：{e}", "recommendations": []}

    # 從數據庫查詢完整菜品資訊
    db = get_db_context()
    if not db:
        logger.error("數據庫連接未設置", extra={"node": "recommend_node"})
        raise DatabaseConnectionError(
            "數據庫連接錯誤：Session 未正確傳遞至 recommend_node。"
            "請檢查 process_chat_request() 中的 set_db_context() 調用。"
        )

    # 從數據庫查詢完整菜品資訊並豐富推薦列表
    data["recommendations"] = enrich_recommendations_with_db_data(
        db,
        data.get("recommendations", []),
        default_reason="精選推薦"
    )
    logger.info(f"智能推薦完成: 生成 {len(data['recommendations'])} 道菜 → {[r['name'] for r in data['recommendations']]}")
    logger.debug(f"推薦數據結構: {json.dumps(data, ensure_ascii=False, indent=2)}")

    data["recommendations"] = attach_forecast_to_recommendations(db, data["recommendations"])
    
    return {
        "messages": [AIMessage(content=data.get("message", "完成推薦"))],
        "response": data,
        "memory_context": memory,
    }


# ==========================================================
# 🗣️ 節點 5：一般聊天
# ==========================================================
def chat_node(state: GraphState) -> GraphState:
    response = get_llm().invoke(state["messages"])
    return {"messages": [response], "response": {"message": response.content}}


# ==========================================================
# 🧭 路由邏輯
# ==========================================================
def route_intent(state: GraphState) -> Literal["FILTER", "BUDGET", "RECOMMEND", "CHAT"]:
    intent = state.get("intent", "CHAT")
    if intent == "FILTER":
        return "FILTER"
    elif intent == "BUDGET":
        return "BUDGET"
    elif intent == "RECOMMEND":
        return "RECOMMEND"
    else:
        return "CHAT"


# ==========================================================
# ⚙️ Graph 組裝
# ==========================================================
memory = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
workflow = StateGraph(GraphState)

workflow.add_node("analyze_intent", analyze_intent_node)
workflow.add_node("filter", filter_node)
workflow.add_node("budget", budget_node)
workflow.add_node("recommend", recommend_node)
workflow.add_node("chat", chat_node)

workflow.add_edge("__start__", "analyze_intent")
workflow.add_conditional_edges("analyze_intent", route_intent, {
    "FILTER": "filter",
    "BUDGET": "budget",
    "RECOMMEND": "recommend",
    "CHAT": "chat",
})
workflow.add_edge("filter", "recommend")

for node in ["budget", "recommend", "chat"]:
    workflow.add_edge(node, END)

app_graph = workflow.compile(checkpointer=memory)


# ==========================================================
# 🚀 對外方法（router 直接調用）
# ==========================================================
_global_memory_context = {}

def process_chat_request(message: str, context: List[Dict[str, str]], menu: list, db: Session) -> dict:
    """
    主聊天入口

    處理使用者的聊天請求，透過 LangGraph 工作流進行意圖分析和推薦生成。

    Args:
        message: 使用者輸入的訊息
        context: 對話歷史（目前未使用，保留供未來擴展）
        menu: 完整的菜單資料
        db: SQLAlchemy Session，用於查詢菜品資訊

    Returns:
        包含回應訊息和推薦清單的字典
    """
    global _global_memory_context

    # 設置當前上下文的 db session
    set_db_context(db)

    try:
        state = {
            "messages": [HumanMessage(content=message)],
            "menu": menu,
            "memory_context": _global_memory_context,
        }
        result = app_graph.invoke(state, config={"configurable": {"thread_id": "global"}})
        if result.get("memory_context"):
            _global_memory_context = result["memory_context"]
        return result.get("response", {"message": "無回應", "recommendations": []})
    finally:
        # 清理上下文
        set_db_context(None)


# ==========================================================
# 🎧 Whisper 語音轉文字（使用 OpenAI API）
# ==========================================================
from openai import OpenAI

def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> Dict[str, str]:
    """
    使用 OpenAI Whisper API 將音訊轉換為文字

    Args:
        audio_bytes: 音訊檔案的位元組資料
        filename: 音訊檔案名稱（用於設定正確的副檔名）

    Returns:
        包含 text 和 language 的字典

    Raises:
        WhisperServiceError: 當 API 調用失敗時拋出

    Note:
        - 需要在 .env 中設定 OPENAI_API_KEY
        - 支援的格式：mp3, mp4, mpeg, mpga, m4a, wav, webm
        - 檔案大小限制：25 MB
    """
    try:
        # 初始化 OpenAI 客戶端（會自動從環境變數讀取 OPENAI_API_KEY）
        client = OpenAI()

        # 將音訊位元組寫入臨時檔案
        # OpenAI API 需要檔案物件，無法直接傳送位元組
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            # 調用 OpenAI Whisper API
            with open(tmp_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json"  # 取得詳細資訊，包含 language
                )

            # 回傳結果
            return {
                "text": transcript.text,
                "language": transcript.language if hasattr(transcript, 'language') else "unknown"
            }

        finally:
            # 清理臨時檔案
            try:
                os.remove(tmp_path)
            except Exception as cleanup_err:
                logger.warning(f"清理臨時檔案失敗: {cleanup_err}")

    except Exception as e:
        logger.error(f"OpenAI Whisper API 調用失敗: {e}", exc_info=True)
        raise WhisperServiceError(f"語音辨識服務錯誤: {str(e)}")