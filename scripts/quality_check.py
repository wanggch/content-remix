#!/usr/bin/env python3
"""Check compiled delivery and image files; semantic/visual review remains separate."""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

from project_paths import resolve
from build_prompt import BATCH_PATH, CONTRACT_PATH, DIMENSIONS, load_project, render_batch, render_contract

REQUIRED = ["00-source/source.md", "01-analysis.md", "02-topics.md", "03-storyboard.md",
            "04-publish.md", "05-review.md", "cards.json", str(CONTRACT_PATH), str(BATCH_PATH)]


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as file:
        header = file.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("不是有效的 PNG 文件头")
    width, height = struct.unpack(">II", header[16:24])
    if not width or not height:
        raise ValueError("图片尺寸非法")
    return width, height


def inspect(root: Path) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    for name in REQUIRED:
        path = resolve(root, name)
        if not path.is_file() or not path.stat().st_size:
            errors.append(f"缺少或为空：{name}")
    data = None
    try:
        data = load_project(root)
    except (OSError, ValueError) as exc:
        errors.append(f"cards.json 格式不可用：{exc}")
    if data:
        for relative, expected in [(BATCH_PATH, render_batch(data)), (CONTRACT_PATH, render_contract(data))]:
            try:
                actual = resolve(root, relative).read_text(encoding="utf-8")
                if actual != expected:
                    errors.append(f"{relative} 与 cards.json 不一致；请重新运行 build_prompt.py")
            except (OSError, UnicodeError) as exc:
                errors.append(f"{relative} 无法读取：{exc}")
        if len(data["title"]) > 20:
            warnings.append(f"标题超过20字（{len(data['title'])}字）")
        lengths = data["format_contract"]["caption_length"]
        for card in data["cards"]:
            count = len(card["caption"])
            if not lengths["min_chars"] <= count <= lengths["max_chars"]:
                warnings.append(f"第 {card['index']} 张文案 {count} 字符，偏离约定篇幅，请核查阅读量")
        if any(data["format_contract"][key]["source"] == "unknown" for key in DIMENSIONS):
            warnings.append("创作约束中有未知素材，不能宣称已完成对应对标拆解")
        cards = data["cards"]
        ratio_w, ratio_h = map(int, data["aspect_ratio"].split(":"))
        expected_ratio = ratio_w / ratio_h
        generated = sum((resolve(root, "generated") / f"{card['index']:02d}.png").is_file() for card in cards)
        final = sum((resolve(root, "final") / f"{card['index']:02d}.png").is_file() for card in cards)
        info.append(f"可选生成目录图片：{generated}/{len(cards)}；带字成品图：{final}/{len(cards)}")
        for card in cards:
            for folder in ("generated", "final"):
                image = resolve(root, folder) / f"{card['index']:02d}.png"
                if image.is_file():
                    try:
                        width, height = png_dimensions(image)
                        if folder == "final" and abs(width / height - expected_ratio) > 0.015:
                            warnings.append(f"{folder}/{image.name} 宽高比偏离 {data['aspect_ratio']}（{width}x{height}）")
                    except (OSError, ValueError) as exc:
                        errors.append(f"{folder}/{image.name} 文件无效：{exc}")
        if final < len(cards):
            warnings.append("最终带字图未全部生成；不可宣称公众号配图成品已完成")
    try:
        source = json.loads(resolve(root, "00-source/source.json").read_text(encoding="utf-8"))
        if not isinstance(source, dict) or source.get("status") != "ok":
            warnings.append("源文素材不完整或需人工图像阅读")
    except (OSError, ValueError):
        warnings.append("缺少有效的 00-source/source.json；来源完整性尚未核实")
    info.append("结构校验不包含审美、生活语感、事实性、视觉畸形与原创人工审核")
    return errors, warnings, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    args = ap.parse_args()
    errors, warnings, info = inspect(args.project.expanduser().resolve())
    for prefix, messages in [("INFO", info), ("WARN", warnings), ("FAIL", errors)]:
        for message in messages:
            print(f"{prefix}: {message}")
    print(f"检查完成：FAIL={len(errors)} WARN={len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
