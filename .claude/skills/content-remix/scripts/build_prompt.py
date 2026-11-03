#!/usr/bin/env python3
"""Validate creative data and compile one batch prompt without model/API calls."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STRUCTURES = {
    "parallel": ("并列话术卡", "每张表达一个独立观点或场景。人物与画风统一，场景和时间可不同，不强行编成连续剧情。"),
    "story": ("连续故事", "按顺序推进同一个事件，保持时间、空间、人物与道具的因果连续，结尾回应开场。"),
    "contrast": ("前后对照", "明确每张属于哪一组对照，保持比较对象、条件与视觉尺度可比，不把差异归因于无关因素。"),
    "tutorial": ("步骤教程", "按可执行顺序展示动作，写清每步的输入、操作和结果，不能跳过完成任务所需的关键步骤。"),
}
DIMENSIONS = {
    "structure": "内容结构", "text_layers": "文字层级", "caption_length": "文案篇幅",
    "tone": "语言语感", "visual": "通用视觉",
}
PLACEHOLDER = re.compile(r"〔[^〕\n]*〕|\{\{[^}\n]*\}\}|【(?:填写|填入|粘贴|待填)[^】\n]*】")
BATCH_PATH = Path("prompts/创作提示词.md")
CONTRACT_PATH = Path("02-创作约束.md")


def require_text(obj: dict, key: str, location: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location}.{key} 必须为非空文本")
    if PLACEHOLDER.search(value) or "```" in value:
        raise ValueError(f"{location}.{key} 残留模板占位符或包含代码块分隔符")
    return value


def validate(data: object, *, require_cards: bool = True) -> dict:
    if not isinstance(data, dict):
        raise ValueError("cards.json 顶层必须是对象")
    if data.get("schema_version") != 2:
        raise ValueError("schema_version 必须为 2；按 references/cards-schema.md 更新创作数据")
    for key in ("title", "audience", "theme", "characters", "style_guide", "scene_policy", "layout", "aspect_ratio"):
        require_text(data, key, "项目")
    if not isinstance(data.get("content_structure"), str) or data["content_structure"] not in STRUCTURES:
        raise ValueError("content_structure 必须是 parallel / story / contrast / tutorial")
    if not re.fullmatch(r"[1-9]\d*:[1-9]\d*", data["aspect_ratio"]):
        raise ValueError("aspect_ratio 必须是正整数比例，如 3:4")
    contract = data.get("format_contract")
    if not isinstance(contract, dict):
        raise ValueError("format_contract 必须是对象")
    for key in DIMENSIONS:
        item = contract.get(key)
        if not isinstance(item, dict):
            raise ValueError(f"format_contract 缺少 {key}")
        for field in ("source", "target", "evidence"):
            require_text(item, field, f"format_contract.{key}")
        if "change_reason" in item:
            require_text(item, "change_reason", f"format_contract.{key}")
    structure = contract["structure"]
    if structure["source"] not in {*STRUCTURES, "unknown"} or structure["target"] != data["content_structure"]:
        raise ValueError("约束中的结构类型非法，或 target 与 content_structure 不一致")
    if structure["source"] not in {"unknown", structure["target"]} and not structure.get("change_reason"):
        raise ValueError("改变对标结构时必须记录 change_reason 和用户依据")
    lengths = contract["caption_length"]
    low, high = lengths.get("min_chars"), lengths.get("max_chars")
    if type(low) is not int or type(high) is not int or not 0 < low <= high:
        raise ValueError("caption_length 需要合理的 min_chars / max_chars（含标点和换行）")
    if not require_cards:
        return data
    cards = data.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("cards 必须是非空数组")
    for index, card in enumerate(cards, 1):
        if not isinstance(card, dict):
            raise ValueError(f"第 {index} 张必须是对象")
        if type(card.get("index")) is not int or card["index"] != index:
            raise ValueError(f"第 {index} 张 index 必须为 {index}")
        if "image_prompt" in card:
            raise ValueError(f"第 {index} 张请使用 scene；image_prompt 已由脚本即时组合")
        for field in ("role", "scene", "caption", "alt"):
            require_text(card, field, f"第 {index} 张")
        if "bubble_text" in card or "body_text" in card:
            bubble = require_text(card, "bubble_text", f"第 {index} 张")
            body = require_text(card, "body_text", f"第 {index} 张")
            if card["caption"] != bubble + "\n" + body:
                raise ValueError(f"第 {index} 张 caption 与气泡、底文不一致")
    for key in ("scene_tags", "action_tags"):
        if key in data and (not isinstance(data[key], list) or any(not isinstance(v, str) or not v.strip() for v in data[key])):
            raise ValueError(f"{key} 必须是非空文本组成的数组")
    return data


def load_project(project: Path, *, require_cards: bool = True) -> dict:
    from project_paths import resolve
    return validate(json.loads(resolve(project, "cards.json").read_text(encoding="utf-8")), require_cards=require_cards)


def common_prompt(data: dict) -> str:
    label, rule = STRUCTURES[data["content_structure"]]
    return (
        f"主题：{data['title']}\n目标读者：{data['audience']}\n核心表达：{data['theme']}\n"
        f"内容结构：{label}。{rule}\n"
        f"人物：{data['characters']}\n画风：{data['style_guide']}\n"
        f"场景规则：{data['scene_policy']}\n画幅：每张独立 {data['aspect_ratio']}。\n"
        f"文字排版：{data['layout']}\n"
        "直接生成带准确简体中文文案的图片，按指定文字逐字使用，保留标点和换行。"
        "不要额外添加标题、序号、logo、水印或环境文字。图中文字清晰，适合手机阅读。"
    )


def card_section(card: dict) -> str:
    text = (f"【{card['index']:02d}｜{card['role']}】\n画面：{card['scene']}\n"
            f"图片内准确文字（保留换行）：\n{card['caption']}\n")
    if "bubble_text" in card:
        line_count = card["bubble_text"].count("\n") + 1
        bubble_region = "第一行" if line_count == 1 else f"前{line_count}行"
        text += f"文字分区：{bubble_region}放气泡，其余文字按指定换行放底部解释区；解释不得塞进气泡。\n"
    return text


def image_prompt(data: dict, card: dict) -> str:
    """仅供可选 API 在内存中组合请求，不交付独立提示词文件。"""
    return "生成一张独立带字图片，不拼图。\n" + common_prompt(data) + "\n\n" + card_section(card)


def render_batch(data: dict) -> str:
    count = len(data["cards"])
    sections = "\n".join(card_section(card) for card in data["cards"])
    return (
        "# 创作提示词\n\n"
        "复制下方整个代码块到支持图片生成的 ChatGPT 对话。所有创作设定均在此文件中；无需读取本地文件。"
        "多图输出受模型、界面和额度影响，实际图片仍需核对文字、人物及手机可读性。\n\n"
        "```text\n"
        f"请使用图片生成能力，生成 {count} 张独立带字图片，按 01—{count:02d} 分别输出。"
        "不是一张四宫格、拼贴或联系表。尽可能完成全部图片；数量不足时说明已完成序号，不用文字描述冒充图片。\n\n"
        "【全组设定】\n" + common_prompt(data) + "\n\n" + sections +
        "\n【质量要求】\n每张只表达一个主要观点或动作；按所选结构组织图片。"
        "检查五官、手指、人体结构、透视、物件数量和文字错漏；画面与文字互补。"
        "使用独立创作的角色、情节和构图，不照搬对标作品的独特表达。\n```\n\n"
        "## 缺图续生成\n\n"
        "在同一对话中说明缺失序号，并从上方复制相应图片的完整分镜与准确文字，"
        "要求沿用全组设定，仅补齐缺图，每张独立输出。\n\n"
        "## 误生成拼图\n\n"
        "要求按上方分镜逐张重新生成独立图片文件，不能将拼图计作多张成品。\n\n"
        "换新对话时同时复制完整全组设定和所需分镜；需要参考图时实际上传有权使用的图片。\n"
    )


def render_contract(data: dict) -> str:
    lines = ["# 创作约束", "", "由 cards.json 生成。选题确定后、编写分镜前填写并检查这些约束；修改后重新生成。", ""]
    for key, label in DIMENSIONS.items():
        item = data["format_contract"][key]
        lines.extend([f"## {label}", "", f"- 对标：{item['source']}", f"- 本次：{item['target']}",
                      f"- 证据：{item['evidence']}", f"- 改动依据：{item.get('change_reason', '保留通用形式，具体表达独立创作。')}", ""])
    lengths = data["format_contract"]["caption_length"]
    lines.extend([f"单图文案目标：{lengths['min_chars']}—{lengths['max_chars']} 字符（含标点、换行）。",
                  f"场景规则：{data['scene_policy']}", "", "证据不足时保留未知项，不把推测当作实际观察。", ""])
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="从 cards.json 生成创作约束和一份整组创作提示词")
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--contract-only", action="store_true", help="分镜前只生成约束，允许 cards 尚为空")
    args = ap.parse_args()
    project = args.project.expanduser().resolve()
    try:
        data = load_project(project, require_cards=not args.contract_only)
        outputs = {CONTRACT_PATH: render_contract(data)}
        if not args.contract_only:
            outputs[BATCH_PATH] = render_batch(data)
        for relative, text in outputs.items():
            from project_paths import resolve
            target = resolve(project, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            print(f"已生成：{target}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"创作数据错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
