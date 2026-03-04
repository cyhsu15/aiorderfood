"""
URL 內容摘要整理腳本
使用 ChatGPT API 整理阿霞飯店相關的 URL 內容
"""
import json
import os
from pathlib import Path
from collections import OrderedDict
from typing import Dict, List, Optional
import time
from dotenv import load_dotenv
load_dotenv()

try:
    from openai import OpenAI
except ImportError:
    print("請先安裝 openai 套件：pip install openai")
    exit(1)


class URLContentSummarizer:
    """URL 內容摘要處理器"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化

        Args:
            api_key: OpenAI API key，若為 None 則從環境變量讀取
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError(
                "請設置 OPENAI_API_KEY 環境變量或傳入 api_key 參數\n"
                "Windows: set OPENAI_API_KEY=your-api-key\n"
                "Linux/Mac: export OPENAI_API_KEY=your-api-key"
            )

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"  # 使用較便宜的模型

    def create_prompt(self, url: str, content: str) -> str:
        """
        創建 ChatGPT 提示詞

        Args:
            url: 網頁 URL
            content: 網頁內容

        Returns:
            提示詞
        """
        prompt = f"""請分析以下網頁內容，這是關於台南「阿霞飯店」的資料。

網址：{url}

請從內容中提取：

1. **阿霞飯店簡介**（如果有）：
   - 歷史背景
   - 特色說明
   - 榮譽認證（如米其林等）

2. **餐點描述**（重點）：
   - 提取所有提到的菜色名稱
   - 每道菜的特色、口味、做法描述
   - 價格資訊（如果有）
   - 推薦理由

3. **用餐資訊**（如果有）：
   - 營業時間
   - 訂位方式
   - 地址/分店資訊

**輸出格式（JSON）**：
```json
{{
  "restaurant_intro": "阿霞飯店簡介文字...",
  "dishes": [
    {{
      "dish_name": "菜名",
      "description": "描述",
      "price": "價格（如果有）",
      "tags": ["特色標籤"]
    }}
  ],
  "dining_info": {{
    "hours": "營業時間",
    "reservation": "訂位方式",
    "location": "地址"
  }}
}}
```

**注意**：
- 只提取與阿霞飯店和餐點相關的資訊
- 忽略廣告、導航欄、其他餐廳資訊
- 如果某個欄位沒有資訊，設為 null
- 描述要簡潔精確，保留重要特色

---

網頁內容：
{content[:8000]}
"""  # 限制 content 長度避免超過 token 限制

        return prompt

    def summarize_content(self, url: str, content: str) -> Dict:
        """
        使用 ChatGPT 整理內容

        Args:
            url: 網頁 URL
            content: 網頁內容

        Returns:
            整理後的結構化資料
        """
        prompt = self.create_prompt(url, content)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一個專業的餐飲資訊整理助手，擅長從網頁內容中提取餐廳和菜色資訊。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # 降低溫度以獲得更一致的輸出
                response_format={"type": "json_object"}  # 要求 JSON 格式輸出
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"處理失敗: {url}")
            print(f"錯誤: {str(e)}")
            return {
                "error": str(e),
                "restaurant_intro": None,
                "dishes": [],
                "dining_info": None
            }

    def process_url(self, url: str, content: str, index: int, total: int) -> Dict:
        """
        處理單個 URL

        Args:
            url: URL
            content: 內容
            index: 當前索引
            total: 總數

        Returns:
            處理結果
        """
        print(f"\n[{index}/{total}] 處理: {url[:80]}...")

        # 調用 ChatGPT
        summary = self.summarize_content(url, content)

        # 組合結果
        result = {
            "url": url,
            "content_length": len(content),
            "original_content": content,
            "summary": summary,
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # 顯示摘要
        if "error" not in summary:
            dish_count = len(summary.get("dishes", []))
            print(f"  ✓ 完成！提取了 {dish_count} 道菜色資訊")

            # 安全地顯示餐廳簡介（可能是 dict/list/str）
            intro = summary.get("restaurant_intro")
            if intro:
                if isinstance(intro, str):
                    print(f"  ✓ 餐廳簡介: {intro[:50]}...")
                else:
                    # 如果不是字符串，轉換為字符串
                    intro_str = str(intro)[:50]
                    print(f"  ✓ 餐廳簡介: {intro_str}...")
        else:
            print(f"  ✗ 處理失敗: {summary['error']}")

        return result


def load_json(file_path: Path) -> dict:
    """讀取 JSON 文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: dict, file_path: Path):
    """保存為 JSON 文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_temp_results(temp_file: Path) -> tuple:
    """
    加載臨時結果

    Returns:
        (results, processed_urls_set)
    """
    if not temp_file.exists():
        return [], set()

    try:
        with open(temp_file, 'r', encoding='utf-8') as f:
            results = json.load(f)

        processed_urls = {r['url'] for r in results}
        return results, processed_urls
    except Exception as e:
        print(f"⚠️  無法讀取臨時文件: {e}")
        return [], set()


def extract_unique_urls(data: dict) -> Dict[str, dict]:
    """
    提取唯一的 URL 和內容

    Returns:
        {url: {"content": ..., "title": ..., "dish_names": [...]}}
    """
    url_map = OrderedDict()

    items = data.get('items', [])

    for item in items:
        dish_name = item.get('disg_detil', {}).get('dish_name', '')
        snippets = item.get('snippets', [])

        for snippet in snippets:
            url = snippet.get('url', '')
            if not url:
                continue

            if url not in url_map:
                url_map[url] = {
                    'content': snippet.get('content', ''),
                    'title': snippet.get('title', ''),
                    'dish_names': [dish_name]
                }
            else:
                # 記錄這個 URL 關聯的菜色
                if dish_name not in url_map[url]['dish_names']:
                    url_map[url]['dish_names'].append(dish_name)

    return url_map


def main():
    """主函數"""
    # 文件路徑
    input_file = Path(__file__).parent.parent / 'dish_describer' / 'axia_dish_descriptions.json'
    output_dir = Path(__file__).parent

    print("="*60)
    print("阿霞飯店 URL 內容摘要整理工具")
    print("="*60)

    # 檢查 API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("\n❌ 錯誤：未設置 OPENAI_API_KEY 環境變量")
        print("\n請先設置 OpenAI API Key：")
        print("  Windows PowerShell:")
        print("    $env:OPENAI_API_KEY='your-api-key-here'")
        print("  Windows CMD:")
        print("    set OPENAI_API_KEY=your-api-key-here")
        print("  Linux/Mac:")
        print("    export OPENAI_API_KEY=your-api-key-here")
        return

    # 讀取數據
    print(f"\n📖 讀取數據: {input_file}")
    data = load_json(input_file)

    # 提取唯一 URL
    print("\n🔍 提取唯一 URL...")
    url_map = extract_unique_urls(data)
    print(f"  找到 {len(url_map)} 個唯一 URL")

    # 檢查是否有臨時文件（中斷恢復）
    temp_file = output_dir / 'url_summaries_temp.json'
    existing_results, processed_urls = load_temp_results(temp_file)

    if existing_results:
        print(f"\n♻️  發現臨時文件！")
        print(f"  已處理: {len(existing_results)} 個 URL")
        print(f"  剩餘: {len(url_map) - len(processed_urls)} 個 URL")

        resume = input("\n是否從上次中斷處繼續？(yes/no): ").strip().lower()
        if resume in ['yes', 'y']:
            print(f"  ✓ 將從第 {len(existing_results) + 1} 個 URL 繼續處理")
        else:
            print("  重新開始處理")
            existing_results = []
            processed_urls = set()
    else:
        print(f"  沒有找到臨時文件，將從頭開始")

    # 計算剩餘要處理的數量
    remaining_count = len(url_map) - len(processed_urls)

    # 詢問用戶
    print("\n⚠️  注意：")
    print(f"  - 總 URL 數: {len(url_map)}")
    print(f"  - 已處理: {len(processed_urls)}")
    print(f"  - 剩餘: {remaining_count}")
    print(f"  - 使用 OpenAI API (模型: gpt-4o-mini)")
    print(f"  - 預估費用: 約 ${remaining_count * 0.001:.2f} USD")
    print(f"  - 預估時間: 約 {remaining_count * 3 / 60:.1f} 分鐘")

    if remaining_count == 0:
        print("\n✅ 所有 URL 已處理完成！")
        return

    choice = input("\n是否繼續？(yes/no) [或輸入數字只處理前 N 個]: ").strip().lower()

    if choice == 'no' or choice == 'n':
        print("已取消")
        return

    # 確定處理數量
    if choice.isdigit():
        limit = int(choice)
        print(f"\n只處理前 {limit} 個 URL")
    elif choice in ['yes', 'y']:
        limit = len(url_map)
    else:
        print("無效輸入，已取消")
        return

    # 初始化處理器
    print("\n🤖 初始化 ChatGPT...")
    summarizer = URLContentSummarizer(api_key=api_key)

    # 處理 URL
    print("\n🚀 開始處理...")
    results = existing_results.copy()  # 從已有結果開始

    processed_count = 0
    for i, (url, info) in enumerate(url_map.items(), 1):
        # 跳過已處理的 URL
        if url in processed_urls:
            continue

        # 檢查是否達到限制
        processed_count += 1
        if processed_count > limit:
            break

        # 計算實際的索引（包括之前已處理的）
        current_index = len(results) + 1

        try:
            result = summarizer.process_url(
                url=url,
                content=info['content'],
                index=current_index,
                total=len(results) + limit
            )

            # 添加額外資訊
            result['title'] = info['title']
            result['related_dishes'] = info['dish_names']

            results.append(result)

            # 每處理 10 個就保存一次（防止中斷丟失）
            if len(results) % 10 == 0:
                save_json(results, temp_file)
                print(f"\n  💾 已保存臨時結果 ({len(results)} 個)")

        except Exception as e:
            print(f"  ✗ 處理時發生錯誤: {str(e)}")
            # 記錄錯誤但繼續處理
            error_result = {
                "url": url,
                "title": info['title'],
                "content_length": len(info['content']),
                "original_content": info['content'],
                "related_dishes": info['dish_names'],
                "summary": {
                    "error": str(e),
                    "restaurant_intro": None,
                    "dishes": [],
                    "dining_info": None
                },
                "processed_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            results.append(error_result)

        # 避免 API 限流
        time.sleep(1)

    # 保存最終結果
    print("\n\n💾 保存結果...")

    # 統計成功和失敗
    success_count = sum(1 for r in results if 'error' not in r.get('summary', {}))
    error_count = len(results) - success_count

    output_data = {
        'metadata': {
            'total_urls': len(url_map),
            'processed_urls': len(results),
            'success_count': success_count,
            'error_count': error_count,
            'model': summarizer.model,
            'processed_at': time.strftime("%Y-%m-%d %H:%M:%S")
        },
        'summaries': results
    }

    output_file = output_dir / 'url_summaries.json'
    save_json(output_data, output_file)

    print(f"\n✅ 完成！")
    print(f"  總處理: {len(results)} 個 URL")
    print(f"  成功: {success_count} 個")
    print(f"  失敗: {error_count} 個")
    print(f"  結果保存至: {output_file}")

    # 統計
    total_dishes = sum(len(r['summary'].get('dishes', [])) for r in results if 'error' not in r.get('summary', {}))
    total_intros = sum(1 for r in results if r.get('summary', {}).get('restaurant_intro'))

    print(f"\n📊 統計：")
    print(f"  提取菜色資訊: {total_dishes} 筆")
    print(f"  提取餐廳簡介: {total_intros} 篇")

    # 詢問是否刪除臨時文件
    if temp_file.exists():
        delete = input("\n是否刪除臨時文件？(yes/no): ").strip().lower()
        if delete in ['yes', 'y']:
            temp_file.unlink()
            print(f"  ✓ 已刪除臨時文件")
        else:
            print(f"  ✓ 保留臨時文件: {temp_file}")


if __name__ == '__main__':
    main()
