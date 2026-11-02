"""Offline smoke tests; run: python3 -m unittest discover -s tests -v"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_script(name: str):
    # 直接按文件路径加载独立 CLI 脚本，无需将 scripts 改成 Python 包。
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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
            p = root / "article.html"
            p.write_text('<meta property="og:title" content="原创素材"><div id="js_content">'
                         '<p>原文第一段，有清晰的情绪冲突和很多细节。</p>'
                         '<img data-src="https://mmbiz.qpic.cn/one">'
                         '<p>原文第二段，来说明故事的最终转折与情绪。</p></div>', encoding="utf-8")
            # 模拟下载响应，确保采集测试离线运行；这里只验证落盘，不解码图片。
            fake_png = b"\x89PNG\r\n\x1a\n" + b"fake_data"
            with patch.object(mod, "get_url_content", return_value=(fake_png, "image/png")), \
                 patch.object(sys, "argv", ["ingest.py", "--html", str(p), "--out", str(root / "case")]):
                self.assertEqual(mod.main(), 0)
            doc = (root / "case/00-source/source.md").read_text()
            self.assertTrue((root / "case/00-source/images/01.png").is_file())
            self.assertTrue(doc.index("第一段") < doc.index("images/01.png") < doc.index("第二段"))
            j = json.loads((root / "case/00-source/source.json").read_text())
            self.assertEqual(j["status"], "ok")
            self.assertEqual(j["title"], "原创素材")

    def test_screenshots_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shot = root / "article-01.png"
            shot.write_bytes(b"\x89PNG\r\n\x1a\n")
            r = subprocess.run([sys.executable, str(SCRIPTS / "ingest.py"), "--screenshots", str(shot), "--out", str(root / "case")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads((root / "case/00-source/source.json").read_text())
            self.assertEqual(data["status"], "partial")
            self.assertTrue((root / "case/00-source/screenshots/01.png").exists())

    def test_render_dry_run_never_needs_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cards.json").write_text(json.dumps({"title":"测试", "cards":[{"index":1,"image_prompt":"一幅原创竖版图片，不要任何文字。"}]}, ensure_ascii=False), encoding="utf-8")
            # 清空环境，验证未配置 API Key 时预览仍可成功，且不会生成图片。
            r = subprocess.run([sys.executable, str(SCRIPTS / "render_images.py"), "--project", str(root)], capture_output=True, text=True, env={})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("未调用 API", r.stdout)
            self.assertFalse((root / "generated/01.png").exists())

    def test_quality_checker_detects_missing_artifacts(self):
        mod = load_script("quality_check")
        with tempfile.TemporaryDirectory() as tmp:
            errors, warnings, info = mod.inspect(Path(tmp))
            self.assertTrue(errors)
            self.assertTrue(warnings)
            self.assertTrue(info)

    def test_dialogue_card_preserves_full_explanation(self):
        mod = load_script("quality_check")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "prompts").mkdir()
            for name in mod.REQUIRED:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("待审核", encoding="utf-8")
            bubble = "你先吃，我来抱一会儿。"
            body = "这是需要完整保留的生活解释。" * 6
            caption = bubble + "\n" + body
            prompt = "上气泡下解释，完整文字：\n" + caption
            cards = [{"index": i, "role": "并列", "bubble_text": bubble,
                      "body_text": body, "caption": caption, "alt": "家庭场景",
                      "image_prompt": prompt} for i in range(1, 5)]
            for i in range(1, 5):
                (root / "prompts" / f"{i:02d}.md").write_text(prompt, encoding="utf-8")
            data = {"title": "具体关心", "cards": cards}
            (root / "cards.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            errors, warnings, _ = mod.inspect(root)
            self.assertEqual(errors, [])
            self.assertFalse(any("精简" in w or "60字" in w for w in warnings))
            cards[0]["caption"] = bubble
            (root / "cards.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            errors, _, _ = mod.inspect(root)
            self.assertTrue(any("caption 与气泡、底文不一致" in e for e in errors))
            cards[0]["caption"] = caption
            cards[0]["image_prompt"] = bubble
            (root / "cards.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            errors, _, _ = mod.inspect(root)
            self.assertTrue(any("未包含完整准确 caption" in e for e in errors))

    def test_direct_captioned_images_need_no_base_images(self):
        mod = load_script("quality_check")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "prompts").mkdir()
            (root / "final").mkdir()
            cards = []
            for i in range(1, 5):
                prompt = f"带字竖图，准确绘制文字：文案{i}。"
                cards.append({"index": i, "role": "递进", "caption": f"文案{i}", "alt": "生活场景", "image_prompt": prompt})
                (root / "prompts" / f"{i:02d}.md").write_text(prompt, encoding="utf-8")
                # 结构检查只读取 PNG 头；此测试不模拟完整图片或视觉审核。
                header = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + (768).to_bytes(4, "big") + (1024).to_bytes(4, "big")
                (root / "final" / f"{i:02d}.png").write_bytes(header)
            for name in mod.REQUIRED:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("测试文档", encoding="utf-8")
            (root / "cards.json").write_text(json.dumps({"title": "测试", "cards": cards}, ensure_ascii=False), encoding="utf-8")
            (root / "00-source/source.json").write_text('{"status": "ok"}', encoding="utf-8")
            errors, warnings, _ = mod.inspect(root)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])
            self.assertFalse((root / "generated").exists())

    def test_end_to_end_artifact_pipeline_offline(self):
        # 用纯色底图代替付费生图，只验证导入、叠字和结构审核的离线链路。
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("No Pillow")
        compose = load_script("compose_cards")
        try:
            font = compose.find_font(None)
        except FileNotFoundError:
            self.skipTest("No Chinese font")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "original.md"
            src.write_text("# 一篇示例文章\n\n一段有内容的原创素材介绍。", encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPTS / "ingest.py"), "--text", str(src), "--out", str(root / "project")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            proj = root / "project"
            cards = []
            for i in range(1, 5):
                prompt = f"单张原创生活摄影，第{i}张。没有文字，没有水印。"
                cards.append({"index": i, "role": f"情绪递进{i}", "caption": f"原创的第{i}张图片文字。", "alt": "日常生活", "image_prompt": prompt})
                (proj / "prompts" / f"{i:02d}.md").write_text(prompt, encoding="utf-8")
                Image.new("RGB", (768, 1152), (120+i, 140+i, 150+i)).save(proj / "generated" / f"{i:02d}.png")
            (proj / "cards.json").write_text(json.dumps({"title": "原创周末的四个瞬间", "cards": cards}, ensure_ascii=False), encoding="utf-8")
            for doc in ["01-analysis.md", "02-topics.md", "03-storyboard.md", "04-publish.md", "05-review.md"]:
                (proj / doc).write_text("# 测试用结构化内容\n\n这是离线测试文本", encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPTS / "compose_cards.py"), "--project", str(proj), "--font", font], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            r = subprocess.run([sys.executable, str(SCRIPTS / "quality_check.py"), "--project", str(proj)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("FAIL=0", r.stdout)
            with Image.open(proj / "final/01.png") as im:
                self.assertAlmostEqual(im.width / im.height, 0.75, delta=0.002)

    def test_compose_text_using_font(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("No Pillow")
        mod = load_script("compose_cards")
        try:
            font = mod.find_font(None)
        except FileNotFoundError:
            self.skipTest("No Chinese font")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "generated").mkdir()
            Image.new("RGB", (800, 1200), (120, 142, 120)).save(root / "generated/01.png")
            (root / "cards.json").write_text(json.dumps({"cards":[{"index":1,"caption":"这是第一张图的原创文案。"}]}, ensure_ascii=False))
            r = subprocess.run([sys.executable, str(SCRIPTS / "compose_cards.py"), "--project", str(root), "--font", font], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((root / "final/01.png").exists())


if __name__ == "__main__":
    unittest.main()
