#!/usr/bin/env python3
"""Overlay Chinese captions on completed base images; optional Pillow dependency."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 按 macOS、Linux、Windows 的常见中文字体依次查找；--font 可覆盖自动选择。
FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def find_font(arg: str | None) -> str:
    if arg:
        path = Path(arg).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"字体不存在：{path}")
        return str(path)
    for font in FONT_CANDIDATES:
        if Path(font).is_file():
            return font
    raise FileNotFoundError("未发现常见中文字体，请用 --font 指定本机中文 TTF/TTC 字体路径")


def wrap_text(text: str, drawer, font, max_width: int) -> list[str]:
    lines: list[str] = []
    # 按实际字形宽度逐字换行，兼容没有空格分词的中文和中英混排。
    for paragraph in str(text).splitlines():
        line = ""
        for char in paragraph:
            proposed = line + char
            box = drawer.textbbox((0, 0), proposed, font=font)
            if line and box[2] - box[0] > max_width:
                lines.append(line)
                line = char
            else:
                line = proposed
        lines.append(line)
    return [s for s in lines if s.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description="为四图无字底图叠加可读的中文文案")
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--font", help="中文 TTF/TTC 字体（未指定时查找系统字体）")
    ap.add_argument("--position", choices=["top", "bottom"], default="bottom")
    ap.add_argument("--ratio", choices=["3:4", "4:5", "9:16", "original"], default="3:4", help="最终成品宽高比")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("缺少 Pillow，请先运行：python3 -m pip install 'Pillow>=10'", file=sys.stderr)
        return 2
    try:
        font_path = find_font(args.font)
        cards = json.loads((args.project / "cards.json").read_text(encoding="utf-8"))["cards"]
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print("输入失败：" + str(exc), file=sys.stderr)
        return 2
    project = args.project.expanduser().resolve()
    (project / "final").mkdir(parents=True, exist_ok=True)
    completed = 0
    for card in cards:
        idx = card.get("index")
        if not isinstance(idx, int) or idx < 1:
            print("cards.json 的 index 无效", file=sys.stderr)
            return 2
        base = project / "generated" / f"{idx:02d}.png"
        result = project / "final" / f"{idx:02d}.png"
        if result.exists() and not args.overwrite:
            print(f"跳过已有成品：{result}")
            completed += 1
            continue
        if not base.is_file():
            print(f"缺少底图：{base}，该张暂不叠字", file=sys.stderr)
            continue
        caption = str(card.get("caption", "")).strip()
        if not caption:
            print(f"第 {idx} 张 caption 为空", file=sys.stderr)
            continue
        try:
            with Image.open(base) as source:
                im = source.convert("RGBA")
            w, h = im.size
            # 只居中裁切、不拉伸；生图阶段需把主体放在中央安全区。
            if args.ratio != "original":
                rw, rh = map(int, args.ratio.split(":"))
                desired = rw / rh
                current = w / h
                if current < desired:  # 底图偏高，裁掉上下多余区域
                    target_h = int(w / desired)
                    y0 = (h - target_h) // 2
                    im = im.crop((0, y0, w, y0 + target_h))
                elif current > desired:  # 底图偏宽，裁掉左右多余区域
                    target_w = int(h * desired)
                    x0 = (w - target_w) // 2
                    im = im.crop((x0, 0, x0 + target_w, h))
                w, h = im.size
            if w < 320 or h < 320:
                raise ValueError("底图尺寸过小")
            font_size = max(30, int(w * 0.048))
            font = ImageFont.truetype(font_path, font_size)
            draw = ImageDraw.Draw(im)
            padding_x = int(w * 0.085)
            lines = wrap_text(caption, draw, font, w - padding_x * 2 - int(w * 0.06))
            leading = int(font_size * 1.48)
            padding_y = int(h * 0.023)
            panel_height = len(lines) * leading + padding_y * 2
            panel_height = max(panel_height, int(h * 0.12))
            # 限制文字面板占比，避免遮住主体；超长文案应精简，而不是无限缩小字号。
            if panel_height > h * 0.33:
                raise ValueError("文案过长，叠字区域将超过画面 1/3，请先缩短 caption")
            margin_y = int(h * 0.04)
            top = margin_y if args.position == "top" else h - margin_y - panel_height
            x0, x1 = int(w * 0.055), int(w * 0.945)
            draw.rounded_rectangle((x0, top, x1, top + panel_height), radius=int(w * 0.025), fill=(255, 253, 249, 228))
            text_y = top + (panel_height - len(lines) * leading) // 2
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                draw.text(((w - text_width) / 2, text_y), line, font=font, fill=(45, 40, 35, 255))
                text_y += leading
            im.convert("RGB").save(result, "PNG", optimize=True)
            print(f"已叠字：{result}")
            completed += 1
        except (OSError, ValueError) as exc:
            print(f"第 {idx} 张叠字失败：{exc}", file=sys.stderr)
    print(f"完成：{completed}/{len(cards)}，请人工在手机尺寸预览图片。")
    return 0 if completed == len(cards) else 1


if __name__ == "__main__":
    raise SystemExit(main())
