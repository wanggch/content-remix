#!/usr/bin/env python3
"""Run synthetic creative regression cases and report semantic checks as pending."""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from build_prompt import BATCH_PATH, CONTRACT_PATH, validate

SKILL_ROOT = Path(__file__).resolve().parents[1]


def case_data(base: dict, case: dict) -> dict:
    if case.get("status") not in {"synthetic", "user_approved"}:
        raise ValueError("案例状态必须是 synthetic 或 user_approved")
    if case["status"] == "user_approved" and (not isinstance(case.get("approval_evidence"), str) or not case["approval_evidence"].strip()):
        raise ValueError("用户认可案例必须附 approval_evidence，不得推测认可")
    data = copy.deepcopy(base)
    for key in ("content_structure", "scene_policy", "cards"):
        data[key] = copy.deepcopy(case[key])
    data["format_contract"]["structure"] = {
        "source": case["content_structure"], "target": case["content_structure"],
        "evidence": ("案例结构要求；用户认可依据：" + case["approval_evidence"]
                     if case["status"] == "user_approved" else "合成回归案例的明确结构要求，非真实对标观察"),
    }
    return validate(data)


def evaluate(catalog: Path) -> tuple[str, int]:
    source = json.loads(catalog.read_text(encoding="utf-8"))
    results = []
    for case in source["cases"]:
        errors = []
        try:
            data = case_data(source["base"], case)
            with tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                original = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
                (project / "cards.json").write_text(original, encoding="utf-8")
                run = subprocess.run([sys.executable, str(SKILL_ROOT / "scripts/build_prompt.py"), "--project", str(project)], capture_output=True, text=True)
                if run.returncode:
                    raise ValueError(run.stderr.strip() or "生成命令失败")
                prompt = (project / BATCH_PATH).read_text(encoding="utf-8")
                for text in case["must_include"]:
                    if text not in prompt:
                        errors.append(f"缺少结构要求：{text}")
                for text in case["must_not_include"]:
                    if text in prompt:
                        errors.append(f"误套其他结构规则：{text}")
                for card in data["cards"]:
                    if card["caption"] not in prompt or card["scene"] not in prompt:
                        errors.append(f"第{card['index']}张完整文案或画面缺失")
                delivered = {path.relative_to(project) for path in project.rglob("*.md")}
                if delivered != {BATCH_PATH, CONTRACT_PATH}:
                    errors.append("交付文件不符合单份整组提示词约定")
                if (project / "cards.json").read_text(encoding="utf-8") != original:
                    errors.append("生成脚本改写了创作数据")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(str(exc))
        results.append((case, errors))
    lines = ["# 创作回归评估", "", "本报告验证程序性约定。合成案例未经用户作品认可，语感、审美、视觉与原创性仍待实际审查。", ""]
    failures = 0
    for case, errors in results:
        failures += bool(errors)
        lines.extend([f"## {case['id']}", "", f"- 案例类型：{case['status']}",
                      f"- 程序检查：{'FAIL' if errors else 'PASS'}"])
        lines.extend(f"- 问题：{error}" for error in errors)
        lines.extend(f"- 待语义审查：{item}" for item in case["semantic_checks"])
        lines.append("")
    lines.append(f"程序结果：{len(results) - failures}/{len(results)} 通过。语义评估未执行，不据此宣称创作质量已获认可。\n")
    return "\n".join(lines), failures


def main() -> int:
    ap = argparse.ArgumentParser(description="运行固定创作案例，输出程序检查与待语义检查报告")
    ap.add_argument("--cases", type=Path, default=SKILL_ROOT / "evals/cases.json")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    try:
        report, failures = evaluate(args.cases)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(report, encoding="utf-8")
            print(f"评估报告：{args.out}")
        print(report)
        return 1 if failures else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"评估数据错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
