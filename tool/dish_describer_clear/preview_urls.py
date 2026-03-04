"""
預覽 URL 列表和內容
不需要 API key，用於查看將要處理的數據
"""
import json
from pathlib import Path
from collections import OrderedDict


def load_json(file_path: Path) -> dict:
    """讀取 JSON 文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_unique_urls(data: dict) -> dict:
    """提取唯一的 URL 和內容"""
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
                    'content_length': len(snippet.get('content', '')),
                    'title': snippet.get('title', ''),
                    'dish_names': [dish_name]
                }
            else:
                if dish_name not in url_map[url]['dish_names']:
                    url_map[url]['dish_names'].append(dish_name)

    return url_map


def main():
    """主函數"""
    # 文件路徑
    input_file = Path(__file__).parent.parent / 'dish_describer' / 'axia_dish_descriptions.json'

    print("="*70)
    print("URL Content Preview Tool")
    print("="*70)

    # Load data
    print(f"\nLoading data: {input_file.name}")
    data = load_json(input_file)

    # Extract URLs
    print("\nAnalyzing data...")
    url_map = extract_unique_urls(data)

    # Statistics
    total_urls = len(url_map)
    total_content_length = sum(info['content_length'] for info in url_map.values())
    avg_content_length = total_content_length / total_urls

    print(f"\nStatistics:")
    print(f"  Total dishes: {len(data.get('items', []))}")
    print(f"  Unique URLs: {total_urls}")
    print(f"  Total content length: {total_content_length:,} chars")
    print(f"  Average content length: {avg_content_length:.0f} chars")

    # Sort by content length
    sorted_by_length = sorted(
        url_map.items(),
        key=lambda x: x[1]['content_length'],
        reverse=True
    )

    # Show top 10 longest URLs
    print(f"\nTop 10 URLs by content length:")
    print("-"*70)
    for i, (url, info) in enumerate(sorted_by_length[:10], 1):
        print(f"\n{i}. {url}")
        print(f"   Title: {info['title'][:60]}")
        print(f"   Content length: {info['content_length']:,} chars")
        print(f"   Related dishes: {len(info['dish_names'])}")
        print(f"   Dishes: {', '.join(info['dish_names'][:5])}", end='')
        if len(info['dish_names']) > 5:
            print(f" ... and {len(info['dish_names']) - 5} more")
        else:
            print()

    # Show content preview
    print(f"\nFirst URL content preview:")
    print("-"*70)
    first_url, first_info = list(url_map.items())[0]
    print(f"URL: {first_url}")
    print(f"Title: {first_info['title']}")
    print(f"\nFirst 500 characters:")
    print(first_info['content'][:500])
    print("...")

    # Cost estimation
    print(f"\nEstimated cost for ChatGPT processing:")
    print("-"*70)
    # 假設每個 URL 平均使用 1500 tokens input + 500 tokens output
    avg_input_tokens = 1500
    avg_output_tokens = 500

    # gpt-4o-mini 價格（2024-10）
    input_cost_per_1m = 0.150  # USD per 1M tokens
    output_cost_per_1m = 0.600  # USD per 1M tokens

    total_input_cost = (avg_input_tokens * total_urls / 1_000_000) * input_cost_per_1m
    total_output_cost = (avg_output_tokens * total_urls / 1_000_000) * output_cost_per_1m
    total_cost = total_input_cost + total_output_cost

    print(f"  模型: gpt-4o-mini")
    print(f"  預估 input tokens: {avg_input_tokens * total_urls:,}")
    print(f"  預估 output tokens: {avg_output_tokens * total_urls:,}")
    print(f"  Estimated total cost: ${total_cost:.2f} USD")
    print(f"  Estimated time: ~{total_urls * 3 / 60:.1f} minutes (~3 sec per URL)")

    # Recommendations
    print(f"\nRecommendations:")
    print("-"*70)
    print(f"  1. Test with 5-10 URLs first to verify results")
    print(f"  2. Process all URLs after confirming quality")
    print(f"  3. Use summarize_url_content.py for processing")
    print(f"  4. Remember to set OPENAI_API_KEY environment variable")

    # Save URL list
    url_list_file = Path(__file__).parent / 'url_list.json'
    url_list = [
        {
            'url': url,
            'title': info['title'],
            'content_length': info['content_length'],
            'dish_count': len(info['dish_names']),
            'dishes': info['dish_names']
        }
        for url, info in url_map.items()
    ]

    with open(url_list_file, 'w', encoding='utf-8') as f:
        json.dump(url_list, f, ensure_ascii=False, indent=2)

    print(f"\nSaved URL list to: {url_list_file.name}")
    print(f"  Contains {total_urls} URLs with full information")


if __name__ == '__main__':
    main()
