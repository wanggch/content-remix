"""Offline regression tests: python3 -m unittest discover -s tests -v."""
from __future__ import annotations

import copy
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sample_data(structure: str = "parallel") -> dict:
    catalog = json.loads((ROOT / "evals/cases.json").read_text(encoding="utf-8"))
    case = next(case for case in catalog["cases"] if case["content_structure"] == structure)
    data = copy.deepcopy(catalog["base"])
    for key in ("content_structure", "scene_policy", "cards"):
        data[key] = copy.deepcopy(case[key])
    data["format_contract"]["structure"] = {"source": structure, "target": structure, "evidence": "测试输入的结构要求"}
    return data


def write_data(project: Path, data: dict) -> None:
    (project / '创作资料').mkdir(parents=True, exist_ok=True)
    (project / "创作资料/cards.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cli(name: str, *args: object, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py"), *map(str, args)], capture_output=True, text=True, **kwargs)


def complete_project(project: Path, data: dict) -> None:
    write_data(project, data)
    for name in ["对标素材/source.md", "创作资料/对标分析.md", "创作资料/选题与分镜.md", "创作资料/选题与分镜.md", "发布文案.md", "记录/审核.md"]:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("离线测试文档", encoding="utf-8")
    (project / "对标素材/source.json").write_text('{"status": "ok"}', encoding="utf-8")
    result = cli("build_prompt", "--project", project)
    if result.returncode:
        raise AssertionError(result.stderr)


def write_png(path: Path, width: int = 3, height: int = 4) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = (b"\x00" + b"\x78\x8c\x96" * width) * height
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                     + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


class SkillTest(unittest.TestCase):
    def test_parser_title_and_image_order(self):
        mod = load_script("ingest")
        parser = mod.ArticleParser()
        parser.feed('''<html><head><title>备选标题</title><meta property="og:title" content="标题A"></head>
        <body><h1 id="activity-name">标题A</h1><div id="js_content">
        <p>第一段。欢迎来到周末。</p><img data-src="https://mmbiz.qpic.cn/one" />
        <section><p>第二段。</p></section></div></body></html>''')
        self.assertEqual(parser.title, "标题A")
        self.assertEqual(parser.heading_title, "标题A")
        result = mod.render_text(parser.tokens, {"https://mmbiz.qpic.cn/one": {"index": 1, "local_path": "images/01.png"}})
        self.assertLess(result.index("第一段"), result.index("images/01.png"))
        self.assertLess(result.index("images/01.png"), result.index("第二段"))

    def test_ingest_local_html_offline(self):
        mod = load_script("ingest")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "article.html"
            source.write_text('<meta property="og:title" content="原创素材"><div id="js_content">'
                              '<p>原文第一段，有清晰的情绪冲突和很多细节。</p>'
                              '<img data-src="https://mmbiz.qpic.cn/one">'
                              '<p>原文第二段，说明最终转折与情绪。</p></div>', encoding="utf-8")
            image = root / "source.png"
            write_png(image)
            with patch.object(mod, "get_url_content", return_value=(image.read_bytes(), "image/png")), \
                 patch.object(sys, "argv", ["ingest.py", "--html", str(source), "--out", str(root / "case")]):
                self.assertEqual(mod.main(), 0)
            doc = (root / "case/对标素材/source.md").read_text(encoding="utf-8")
            self.assertTrue(doc.index("第一段") < doc.index("images/01.png") < doc.index("第二段"))
            data = json.loads((root / "case/对标素材/source.json").read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["title"], "原创素材")

    def test_screenshots_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shot = root / "article-01.png"
            write_png(shot)
            result = cli("ingest", "--screenshots", shot, "--out", root / "case")
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((root / "case/对标素材/source.json").read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "partial")
            self.assertTrue((root / "case/对标素材/screenshots/01.png").exists())

    def test_render_dry_run_never_needs_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = sample_data()
            write_data(root, data)
            result = cli("render_ddcherry", "--project", root, env={})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("仅预览", result.stdout)
            self.assertFalse((root / '.tmp').exists())
            disabled = cli('render_images', '--project', root)
            self.assertEqual(disabled.returncode, 2)
            self.assertIn('已停用', disabled.stderr)

    def test_single_batch_preserves_full_text_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = sample_data()
            write_data(root, data)
            original = (root / "创作资料/cards.json").read_bytes()
            result = cli("build_prompt", "--project", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            batch = root / "创作提示词.md"
            content = batch.read_text(encoding="utf-8")
            self.assertEqual([path.name for path in batch.parent.glob('*.md')], ["创作提示词.md"])
            for card in data["cards"]:
                self.assertIn(card["caption"], content)
                self.assertIn(card["scene"], content)
            self.assertIn("场景和时间可不同", content)
            self.assertNotIn("结尾回应开场", content)
            self.assertEqual(cli("build_prompt", "--project", root).returncode, 0)
            self.assertEqual(batch.read_text(encoding="utf-8"), content)
            self.assertEqual((root / "创作资料/cards.json").read_bytes(), original)

    def test_contract_can_precede_storyboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = sample_data()
            data["cards"] = []
            write_data(root, data)
            result = cli("build_prompt", "--project", root, "--contract-only")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / "创作资料/创作约束.md").is_file())
            self.assertFalse((root / "创作提示词.md").exists())
            self.assertEqual(cli("build_prompt", "--project", root).returncode, 2)

    def test_incomplete_explanation_and_placeholders_are_rejected(self):
        mod = load_script("build_prompt")
        data = sample_data()
        data["cards"][0]["caption"] = data["cards"][0]["bubble_text"]
        with self.assertRaisesRegex(ValueError, "caption 与气泡、底文不一致"):
            mod.validate(data)
        data = sample_data()
        data["cards"][0]["bubble_text"] += "\n慢慢吃。"
        data["cards"][0]["caption"] = data["cards"][0]["bubble_text"] + "\n" + data["cards"][0]["body_text"]
        mod.validate(data)
        self.assertIn("前2行放气泡", mod.render_batch(data))
        for text in ["〔完整动作〕", "【填写文案】", "{{scene}}", "```text"]:
            data = sample_data()
            data["cards"][0]["scene"] = text
            with self.assertRaisesRegex(ValueError, "占位符|代码块"):
                mod.validate(data)

    def test_invalid_json_shapes_produce_errors_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_card = sample_data()
            bad_card["cards"] = [None]
            bad_structure = sample_data()
            bad_structure["content_structure"] = []
            for payload in [[], {"schema_version": 2}, bad_card, bad_structure]:
                write_data(root, payload)
                result = cli("build_prompt", "--project", root)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)
                errors, _, _ = load_script("quality_check").inspect(root)
                self.assertTrue(errors)

    def test_changed_structure_requires_reason_and_unknown_is_visible(self):
        mod = load_script("build_prompt")
        data = sample_data()
        data["format_contract"]["structure"]["source"] = "story"
        with self.assertRaisesRegex(ValueError, "change_reason"):
            mod.validate(data)
        data["format_contract"]["structure"]["change_reason"] = "测试用户明确要求改成并列卡"
        mod.validate(data)
        data["format_contract"]["structure"]["source"] = "unknown"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            complete_project(root, data)
            errors, warnings, _ = load_script("quality_check").inspect(root)
            self.assertEqual(errors, [])
            self.assertTrue(any("未知素材" in warning for warning in warnings))

    def test_stale_batch_and_contract_fail_until_regenerated(self):
        mod = load_script("quality_check")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = sample_data()
            complete_project(root, data)
            data["cards"][1]["caption"] = "你先出门，垃圾我来带。"
            data["format_contract"]["tone"]["target"] = "更简洁的生活口语"
            write_data(root, data)
            errors, _, _ = mod.inspect(root)
            self.assertTrue(any("创作提示词.md 与" in error for error in errors))
            self.assertTrue(any("创作资料/创作约束.md 与" in error for error in errors))
            self.assertEqual(cli("build_prompt", "--project", root).returncode, 0)
            self.assertEqual(mod.inspect(root)[0], [])
            batch = root / "创作提示词.md"
            batch.write_text(batch.read_text(encoding="utf-8").replace(data["cards"][0]["caption"], "漏掉解释"), encoding="utf-8")
            self.assertTrue(any("创作提示词.md 与" in error for error in mod.inspect(root)[0]))

    def test_invalid_data_does_not_overwrite_existing_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = sample_data()
            complete_project(root, data)
            batch = root / "创作提示词.md"
            original = batch.read_bytes()
            data["cards"][0]["caption"] = "遗漏底文"
            write_data(root, data)
            self.assertEqual(cli("build_prompt", "--project", root).returncode, 2)
            self.assertEqual(batch.read_bytes(), original)

    def test_nondefault_count_ratio_and_complete_image_files(self):
        mod = load_script("quality_check")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = sample_data()
            data["cards"].append({**data["cards"][1], "index": 3})
            data["aspect_ratio"] = "16:9"
            complete_project(root, data)
            self.assertTrue(any("最终带字图未全部生成" in warning for warning in mod.inspect(root, check_images=True)[1]))
            for index in range(1, 4):
                write_png(root / "图片" / f"{index:02d}.png", 16, 9)
            result = cli("quality_check", "--project", root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("FAIL=0 WARN=0", result.stdout)
            (root / "图片/01.png").write_text("不是PNG", encoding="utf-8")
            self.assertTrue(any("文件无效" in error for error in mod.inspect(root, check_images=True)[0]))

    def test_preference_priority_evidence_and_scope(self):
        mod = load_script("project_memory")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def record(kind, value, scope="workspace"):
                mod.record_preference(root, kind=kind, key="tone", value=value, evidence="测试用户原话或观察", scope=scope)
            record("inferred", "推测喜欢短句")
            record("explicit", "保留解释")
            record("inferred", "推测只要标语")
            record("explicit", "保留完整生活解释")
            record("explicit", "账号内更简洁", "account:示例")
            records = mod.context(root)["preferences"]
            self.assertEqual(next(item["value"] for item in records if item["scope"] == "workspace"), "保留完整生活解释")
            self.assertEqual(len(records), 2)
            self.assertTrue(all(item["evidence"] for item in records))
            with self.assertRaises(ValueError):
                mod.record_preference(root, kind="explicit", key="tone", value="短句", evidence="", scope="workspace")

    def test_history_sync_query_and_deletion_preserve_preferences(self):
        mod = load_script("project_memory")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "wechat-posts/a"
            b = root / "wechat-posts/b"
            first, second = sample_data(), sample_data("tutorial")
            first["scene_tags"] = ["餐桌吃饭"]
            second["scene_tags"] = ["饭盒分装"]
            write_data(a, first)
            write_data(b, second)
            mod.record_preference(root, kind="explicit", key="tone", value="完整解释", evidence="测试原话", scope="workspace")
            preference_path = root / ".content-remix/preferences.json"
            original = preference_path.read_bytes()
            self.assertEqual(len(mod.sync(root)["topics"]), 2)
            result = mod.context(root, "饭盒分装")
            self.assertEqual(result["topics"][0]["project"], "wechat-posts/b")
            self.assertEqual(len(mod.context(root, exclude_project="wechat-posts/a")["topics"]), 1)
            (a / "创作资料/cards.json").unlink()
            self.assertEqual(len(mod.sync(root)["topics"]), 1)
            self.assertEqual(preference_path.read_bytes(), original)
            history_path = root / ".content-remix/topic-history.json"
            old_history = history_path.read_bytes()
            (b / "创作资料/cards.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                mod.sync(root)
            self.assertEqual(history_path.read_bytes(), old_history)

    def test_four_structures_regression_and_semantic_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.md"
            result = cli("evaluate", "--out", report)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            text = report.read_text(encoding="utf-8")
            self.assertIn("4/4 通过", text)
            self.assertEqual(text.count("程序检查：PASS"), 4)
            self.assertIn("语义评估未执行", text)
            self.assertIn("案例类型：synthetic", text)
            catalog = json.loads((ROOT / "evals/cases.json").read_text(encoding="utf-8"))
            catalog["cases"][0]["status"] = "user_approved"
            unverified = Path(tmp) / "unverified.json"
            unverified.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
            rejected = cli("evaluate", "--cases", unverified)
            self.assertEqual(rejected.returncode, 1)
            self.assertIn("必须附 approval_evidence", rejected.stdout)

    def test_installed_skill_runs_outside_source_without_personal_memory(self):
        with tempfile.TemporaryDirectory(prefix="content remix ") as tmp:
            workspace = Path(tmp)
            result = subprocess.run(["bash", str(ROOT / "install.sh"), "codex"], cwd=workspace, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = workspace / ".agents/skills/content-remix"
            self.assertTrue((installed / "evals/cases.json").is_file())
            self.assertFalse((installed / ".content-remix").exists())
            data_project = workspace / "wechat-posts/example"
            write_data(data_project, sample_data())
            for script, args in [("build_prompt", ["--project", str(data_project)]), ("evaluate", [])]:
                result = subprocess.run([sys.executable, str(installed / "scripts" / f"{script}.py"), *args], cwd=workspace, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((data_project / '创作提示词.md').is_file())


if __name__ == "__main__":
    unittest.main()
