import tempfile
import unittest
from pathlib import Path
from test_skill import complete_project, sample_data, load_script


class TitleStrategyTest(unittest.TestCase):
    def test_long_title_is_not_a_programmatic_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            data = sample_data()
            data['title'] = '给老公情绪价值，不是哄着他，而是把这几句话说具体'
            self.assertGreater(len(data['title']), 20)
            complete_project(project, data)
            errors, warnings, _ = load_script('quality_check').inspect(project)
            self.assertEqual(errors, [])
            self.assertFalse(any('标题超过' in warning for warning in warnings))
            self.assertIn(data['title'], (project / '创作提示词.md').read_text())
