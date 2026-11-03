import json
import tempfile
import unittest
from pathlib import Path
from test_skill import sample_data, cli, write_png
from project_paths import resolve


class OrganizedProjectTest(unittest.TestCase):
    def test_build_check_and_memory(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            project = workspace / 'wechat-posts/example'
            (project / '创作资料').mkdir(parents=True)
            data = sample_data()
            resolve(project, '创作资料/cards.json').write_text(json.dumps(data, ensure_ascii=False))
            for name in ['对标素材/source.md', '创作资料/对标分析.md', '创作资料/选题与分镜.md', '发布文案.md', '记录/审核.md']:
                path = resolve(project, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('测试内容')
            resolve(project, '对标素材/source.json').write_text('{"status":"ok"}')
            for card in data['cards']:
                write_png(resolve(project, '图片') / f'{card["index"]:02d}.png')
            result = cli('build_prompt', '--project', project)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((project / '创作提示词.md').is_file())
            self.assertFalse((project / 'prompts').exists())
            result = cli('quality_check', '--project', project)
            self.assertEqual(result.returncode, 0, result.stdout)
            result = cli('project_memory', 'sync', '--workspace', workspace)
            self.assertEqual(result.returncode, 0, result.stderr)
            history = json.loads((workspace / '.content-remix/topic-history.json').read_text())
            self.assertEqual(len(history['topics']), 1)
