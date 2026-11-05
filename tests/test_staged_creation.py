import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StagedCreationRulesTest(unittest.TestCase):
    def test_main_flow_has_two_explicit_stops(self):
        text = (ROOT / 'SKILL.md').read_text()
        self.assertIn('10个真正不同的主题', text)
        self.assertIn('停止，等待确认', text)
        self.assertIn('停止，等待大纲确认', text)
        self.assertIn('标题方案.md', text)
        self.assertIn('大纲.md', text)
        self.assertNotIn('标题选择不新增强制确认关卡', text)

    def test_title_library_is_reusable_and_not_automatic_creation(self):
        text = (ROOT / 'references/title-strategy.md').read_text()
        self.assertIn('T01—T10', text)
        self.assertIn('未选项保留', text)
        self.assertIn('关联列表', (ROOT / 'SKILL.md').read_text())
        self.assertIn('不能继续大纲', text)
        self.assertIn('不默认新增3个发布标题候选', text)
