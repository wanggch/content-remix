import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from test_skill import load_script


class ReviewAgyTest(unittest.TestCase):
    def prepare(self, root):
        profile = root / '.content-remix/account-profile.md'
        profile.parent.mkdir()
        profile.write_text('宝妈读者')
        target = root / '对标资料/主题'
        target.mkdir(parents=True)
        (target / '对标分析.md').write_text('来源')
        (target / '标题方案.md').write_text('T01 候选')
        return target

    def test_success_no_auto_apply_and_explicit_model(self):
        mod = load_script('review_agy')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); target = self.prepare(root)
            process = MagicMock(returncode=0)
            process.communicate.return_value = ('具体问题：T01表达别扭', '')
            with patch.object(mod.subprocess, 'Popen', return_value=process) as mock:
                result = mod.run_review(root, target, 'titles')
            command = mock.call_args.args[0]
            self.assertIn('gemini-3.8-flash-high', command)
            self.assertNotIn('--disable-slash-commands', command)
            self.assertNotIn('--dangerously-skip-permissions', command)
            self.assertEqual(result['status'], 'review_returned')
            self.assertEqual((target / '标题方案.md').read_text(), 'T01 候选')
            self.assertEqual(len(result['input_sha256']), 3)

    def test_failure_replaces_stale_report(self):
        mod = load_script('review_agy')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); target = self.prepare(root)
            process = MagicMock(returncode=1)
            process.communicate.return_value = ('partial', 'timeout')
            with patch.object(mod.subprocess, 'Popen', return_value=process):
                result = mod.run_review(root, target, 'titles')
            self.assertEqual(result['status'], 'failed')
            self.assertIn('未完成', (target / '记录/标题独立复核.md').read_text())
