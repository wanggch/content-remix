#!/usr/bin/env python3
"""Deterministic file/structure checks; does not replace visual or originality review."""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as file:
        # PNG 的 IHDR 固定记录宽高；只读文件头，不依赖 Pillow 或完整解码图片。
        header = file.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("不是有效的 PNG 文件头")
    w, h = struct.unpack(">II", header[16:24])
    if not w or not h:
        raise ValueError("图片尺寸非法")
    return w, h


REQUIRED = ["00-source/source.md", "01-analysis.md", "02-topics.md", "03-storyboard.md", "04-publish.md", "05-review.md", "cards.json"]


def inspect(root: Path) -> tuple[list[str], list[str], list[str]]:
    # errors 阻止结构校验通过；warnings 提醒人工复核，不单独导致非零退出码。
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    for name in REQUIRED:
        path = root / name
        if not path.is_file() or not path.stat().st_size:
            errors.append(f"缺少或为空：{name}")
    cards = []
    try:
        data = json.loads((root / "cards.json").read_text(encoding="utf-8"))
        cards = data["cards"]
        if not isinstance(cards, list) or not cards:
            raise ValueError("cards 必须是非空数组")
        title = str(data.get("title", ""))
        if not title:
            errors.append("cards.json 缺少 title")
        elif len(title) > 20:
            warnings.append(f"标题超过20字（{len(title)}字）")
        for i, card in enumerate(cards, 1):
            if card.get("index") != i:
                errors.append(f"第 {i} 张 index 不是 {i}")
            for key in ["role", "caption", "alt", "image_prompt"]:
                if not str(card.get(key, "")).strip():
                    errors.append(f"第 {i} 张缺少 {key}")
            caption = str(card.get("caption", ""))
            has_regions = "bubble_text" in card or "body_text" in card
            if has_regions:
                bubble = str(card.get("bubble_text", ""))
                body = str(card.get("body_text", ""))
                if not bubble.strip() or not body.strip():
                    errors.append(f"第 {i} 张气泡或底部解释为空")
                if caption != bubble + "\n" + body:
                    errors.append(f"第 {i} 张 caption 与气泡、底文不一致")
            limit = 150 if has_regions else 60
            if len(caption) > limit:
                warnings.append(f"第 {i} 张文案大于{limit}字，请核查手机可读性")
            if caption and caption not in str(card.get("image_prompt", "")):
                errors.append(f"第 {i} 张 image_prompt 未包含完整准确 caption")
            prompt = root / "prompts" / f"{i:02d}.md"
            if not prompt.exists() or not prompt.read_text(encoding="utf-8").strip():
                errors.append(f"缺少实际生图提示词：prompts/{i:02d}.md")
            elif card.get("image_prompt") and str(card["image_prompt"]).strip() not in prompt.read_text(encoding="utf-8"):
                warnings.append(f"prompts/{i:02d}.md 与 cards.json 的 image_prompt 不一致")
        if len(cards) != 4:
            warnings.append(f"当前为 {len(cards)} 张图，非默认四图，确认是否符合用户需求")
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        errors.append("cards.json 格式不可用：" + str(exc))

    # 按 cards 序号统计交付文件，目录中其他图片不计入完成数量。
    generated = sum((root / "generated" / f"{i:02d}.png").is_file() for i in range(1, len(cards) + 1))
    final = sum((root / "final" / f"{i:02d}.png").is_file() for i in range(1, len(cards) + 1))
    info.append(f"可选生成目录图片：{generated}/{len(cards)}；带字成品图：{final}/{len(cards)}")
    for i in range(1, len(cards) + 1):
        for folder in ["generated", "final"]:
            image = root / folder / f"{i:02d}.png"
            if image.is_file():
                try:
                    w, h = png_dimensions(image)
                    # 允许中心裁切取整造成的小误差；非默认比例仅提醒，不判失败。
                    if folder == "final" and abs(w / h - 3 / 4) > 0.015:
                        warnings.append(f"{folder}/{i:02d}.png 宽高比不是默认 3:4（{w}x{h}）")
                except (OSError, ValueError) as exc:
                    errors.append(f"{folder}/{i:02d}.png 文件无效：{exc}")
    # ChatGPT 可直接交付 final/ 中的带字图片，不要求额外保留无字底图。
    if final < len(cards):
        warnings.append("最终带字图未全部生成；不可宣称公众号配图成品已完成")
    try:
        source = json.loads((root / "00-source/source.json").read_text(encoding="utf-8"))
        if source.get("status") != "ok":
            warnings.append("源文素材不完整或需人工图像阅读：" + str(source.get("status")))
    except (OSError, json.JSONDecodeError):
        warnings.append("缺少 00-source/source.json；来源完整性尚未核实")
    info.append("结构校验不包含视觉畸形、文案事实性、版权/原创人工审核")
    return errors, warnings, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    args = ap.parse_args()
    root = args.project.expanduser().resolve()
    errors, warnings, info = inspect(root)
    for msg in info:
        print("INFO: " + msg)
    for msg in warnings:
        print("WARN: " + msg)
    for msg in errors:
        print("FAIL: " + msg)
    print(f"检查完成：FAIL={len(errors)} WARN={len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
