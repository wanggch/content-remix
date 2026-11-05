import json
import shutil
import tempfile
import unittest
from pathlib import Path
from test_skill import complete_project, sample_data, load_script


class SharedReferenceTest(unittest.TestCase):
    def test_two_articles_share_one_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shared = root / '对标资料/主题'
            shared.mkdir(parents=True)
            (shared / '对标分析.md').write_text('原文拆解')
            for name in ['a', 'b']:
                article = root / 'wechat-posts' / name
                complete_project(article, sample_data())
                if not (shared / '对标素材').exists():
                    shutil.copytree(article / '对标素材', shared / '对标素材')
                shutil.rmtree(article / '对标素材')
                (article / '创作资料/对标分析.md').unlink()
                ref = article / '创作资料/对标引用.json'
                ref.write_text(json.dumps({'schema_version':1, 'reference_path':'../../对标资料/主题'}))
                self.assertEqual(load_script('quality_check').inspect(article)[0], [])
            (shared / '对标分析.md').unlink()
            self.assertTrue(any('对标引用不可用' in x for x in load_script('quality_check').inspect(article)[0]))
