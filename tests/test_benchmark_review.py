"""Documentation wiring only; not a semantic-quality evaluator."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BenchmarkReviewContractTest(unittest.TestCase):
    def test_default_delivery_requires_evidence_based_review(self):
        text = (ROOT / 'SKILL.md').read_text()
        self.assertIn('交付前必须读取 `references/benchmark-review.md`', text)
        self.assertIn('原文证据、新稿证据', text)
        self.assertIn('重新编译', text)
        self.assertIn('不等用户要求比对', text)

    def test_all_seven_review_dimensions_and_counterexamples_exist(self):
        text = (ROOT / 'references/benchmark-review.md').read_text()
        for heading in ['内容维度与覆盖', '标题的情绪与实际收益', '例子能否支撑观点', '场景的代入门槛', '内容类型与语气', '图文动作、时刻与情绪尺度', '形式取舍是否损害表达']:
            self.assertIn(heading, text)
        self.assertIn('不要求同数量', text)
        self.assertIn('不是自动质量判定', text)
        cases = (ROOT / 'evals/benchmark-review.md').read_text()
        self.assertIn('摄影师伴侣', cases)
        self.assertIn('不强制改代词', cases)

    def test_checklist_and_titles_link_review_without_image_gate(self):
        qa = (ROOT / 'references/qa-checklist.md').read_text()
        self.assertIn('缺图不构成当前交付阻断', qa)
        for path in ['references/qa-checklist.md', 'references/title-strategy.md']:
            self.assertIn('benchmark-review.md', (ROOT / path).read_text())
