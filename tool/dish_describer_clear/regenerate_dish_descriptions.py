"""
使用 ChatGPT 重新產生每個餐點的描述與 TAG
讀取 axia_dish_descriptions.json、url_summaries.json 和 menu_tags_simplified.json
輸出符合 Pydantic 格式的結果
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import time
from dotenv import load_dotenv
load_dotenv()

try:
    from openai import OpenAI
except ImportError:
    print("請先安裝 openai 套件：pip install openai")
    exit(1)


class DishDescriptionRegenerator:
    """餐點描述重新產生器"""

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
        self.model = "gpt-4o-mini"

    def load_json(self, file_path: Path) -> dict:
        """讀取 JSON 文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_json(self, data: dict, file_path: Path):
        """保存為 JSON 文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def extract_allowed_tags(self, tags_data: dict) -> List[str]:
        """
        從 menu_tags_simplified.json 提取所有允許的標籤

        Args:
            tags_data: 標籤系統數據

        Returns:
            所有允許的標籤列表
        """
        allowed_tags = []

        # 提取食材類標籤
        if "食材" in tags_data:
            for category, tags in tags_data["食材"].items():
                if isinstance(tags, list):
                    allowed_tags.extend(tags)

        # 提取其他維度的標籤
        for dimension in ["口味", "烹飪方式", "菜品類型", "其他"]:
            if dimension in tags_data and "tags" in tags_data[dimension]:
                allowed_tags.extend(tags_data[dimension]["tags"])

        return allowed_tags

    def build_url_summary_map(self, url_summaries: dict) -> Dict[str, dict]:
        """
        建立 URL 到摘要的映射

        Args:
            url_summaries: url_summaries.json 的內容

        Returns:
            {url: summary_data}
        """
        url_map = {}
        for summary_item in url_summaries.get('summaries', []):
            url = summary_item.get('url')
            if url:
                url_map[url] = summary_item
        return url_map

    def create_prompt(self, dish_name: str, raw_data_list: List[dict], allowed_tags: List[str]) -> str:
        """
        創建 ChatGPT 提示詞

        Args:
            dish_name: 菜名
            raw_data_list: 原始數據列表 (包含 source, snippet, summarize)
            allowed_tags: 允許的標籤列表

        Returns:
            提示詞
        """
        # 構建來源資料文字
        sources_text = ""
        for idx, raw_data in enumerate(raw_data_list, 1):
            sources_text += f"\n### 來源 {idx}: {raw_data['source']}\n"
            sources_text += f"原始文字片段：\n{raw_data['snippet'][:500]}\n"
            if raw_data.get('summarize'):
                sources_text += f"摘要：\n{raw_data['summarize']}\n"

        allowed_tags_str = "、".join(allowed_tags)

        prompt = f"""請為台南「阿霞飯店」的菜餚「{dish_name}」撰寫描述和標籤。

**菜名**: {dish_name}

**來源資料**:
{sources_text}

**任務要求**:

1. **dish_describer** (菜餚描述):
   - 撰寫自然流暢的段落描述（2-4 句話）
   - 重點描述：食材、烹飪方式、口味特色、推薦理由
   - 語氣客觀、不誇飾、不使用行銷術語
   - 若來源資料充足，整合多個來源的資訊
   - 若來源資料不足，基於菜名和常識撰寫簡短描述

2. **tags** (標籤列表):
   - 只能從以下允許清單中選擇：{allowed_tags_str}
   - 選擇 3-7 個最相關的標籤
   - 必須包含：至少 1 個食材標籤、1 個烹飪方式標籤
   - 建議包含：口味標籤、菜品類型標籤
   - 如果是招牌菜，加上「招牌」標籤

**輸出格式 (JSON)**:
```json
{{
  "dish_name": "{dish_name}",
  "dish_describer": "菜餚描述文字...",
  "tags": ["標籤1", "標籤2", "標籤3"]
}}
```

**注意**:
- 所有內容使用繁體中文
- 描述要基於實際資料，不要編造
- 標籤必須完全符合允許清單（包含大小寫）
- 如果來源資料矛盾，以最可靠的來源為準
"""
        return prompt

    def regenerate_dish_description(
        self,
        dish_name: str,
        raw_data_list: List[dict],
        allowed_tags: List[str]
    ) -> dict:
        """
        使用 ChatGPT 重新產生菜餚描述

        Args:
            dish_name: 菜名
            raw_data_list: 原始數據列表
            allowed_tags: 允許的標籤列表

        Returns:
            {
                "dish_name": str,
                "dish_describer": str,
                "tags": List[str]
            }
        """
        prompt = self.create_prompt(dish_name, raw_data_list, allowed_tags)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一個專業的餐飲文案撰寫助手，擅長從多個來源整合資訊，撰寫客觀、準確的菜餚描述。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            # 驗證必要欄位
            if "dish_name" not in result or "dish_describer" not in result or "tags" not in result:
                raise ValueError("ChatGPT 回應缺少必要欄位")

            # 驗證標籤都在允許清單中
            invalid_tags = [tag for tag in result["tags"] if tag not in allowed_tags]
            if invalid_tags:
                print(f"  ⚠️  警告: 發現不在允許清單的標籤: {invalid_tags}")
                # 過濾掉無效標籤
                result["tags"] = [tag for tag in result["tags"] if tag in allowed_tags]

            return result

        except Exception as e:
            print(f"  ✗ ChatGPT 處理失敗: {str(e)}")
            # 返回預設值
            return {
                "dish_name": dish_name,
                "dish_describer": f"{dish_name}是阿霞飯店的特色菜餚。",
                "tags": ["經典"],
                "error": str(e)
            }

    def process_dish(
        self,
        dish_item: dict,
        url_summary_map: Dict[str, dict],
        allowed_tags: List[str],
        index: int,
        total: int
    ) -> dict:
        """
        處理單個菜品

        Args:
            dish_item: 原始菜品數據 (來自 axia_dish_descriptions.json)
            url_summary_map: URL 到摘要的映射
            allowed_tags: 允許的標籤列表
            index: 當前索引
            total: 總數

        Returns:
            符合 DishOutputFormet 格式的結果
        """
        dish_name = dish_item.get('disg_detil', {}).get('dish_name', '未知菜名')
        print(f"\n[{index}/{total}] 處理: {dish_name}")

        # 收集此菜品的所有原始數據
        raw_data_list = []
        snippets = dish_item.get('snippets', [])

        for snippet in snippets:
            url = snippet.get('url', '')
            snippet_content = snippet.get('content', '')

            # 查找對應的摘要
            summarize = ""
            if url in url_summary_map:
                summary_data = url_summary_map[url].get('summary', {})
                # 嘗試從 summary 中提取相關資訊
                if 'dishes' in summary_data:
                    # 找到與當前菜名相關的 dish 描述
                    for dish_info in summary_data['dishes']:
                        if dish_info.get('dish_name') == dish_name:
                            summarize = dish_info.get('description', '')
                            break

                # 如果沒有找到，使用 restaurant_intro 作為補充
                if not summarize and 'restaurant_intro' in summary_data:
                    intro = summary_data['restaurant_intro']
                    if isinstance(intro, str):
                        summarize = intro
                    else:
                        summarize = str(intro)

            raw_data_list.append({
                "source": url,
                "snippet": snippet_content,
                "summarize": summarize
            })

        # 使用 ChatGPT 重新產生描述
        dish_describer = self.regenerate_dish_description(
            dish_name=dish_name,
            raw_data_list=raw_data_list,
            allowed_tags=allowed_tags
        )

        # 構建輸出格式
        result = {
            "disg_detil": dish_describer,
            "dish_raw_datas": raw_data_list
        }

        # 顯示結果
        if "error" not in dish_describer:
            print(f"  ✓ 完成！")
            print(f"    描述: {dish_describer['dish_describer'][:60]}...")
            print(f"    標籤: {', '.join(dish_describer['tags'])}")
        else:
            print(f"  ✗ 使用預設值")

        return result


def main():
    """主函數"""
    print("=" * 60)
    print("阿霞飯店菜餚描述重新產生工具")
    print("=" * 60)

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

    # 文件路徑
    base_dir = Path(__file__).parent
    axia_file = base_dir.parent / 'dish_describer' / 'axia_dish_descriptions.json'
    url_summaries_file = base_dir / 'url_summaries.json'
    tags_file = base_dir / 'menu_tags_simplified.json'
    output_file = base_dir / 'dish_descriptions_regenerated.json'
    temp_file = base_dir / 'dish_descriptions_temp.json'

    # 檢查文件是否存在
    if not axia_file.exists():
        print(f"\n❌ 錯誤：找不到 {axia_file}")
        return

    if not url_summaries_file.exists():
        print(f"\n❌ 錯誤：找不到 {url_summaries_file}")
        print("請先運行 summarize_url_content.py 生成 url_summaries.json")
        return

    if not tags_file.exists():
        print(f"\n❌ 錯誤：找不到 {tags_file}")
        return

    # 初始化處理器
    print("\n🤖 初始化 ChatGPT...")
    regenerator = DishDescriptionRegenerator(api_key=api_key)

    # 讀取數據
    print(f"\n📖 讀取數據...")
    axia_data = regenerator.load_json(axia_file)
    url_summaries = regenerator.load_json(url_summaries_file)
    tags_data = regenerator.load_json(tags_file)

    # 提取允許的標籤
    allowed_tags = regenerator.extract_allowed_tags(tags_data)
    print(f"  允許的標籤數: {len(allowed_tags)}")

    # 建立 URL 摘要映射
    print(f"\n🔗 建立 URL 摘要映射...")
    url_summary_map = regenerator.build_url_summary_map(url_summaries)
    print(f"  找到 {len(url_summary_map)} 個 URL 摘要")

    # 獲取所有菜品
    all_dishes = axia_data.get('items', [])
    total_dishes = len(all_dishes)
    print(f"\n📊 總菜品數: {total_dishes}")

    # 檢查臨時文件
    existing_results = []
    processed_dish_names = set()

    if temp_file.exists():
        try:
            temp_data = regenerator.load_json(temp_file)
            existing_results = temp_data.get('items', [])
            processed_dish_names = {
                item['disg_detil']['dish_name']
                for item in existing_results
            }
            print(f"\n♻️  發現臨時文件！")
            print(f"  已處理: {len(existing_results)} 個菜品")
            print(f"  剩餘: {total_dishes - len(processed_dish_names)} 個菜品")

            resume = input("\n是否從上次中斷處繼續？(yes/no): ").strip().lower()
            if resume not in ['yes', 'y']:
                print("  重新開始處理")
                existing_results = []
                processed_dish_names = set()
        except Exception as e:
            print(f"  ⚠️  無法讀取臨時文件: {e}")
            existing_results = []
            processed_dish_names = set()

    # 計算剩餘數量
    remaining_count = total_dishes - len(processed_dish_names)

    # 預估成本
    print(f"\n⚠️  處理資訊：")
    print(f"  總菜品數: {total_dishes}")
    print(f"  已處理: {len(processed_dish_names)}")
    print(f"  剩餘: {remaining_count}")
    print(f"  使用 OpenAI API (模型: {regenerator.model})")
    print(f"  預估費用: 約 ${remaining_count * 0.002:.2f} USD")
    print(f"  預估時間: 約 {remaining_count * 3 / 60:.1f} 分鐘")

    if remaining_count == 0:
        print("\n✅ 所有菜品已處理完成！")
        return

    choice = input("\n是否繼續？(yes/no) [或輸入數字只處理前 N 個]: ").strip().lower()

    if choice == 'no' or choice == 'n':
        print("已取消")
        return

    # 確定處理數量
    if choice.isdigit():
        limit = int(choice)
        print(f"\n只處理前 {limit} 個菜品")
    elif choice in ['yes', 'y']:
        limit = total_dishes
    else:
        print("無效輸入，已取消")
        return

    # 處理菜品
    print("\n🚀 開始處理...")
    results = existing_results.copy()

    processed_count = 0
    for index, dish_item in enumerate(all_dishes, 1):
        dish_name = dish_item.get('disg_detil', {}).get('dish_name', '')

        # 跳過已處理的菜品
        if dish_name in processed_dish_names:
            continue

        # 檢查是否達到限制
        processed_count += 1
        if processed_count > limit:
            break

        try:
            result = regenerator.process_dish(
                dish_item=dish_item,
                url_summary_map=url_summary_map,
                allowed_tags=allowed_tags,
                index=len(results) + 1,
                total=len(results) + limit
            )

            results.append(result)

            # 每處理 5 個就保存一次
            if len(results) % 5 == 0:
                temp_output = {"items": results}
                regenerator.save_json(temp_output, temp_file)
                print(f"\n  💾 已保存臨時結果 ({len(results)} 個)")

        except Exception as e:
            print(f"  ✗ 處理時發生錯誤: {str(e)}")
            # 記錄錯誤但繼續處理
            error_result = {
                "disg_detil": {
                    "dish_name": dish_name,
                    "dish_describer": f"{dish_name}是阿霞飯店的特色菜餚。",
                    "tags": ["經典"],
                    "error": str(e)
                },
                "dish_raw_datas": dish_item.get('snippets', [])
            }
            results.append(error_result)

        # 避免 API 限流
        time.sleep(1)

    # 保存最終結果
    print("\n\n💾 保存結果...")

    # 統計
    success_count = sum(
        1 for r in results
        if 'error' not in r.get('disg_detil', {})
    )
    error_count = len(results) - success_count

    output_data = {
        "metadata": {
            "total_dishes": total_dishes,
            "processed_dishes": len(results),
            "success_count": success_count,
            "error_count": error_count,
            "model": regenerator.model,
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "items": results
    }

    regenerator.save_json(output_data, output_file)

    print(f"\n✅ 完成！")
    print(f"  總處理: {len(results)} 個菜品")
    print(f"  成功: {success_count} 個")
    print(f"  失敗: {error_count} 個")
    print(f"  結果保存至: {output_file}")

    # 統計標籤使用情況
    tag_counter = {}
    for item in results:
        tags = item.get('disg_detil', {}).get('tags', [])
        for tag in tags:
            tag_counter[tag] = tag_counter.get(tag, 0) + 1

    print(f"\n📊 標籤統計：")
    sorted_tags = sorted(tag_counter.items(), key=lambda x: x[1], reverse=True)
    for tag, count in sorted_tags[:10]:
        print(f"  {tag}: {count} 次")

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
