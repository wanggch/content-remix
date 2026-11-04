#!/usr/bin/env python3
"""Workspace-local preferences and searchable topic history; no model/API calls."""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

from build_prompt import load_project

MEMORY_DIR = ".content-remix"


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} 必须是对象")
    return data


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def preferences(workspace: Path) -> list[dict]:
    data = read_json(workspace / MEMORY_DIR / "preferences.json", {"schema_version": 1, "entries": []})
    entries = data.get("entries")
    if data.get("schema_version") != 1 or not isinstance(entries, list):
        raise ValueError("preferences.json 格式不可用")
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("kind") not in {"explicit", "inferred"}:
            raise ValueError("偏好记录 kind 必须为 explicit 或 inferred")
        if entry.get('status', 'active') not in {'active', 'superseded'}:
            raise ValueError('偏好记录status必须为active或superseded')
        for key in ("key", "value", "evidence", "scope"):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                raise ValueError(f"偏好记录缺少 {key}")
    return entries


def effective_preferences(entries: list[dict]) -> list[dict]:
    selected: dict[tuple[str, str], dict] = {}
    for entry in entries:
        if entry.get('status') == 'superseded':
            continue
        key = (entry["scope"], entry["key"])
        previous = selected.get(key)
        if previous is None or entry["kind"] == "explicit" or previous["kind"] != "explicit":
            selected[key] = entry
    return list(selected.values())


def sync(workspace: Path) -> dict:
    topics = []
    from project_paths import resolve
    for project in sorted((workspace / "wechat-posts").glob("*")):
        if not project.is_dir() or not resolve(project, '创作资料/cards.json').is_file():
            continue
        data = load_project(project)
        topics.append({
            "project": str(project.relative_to(workspace)), "title": data["title"],
            "theme": data["theme"], "content_structure": data["content_structure"],
            "scene_tags": data.get("scene_tags", []), "action_tags": data.get("action_tags", []),
            "scenes": [card["scene"] for card in data["cards"]],
            "roles": [card["role"] for card in data["cards"]],
            "status": "策划已建档；本索引未汇总认可与发布数据，请查看项目记录及案例",
        })
    # 仅在全部项目可解析后更新索引，避免错误时覆盖有效历史。
    entries = preferences(workspace)
    history = {"schema_version": 1, "topics": topics}
    save_json(workspace / MEMORY_DIR / "topic-history.json", history)
    preference_path = workspace / MEMORY_DIR / "preferences.json"
    if not preference_path.exists():
        save_json(preference_path, {"schema_version": 1, "entries": entries})
    return history


def record_preference(workspace: Path, *, kind: str, key: str, value: str, evidence: str, scope: str) -> None:
    entry = dict(kind=kind, key=key, value=value, evidence=evidence, scope=scope)
    if kind not in {"explicit", "inferred"} or any(not text.strip() for text in (key, value, evidence, scope)):
        raise ValueError("偏好需要合法类型、键、内容、证据和适用范围")
    entries = preferences(workspace)
    if entry not in entries:
        entries.append(entry)
    save_json(workspace / MEMORY_DIR / "preferences.json", {"schema_version": 1, "entries": entries})


def grams(text: str) -> set[str]:
    compact = "".join(re.findall(r"[\w]+", text.casefold()))
    return {compact[i:i + 2] for i in range(len(compact) - 1)} or set(compact)


def context(workspace: Path, query: str = "", exclude_project: str = "") -> dict:
    entries = preferences(workspace)
    history = read_json(workspace / MEMORY_DIR / "topic-history.json", {"schema_version": 1, "topics": []})
    if history.get("schema_version") != 1 or not isinstance(history.get("topics"), list):
        raise ValueError("topic-history.json 格式不可用；请运行 sync 重建")
    topics = []
    query_grams = grams(query)
    for topic in history["topics"]:
        if not isinstance(topic, dict) or not isinstance(topic.get("project"), str):
            raise ValueError("topic-history.json 项目记录非法；请运行 sync 重建")
        if topic["project"] == exclude_project:
            continue
        text = json.dumps({key: topic.get(key) for key in ("title", "theme", "scene_tags", "action_tags", "roles", "scenes")}, ensure_ascii=False)
        overlap = len(query_grams & grams(text))
        topics.append({**topic, "text_overlap": overlap})
    topics.sort(key=lambda item: (-item["text_overlap"], item["project"]))
    profile_path = workspace / MEMORY_DIR / 'account-profile.md'
    profile = {'status': 'missing', 'path': str(profile_path.relative_to(workspace))}
    if profile_path.is_file():
        content = profile_path.read_text(encoding='utf-8')
        profile.update(status='available' if content.strip() else 'empty', content=content)
    return {"account_profile": profile, "preferences": effective_preferences(entries), "topics": topics[:10],
            "note": "text_overlap 仅为字面重合数量，供人工检查重复主题、场景与动作；不代表语义相似度或传播效果。当前用户指令优先于历史偏好。"}


def main() -> int:
    ap = argparse.ArgumentParser(description="维护工作区偏好与历史选题；数据存于工作区 .content-remix/")
    sub = ap.add_subparsers(dest="command", required=True)
    for command in ("sync", "context", "preference"):
        parser = sub.add_parser(command)
        parser.add_argument("--workspace", type=Path, default=Path.cwd())
        if command == "context":
            parser.add_argument("--query", default="")
            parser.add_argument("--exclude-project", default="")
        elif command == "preference":
            parser.add_argument("--kind", choices=["explicit", "inferred"], required=True)
            for name in ("key", "value", "evidence"):
                parser.add_argument(f"--{name}", required=True)
            parser.add_argument("--scope", default="workspace")
    args = ap.parse_args()
    workspace = args.workspace.expanduser().resolve()
    try:
        if args.command == "sync":
            result = sync(workspace)
            print(f"已建档 {len(result['topics'])} 个项目：{workspace / MEMORY_DIR / 'topic-history.json'}")
        elif args.command == "context":
            print(json.dumps(context(workspace, args.query, args.exclude_project), ensure_ascii=False, indent=2))
        else:
            record_preference(workspace, kind=args.kind, key=args.key, value=args.value, evidence=args.evidence, scope=args.scope)
            print("偏好已记录；明确要求优先于推测，同类记录以最新明确要求为准。")
        return 0
    except (OSError, ValueError) as exc:
        print(f"工作区记录错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
