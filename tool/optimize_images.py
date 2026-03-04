#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
圖片優化工具 - 簡化版
- 直接在 dish 目錄生成 WebP 格式
- 保留原始 PNG 檔案
- 不生成多種尺寸

使用方式：
    # 為 dish 目錄中的所有 PNG 生成 WebP
    python tool/optimize_images.py

    # 僅預覽，不實際執行
    python tool/optimize_images.py --dry-run

    # 自訂品質設定
    python tool/optimize_images.py --quality 85

依賴套件：
    pip install Pillow
"""
import os
import sys
import io
from pathlib import Path
from PIL import Image
import argparse

# 設定 Windows 控制台輸出編碼
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 設定
DISH_DIR = Path("static/public/images/dish")
WEBP_QUALITY = 80  # WebP 品質 (0-100)


def get_file_size(path: Path) -> int:
    """取得檔案大小（bytes）"""
    return path.stat().st_size if path.exists() else 0


def format_size(size_bytes: int) -> str:
    """格式化檔案大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def convert_to_webp(png_path: Path, quality: int = WEBP_QUALITY, dry_run: bool = False) -> dict:
    """
    將 PNG 轉換為 WebP 格式

    Args:
        png_path: PNG 檔案路徑
        quality: WebP 品質 (0-100)
        dry_run: 預覽模式，不實際轉換

    Returns:
        包含轉換資訊的字典
    """
    try:
        # 開啟圖片
        img = Image.open(png_path)

        # 轉換為 RGB（某些 PNG 可能是 RGBA）
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

        # 生成 WebP 檔案路徑
        webp_path = png_path.with_suffix('.webp')

        # 取得原始檔案大小
        original_size = get_file_size(png_path)

        # 如果 WebP 已存在，取得其大小
        if webp_path.exists():
            existing_webp_size = get_file_size(webp_path)
        else:
            existing_webp_size = 0

        if not dry_run:
            # 儲存 WebP
            img.save(webp_path, "WEBP", quality=quality, method=6)

        # 取得新的 WebP 大小
        webp_size = get_file_size(webp_path) if not dry_run else 0

        # 如果是預覽模式，估算 WebP 大小（約為 PNG 的 20-30%）
        if dry_run:
            webp_size = int(original_size * 0.25)

        return {
            'success': True,
            'png_path': png_path,
            'webp_path': webp_path,
            'original_size': original_size,
            'webp_size': webp_size,
            'saved': original_size - webp_size,
            'saved_percent': ((original_size - webp_size) / original_size * 100) if original_size > 0 else 0,
            'existed': existing_webp_size > 0,
        }

    except Exception as e:
        return {
            'success': False,
            'png_path': png_path,
            'error': str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="圖片優化工具 - WebP 轉換")
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='預覽模式，不實際轉換'
    )
    parser.add_argument(
        '--quality',
        type=int,
        default=WEBP_QUALITY,
        help=f'WebP 品質 (0-100)，預設 {WEBP_QUALITY}'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='強制重新轉換已存在的 WebP 檔案'
    )
    args = parser.parse_args()

    # 檢查目錄
    if not DISH_DIR.exists():
        print(f"❌ 目錄不存在: {DISH_DIR}")
        sys.exit(1)

    # 取得所有 PNG 檔案
    png_files = list(DISH_DIR.glob("*.png")) + list(DISH_DIR.glob("*.PNG"))

    if not png_files:
        print(f"❌ 在 {DISH_DIR} 中找不到 PNG 檔案")
        sys.exit(1)

    print("🖼️  圖片優化工具 - WebP 轉換")
    print(f"📂 目錄: {DISH_DIR}")
    print(f"📦 找到 {len(png_files)} 張 PNG 圖片")
    print(f"⚙️  WebP 品質: {args.quality}")

    if args.dry_run:
        print("👀 預覽模式（不會實際轉換）")

    print("\n" + "=" * 80)

    # 統計資訊
    total_original = 0
    total_webp = 0
    converted_count = 0
    skipped_count = 0
    error_count = 0

    # 處理每張圖片
    for png_path in sorted(png_files):
        # 檢查 WebP 是否已存在
        webp_path = png_path.with_suffix('.webp')

        if webp_path.exists() and not args.force and not args.dry_run:
            # 已存在且不強制覆蓋，跳過
            skipped_count += 1
            continue

        # 轉換
        result = convert_to_webp(png_path, quality=args.quality, dry_run=args.dry_run)

        if result['success']:
            print(f"📄 {png_path.name}")
            print(f"   PNG: {format_size(result['original_size'])}")
            print(f"   WebP: {format_size(result['webp_size'])}")
            print(f"   節省: {format_size(result['saved'])} ({result['saved_percent']:.1f}%)")

            if result['existed']:
                print(f"   ♻️  覆蓋現有檔案")

            if args.dry_run:
                print(f"   [預覽] 將會轉換")
            else:
                print(f"   ✅ 已轉換")

            print()

            total_original += result['original_size']
            total_webp += result['webp_size']
            converted_count += 1

        else:
            print(f"❌ {png_path.name}")
            print(f"   錯誤: {result['error']}\n")
            error_count += 1

    print("=" * 80)
    print(f"\n📊 統計資訊:")
    print(f"   轉換檔案數: {converted_count}")

    if skipped_count > 0:
        print(f"   跳過檔案數: {skipped_count} (已存在)")
        print(f"   提示: 使用 --force 強制重新轉換")

    if error_count > 0:
        print(f"   錯誤數: {error_count}")

    if converted_count > 0:
        print(f"   PNG 總大小: {format_size(total_original)}")
        print(f"   WebP 總大小: {format_size(total_webp)}")
        print(f"   節省空間: {format_size(total_original - total_webp)} "
              f"({((total_original - total_webp) / total_original * 100):.1f}%)")

    if args.dry_run:
        print(f"\n💡 這是預覽模式，沒有實際轉換檔案")
        print(f"   執行 `python tool/optimize_images.py` 開始轉換")
    else:
        print(f"\n✅ 完成！")
        print(f"   WebP 檔案已儲存到: {DISH_DIR}")
        print(f"\n💡 提示：")
        print(f"   - 原始 PNG 檔案已保留")
        print(f"   - 瀏覽器會自動選擇最佳格式")
        print(f"   - WebP 平均節省 70-80% 檔案大小")


if __name__ == "__main__":
    try:
        from PIL import Image
    except ImportError:
        print("❌ 需要安裝 Pillow 套件")
        print("執行: pip install Pillow")
        sys.exit(1)

    main()
