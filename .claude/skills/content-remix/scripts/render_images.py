#!/usr/bin/env python3
"""Optional paid OpenAI Image API renderer; prints dry-run unless --yes is passed."""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.openai.com/v1/images/generations"


def load_cards(project: Path) -> list[dict]:
    data = json.loads((project / "cards.json").read_text(encoding="utf-8"))
    cards = data.get("cards", [])
    if not isinstance(cards, list) or not cards:
        raise ValueError("cards.json 必须包含非空 cards 数组")
    # 连续序号与 prompts/、generated/、final/ 的两位数文件名保持对应。
    for index, card in enumerate(cards, 1):
        if card.get("index") != index or not str(card.get("image_prompt", "")).strip():
            raise ValueError(f"第 {index} 张图需有正确 index 和非空 image_prompt")
    return cards


def main() -> int:
    ap = argparse.ArgumentParser(description="可选：调用 OpenAI Image API 生成单张图片（付费）")
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--yes", action="store_true", help="明确同意调用付费 API；否则仅预览")
    ap.add_argument("--model", default="gpt-image-2.5-flare")
    ap.add_argument("--size", default="1024x1536", choices=["1024x1024", "1024x1536", "1536x1024"])
    ap.add_argument("--quality", default="medium", choices=["low", "medium", "high", "auto"])
    ap.add_argument("--overwrite", action="store_true", help="已有图片重新生成（仍产生费用）")
    args = ap.parse_args()
    project = args.project.expanduser().resolve()
    try:
        cards = load_cards(project)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print("数据错误：" + str(exc), file=sys.stderr)
        return 2
    target_dir = project / "generated"
    target_dir.mkdir(parents=True, exist_ok=True)
    # 默认跳过已有底图，便于中断后续跑；只有 --overwrite 才重新付费生成。
    todo = [c for c in cards if args.overwrite or not (target_dir / f"{c['index']:02d}.png").exists()]
    print(f"模型：{args.model}; 尺寸：{args.size}; 质量：{args.quality}; 待生成：{len(todo)}/{len(cards)}")
    for c in todo:
        print(f" - {c['index']:02d}.png: {str(c['image_prompt'])[:65]}...")
    # 付费开关之前不读取密钥、不请求 API；无密钥也能完整预览待生成任务。
    if not args.yes:
        print("预览完成。未调用 API；确认可能产生费用后添加 --yes。")
        return 0
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        print("缺少 OPENAI_API_KEY，未发起任何请求。", file=sys.stderr)
        return 2
    if not todo:
        print("所有图片已存在；如需重新生成请加 --overwrite。")
        return 0
    ok = 0
    for card in todo:
        idx = card["index"]
        payload = {
            "model": args.model,
            "prompt": card["image_prompt"],
            "size": args.size,
            "quality": args.quality,
            "output_format": "png",
            "n": 1,
        }
        request = urllib.request.Request(
            API,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=240) as resp:
                result = json.load(resp)
            data = result.get("data", [])
            if not data or not data[0].get("b64_json"):
                raise ValueError("API 未返回 base64 图片；请检查响应模型及 API 规格")
            # 先校验 base64 和 PNG 签名，再落盘，避免把错误响应保存成图片。
            raw = base64.b64decode(data[0]["b64_json"], validate=True)
            if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("API 返回的字节不是 PNG")
            path = target_dir / f"{idx:02d}.png"
            path.write_bytes(raw)
            ok += 1
            print(f"已保存：{path}")
        except (urllib.error.URLError, ValueError, OSError, json.JSONDecodeError) as exc:
            print(f"第 {idx} 张失败：{exc}", file=sys.stderr)
            if isinstance(exc, urllib.error.HTTPError):
                try:
                    print(exc.read(600).decode("utf-8", "replace"), file=sys.stderr)
                except Exception:
                    pass
            # 不自动重试付费请求：服务端可能已完成生成，重试有重复计费风险。
    print(f"本次成功：{ok}/{len(todo)}；失败可修复后重新运行，已有文件默认跳过。")
    return 0 if ok == len(todo) else 1


if __name__ == "__main__":
    raise SystemExit(main())
