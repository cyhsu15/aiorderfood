# -*- coding: utf-8 -*-

import os
import re
import time
import json
import csv
import argparse
from typing import List, Dict, Any, Optional, Union
import pickle

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv()
# 若未提供 OPENAI_API_KEY，為了支援本地 LM Studio，給預設值避免拋錯
os.environ.setdefault("OPENAI_API_KEY", os.getenv("LMSTUDIO_API_KEY", "lm-studio"))
# LangChain imports with version compatibility
try:
    from langchain_core.output_parsers import PydanticOutputParser
    from langchain_core.prompts import PromptTemplate
except Exception:  # pragma: no cover
    from langchain.output_parsers import PydanticOutputParser  # type: ignore
    from langchain.prompts import PromptTemplate  # type: ignore

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    from langchain.chat_models import ChatOpenAI  # type: ignore


class DishDescriber(BaseModel):
    """LLM 輸出用結構：菜名、描述、標籤。
    """

    dish_name: str = Field(..., description="菜名")
    dish_describer: str = Field(..., description="菜餚描述（自然段落、無誇飾）")
    tags: List[str] = Field(..., description="標籤列表（僅從允許清單擇取）")


class DishOutputFormet(BaseModel):
    """最終輸出格式，需保存來源網站與收集文字。

    維持使用者要求的類名與欄位拼寫（disg_detil 保留）。
    """

    disg_detil: DishDescriber = Field(..., description="菜餚描述結果")
    sources: List[str] = Field(..., description="來源網站 URL 清單")
    snippets: List[Dict[str, str]] = Field(..., description="來源網站擷取到的文字段落與中繼資訊")


def _load_allowed_tags(tags_json_path: str = "menu_tags_template.json") -> List[str]:
    """從 menu_tags_template.json 彙整所有可用標籤字串（遞迴抽取所有字串值）。"""

    def collect_strings(node: Union[Dict[str, Any], List[Any], str]) -> List[str]:
        out: List[str] = []
        if isinstance(node, str):
            s = node.strip()
            if s:
                out.append(s)
        elif isinstance(node, list):
            for it in node:
                out.extend(collect_strings(it))
        elif isinstance(node, dict):
            for v in node.values():
                out.extend(collect_strings(v))
        return out

    try:
        with open(tags_json_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        tags = collect_strings(data)
        seen = set()
        uniq: List[str] = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                uniq.append(t)
        return uniq
    except Exception:
        return []


def llm_compose_desc_with_parser(
    model_name: str,
    restaurant: str,
    dish: str,
    collected_text: str,
    allowed_tags: List[str],
    category: Optional[str] = None,
) -> DishDescriber:
    """使用 LangChain 的 PydanticOutputParser 產出 DishDescriber。"""
    # if len(collected_text) >= 11500:
    #     collected_text = collected_text[:11500]
    parser = PydanticOutputParser(pydantic_object=DishDescriber)
    format_instructions = parser.get_format_instructions()

    # System message is in the prompt body for compatibility with simple invoke
    system = (
        "你是台灣餐飲文案與考據助理，重視可信來源，避免過度渲染與誇飾；"
        "以清楚、易讀的繁體中文撰寫菜餚描述，並聚焦可被查證的作法、口感、風味與典故。"
    )

    tags_hint = ", ".join(allowed_tags[:200])  # 避免提示過長

    prompt_tmpl = PromptTemplate(
        template=(
            "{system}\n\n"
            "店家：{restaurant}\n"
            "菜名：{dish}\n"
            "分類：{category}\n\n"
            "以下為以 Selenium 爬取 DuckDuckGo 後蒐集的參考資料（可能含多個來源片段）：\n"
            "{collected}\n\n"
            "請根據以上可靠線索，用一段的通順文字撰寫 100 字以內的菜餚描述；"
            "例如:頂級烏魚子經炭火炙烤提香，融合火炒米飯，是識味人必點的職人之作。 或 干貝、花菇與豬肚慢燉熬製，湯頭濃潤、層次分明。"
            "若提供分類，請確認描述與分類一致，標籤選擇亦以分類作為優先方向。\n"
            "接著依據提供的允許標籤清單，挑選 3-7 個最貼切的標籤填入 tags。\n"
            "允許標籤清單（僅可擇取其中）：{allowed_tags}\n\n"
            "嚴格依照以下輸出格式：\n{format_instructions}"
        ),
        input_variables=["system", "restaurant", "dish", "collected", "allowed_tags", "category"],
        partial_variables={"format_instructions": format_instructions},
    )

    # 使用本地 LM Studio 端點；若未設定環境變數則預設為 http://localhost:1234/v1
    # 註：某些驅動需要 API Key，即使本地不驗證，給一個預設值可避免拋錯。
    lm_base_url = os.getenv("OPENAI_BASE_URL", os.getenv("LMSTUDIO_BASE_URL", "https://openrouter.ai/api/v1"))
    lm_api_key = os.getenv("OPEN_ROUTER_API_KEY", "no")

    llm = ChatOpenAI(
        model=model_name,
        temperature=0.6,
        base_url=lm_base_url,
        api_key=lm_api_key,
    )
    chain = prompt_tmpl | llm | parser

    prompt_value = {
        "system": system,
        "restaurant": restaurant,
        "dish": dish,
        "collected": collected_text,
        "allowed_tags": tags_hint,
        "category": category or "(未提供)",
    }
    # 第一次嘗試
    try:
        return chain.invoke(prompt_value)
    except Exception:
        # 簡單回退：直接再次請求並嘗試解析
        msg = prompt_tmpl.format(**prompt_value)
        try:
            resp = llm.invoke(msg)
            text = getattr(resp, "content", str(resp))
            return parser.parse(text)
        except Exception:
            # 最後保底：輸出最小可用結構
            return DishDescriber(dish_name=dish, dish_describer="[PARSE_ERROR] 請重試產生內容", tags=[])


CLEAN_TAGS = ["script", "style", "noscript", "header", "footer", "nav", "aside"]


def clean_html_to_text(html: str, max_len: int = 15000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in CLEAN_TAGS:
        for node in soup.find_all(tag):
            node.decompose()
    text = soup.get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def keep_related_segments(text: str, keywords: List[str], max_chars: int = 2000) -> str:
    if not text:
        return ""
    kw = [k for k in keywords if k]
    if not kw:
        return text[:max_chars]
    pattern = "|".join([re.escape(k) for k in kw])
    segments: List[str] = []
    for m in re.finditer(pattern, text, flags=re.IGNORECASE):
        s = max(0, m.start() - 180)
        e = min(len(text), m.end() + 320)
        segments.append(text[s:e])
    if not segments:
        segments = [text[:600]]
    merged = "\n...\n".join(segments)
    return merged[:max_chars]


def build_driver(headless: bool = False, user_agent: Optional[str] = None) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    if user_agent:
        options.add_argument(f"user-agent={user_agent}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"},
        )
    except Exception:
        pass
    return driver


def ddg_search(driver: webdriver.Chrome, query: str, ddg_origin: str, top_k: int, timeout: int = 20):
    url = f"{ddg_origin}/?q={query}&t=h_&ia=web"
    driver.set_page_load_timeout(timeout)
    driver.get(url)
    try:
        WebDriverWait(driver, min(15, timeout)).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "article[data-testid='result'], a.result__a")
        )
    except Exception:
        pass
    results = []
    cards = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='result']")
    for c in cards:
        try:
            a = c.find_element(By.CSS_SELECTOR, "a[data-testid='result-title-a']")
            href = a.get_attribute("href")
            title = a.text.strip()
            try:
                snippet_el = c.find_element(By.CSS_SELECTOR, "div[data-testid='result-extras']")
                snippet = snippet_el.text.strip()
            except Exception:
                snippet = ""
            if href and title:
                results.append({"url": href, "title": title, "snippet": snippet})
        except Exception:
            continue
        if len(results) >= top_k:
            break
    if len(results) < top_k:
        for a in driver.find_elements(By.CSS_SELECTOR, "a.result__a"):
            try:
                href = a.get_attribute("href")
                title = a.text.strip()
                if href and title:
                    results.append({"url": href, "title": title, "snippet": ""})
            except Exception:
                continue
            if len(results) >= top_k:
                break
    return results[:top_k]


def fetch_page_text(driver: webdriver.Chrome, url: str, timeout: int = 25) -> str:
    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        WebDriverWait(driver, min(15, timeout)).until(
            lambda d: d.find_elements(By.TAG_NAME, "body")
        )
        html = driver.page_source
        return clean_html_to_text(html)
    except Exception as e:
        return f"[ERROR] {url} -> {e}"


def load_processed_from_json(path: str) -> set:
    """從舊或新輸出檔讀取已處理菜名（容錯）。"""
    done = set()
    if not path or not os.path.exists(path):
        return done
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        for it in data.get("items", []):
            name = None
            if isinstance(it, dict):
                if "disg_detil" in it and isinstance(it["disg_detil"], dict):
                    name = it["disg_detil"].get("dish_name")
                name = name or it.get("dish")
            if name:
                done.add(str(name).strip())
    except Exception:
        pass
    return done


def _atomic_write_text(path: str, text: str, encoding: str = "utf-8") -> None:
    """原子性寫入：先寫暫存檔，再使用 os.replace 取代，避免中斷造成檔案損毀。"""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding=encoding) as f:
        f.write(text)
    os.replace(tmp, path)


def save_results_json(out_json: str, restaurant: str, items: List[DishOutputFormet]):
    payload = {
        "restaurant": restaurant,
        "count": len(items),
        "items": [json.loads(i.model_dump_json(ensure_ascii=False)) for i in items],
    }
    _atomic_write_text(out_json, json.dumps(payload, ensure_ascii=False, indent=2))


def save_results_txt(out_txt: str, items: List[DishOutputFormet]):
    """依目前結果重寫 TXT 輸出，確保可重入且不中斷也不產生重複段落。"""
    lines = []
    for idx, r in enumerate(items, 1):
        lines.append(f"第{idx}. {r.disg_detil.dish_name}：{r.disg_detil.dish_describer}")
    _atomic_write_text(out_txt, "\n".join(lines) + ("\n" if lines else ""))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="dish.csv")
    # parser.add_argument("--model", type=str, default="gpt-4o-mini")
    # parser.add_argument("--model", type=str, default="gpt-oss-20b")
    # parser.add_argument("--model", type=str, default="gpt-oss-20b@q4_k_s")
    parser.add_argument("--model", type=str, default="openai/gpt-oss-20b:free")
    # parser.add_argument("--model", type=str, default="gemma-3-12b-it@q5_k_xl")
    parser.add_argument("--restaurant", type=str, default="阿霞飯店")
    parser.add_argument("--ddg-origin", type=str, default="https://duckduckgo.com")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--page-timeout", type=int, default=25)
    parser.add_argument("--delay", type=float, default=0.8)
    parser.add_argument("--delay-page", type=float, default=1.2)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--user-agent", type=str, default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    parser.add_argument("--out-json", type=str, default="axia_dish_descriptions.json")
    parser.add_argument("--out-txt", type=str, default="axia_dish_descriptions.txt")
    parser.add_argument("--cache-json", type=str, default="")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        raise SystemExit(f"找不到輸入檔案：{args.input}")

    # 讀取 CSV（支援有表頭或無表頭）。欄位：dish/name, category
    items_in: List[Dict[str, Optional[str]]] = []
    with open(args.input, "r", encoding="utf-8", errors="ignore", newline="") as f:
        try:
            reader = csv.DictReader(f)
            if reader.fieldnames and any(h and h.lower() in ("dish", "name") for h in reader.fieldnames):
                for row in reader:
                    dish = (row.get("dish") or row.get("name") or "").strip()
                    category = (row.get("category") or row.get("cat") or "").strip() or None
                    if dish:
                        items_in.append({"dish": dish, "category": category})
            else:
                raise ValueError("no header")
        except Exception:
            f.seek(0)
            reader2 = csv.reader(f)
            for row in reader2:
                if not row:
                    continue
                dish = (row[0] if len(row) > 0 else "").strip()
                category = (row[1] if len(row) > 1 else "").strip() or None
                if dish:
                    items_in.append({"dish": dish, "category": category})

    # 去重（以 dish 名稱為鍵）
    seen_names: set = set()
    items: List[Dict[str, Optional[str]]] = []
    for it in items_in:
        if it["dish"] not in seen_names:
            seen_names.add(it["dish"])
            items.append(it)

    # 環境變數檢查（LLM）
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("請先設定 OPENAI_API_KEY 環境變數")

    allowed_tags = _load_allowed_tags("menu_tags_template.json")

    driver = build_driver(headless=args.headless, user_agent=args.user_agent)

    # 載入既有輸出（新格式），並建立 URL 快取供重用
    results: List[DishOutputFormet] = []
    url_cache: Dict[str, Dict[str, str]] = {}
    # 嘗試載入使用者提供的 url_cache.pickle。若格式為整個 JSON 結構，則轉換為 {url: snippet} 快取。
    try:
        if os.path.exists('url_cache.pickle'):
            with open('url_cache.pickle', 'rb') as handle:
                loaded = pickle.load(handle)
            if isinstance(loaded, dict) and 'items' in loaded and isinstance(loaded['items'], list):
                for it in loaded.get('items', []):
                    if not isinstance(it, dict):
                        continue
                    for snip in it.get('snippets', []):
                        if isinstance(snip, dict) and snip.get('url'):
                            url_cache[snip['url']] = {
                                'url': snip.get('url', ''),
                                'title': snip.get('title', ''),
                                'snippet': snip.get('snippet', ''),
                                'content': snip.get('content', ''),
                            }
            elif isinstance(loaded, dict):
                # 直接是 {url: {...}} 的快取格式
                url_cache = loaded  # type: ignore[assignment]
    except Exception:
        # 快取異常不影響主流程
        pass
    print(len(url_cache))
    if os.path.exists(args.out_json) and not args.no_resume:
        try:
            with open(args.out_json, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            for it in data.get("items", []):
                try:
                    dd = DishDescriber(**it.get("disg_detil", {}))
                    results.append(
                        DishOutputFormet(
                            disg_detil=dd,
                            sources=it.get("sources", []),
                            snippets=it.get("snippets", []),
                        )
                    )
                    for snip in it.get("snippets", []):
                        if isinstance(snip, dict) and snip.get("url"):
                            url_cache[snip["url"]] = {
                                "url": snip.get("url", ""),
                                "title": snip.get("title", ""),
                                "snippet": snip.get("snippet", ""),
                                "content": snip.get("content", ""),
                            }
                except Exception:
                    pass
        except Exception:
            pass

    # resume: 已處理菜名集合（從舊或新格式取）
    done = set()
    if not args.no_resume:
        done |= load_processed_from_json(args.out_json)
        if args.cache_json:
            done |= load_processed_from_json(args.cache_json)

    try:
        for entry in items:
            dish = entry["dish"]
            category = entry.get("category")
            if dish in done or any(r.disg_detil.dish_name == dish for r in results):
                print(f"[SKIP] {dish}")
                continue
            print(f"[RUN] {dish}")
            try:
                q = f"{args.restaurant} {dish}"
                search_res = ddg_search(driver, q, args.ddg_origin, top_k=args.top_k, timeout=args.page_timeout)
                packed: List[Dict[str, str]] = []
                for it in search_res:
                    url = it["url"]
                    if url in url_cache and url_cache[url].get("content"):
                        cached = url_cache[url]
                        packed.append({
                            "url": url,
                            "title": it.get("title", cached.get("title", "")),
                            "snippet": it.get("snippet", cached.get("snippet", "")),
                            "content": cached.get("content", ""),
                        })
                        continue

                    txt = fetch_page_text(driver, url, timeout=args.page_timeout)
                    related = keep_related_segments(txt, [args.restaurant, dish, category or ""])
                    item = {"url": url, "title": it.get("title", ""), "snippet": it.get("snippet", ""), "content": related}
                    packed.append(item)
                    url_cache[url] = item
                    time.sleep(args.delay_page)

                combined = "\n\n".join(
                    f"[{i+1}] {p['url']}\n{p.get('snippet','')}\n---\n{p.get('content','')}" for i, p in enumerate(packed)
                )
                combined_with_prefetch = combined

                dish_desc = llm_compose_desc_with_parser(
                    model_name=args.model,
                    restaurant=args.restaurant,
                    dish=dish,
                    collected_text=combined_with_prefetch,
                    allowed_tags=allowed_tags,
                    category=category,
                )

                out_obj = DishOutputFormet(
                    disg_detil=dish_desc,
                    sources=[p["url"] for p in packed],
                    snippets=packed,
                )
                results.append(out_obj)
                print(f"完成 {dish}：{dish_desc.dish_describer[:80]}...")
            except Exception as e:
                print(f"處理發生錯誤（{dish}）：{e}")
                fallback = DishDescriber(dish_name=dish, dish_describer=f"[ERROR] {e}", tags=[])
                results.append(DishOutputFormet(disg_detil=fallback, sources=[], snippets=[]))

            # 每完成一個菜餚就保存一次
            save_results_json(args.out_json, args.restaurant, results)
            save_results_txt(args.out_txt, results)
            time.sleep(args.delay)
    finally:
        driver.quit()

    # 收尾再次保存
    save_results_json(args.out_json, args.restaurant, results)
    save_results_txt(args.out_txt, results)
    print(f"輸出完成 JSON：{args.out_json}；TXT：{args.out_txt}")


if __name__ == "__main__":
    main()
