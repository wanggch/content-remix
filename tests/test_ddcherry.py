import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from test_skill import load_script, sample_data, write_data, write_png


class DDCherryBatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.data = sample_data()
        write_data(self.project, self.data)
        self.mod = load_script('render_ddcherry')
        self.args = ['--project', str(self.project)]

    def provider(self, count):
        paths = []
        for i in range(count):
            p = self.project / '.tmp/raw' / f'{i}.png'
            write_png(p)
            paths.append(p)
        return SimpleNamespace(MODEL='test', generate=Mock(return_value=('test', paths)))

    def test_preview_no_provider(self):
        with patch.object(self.mod, 'load_provider') as load:
            self.assertEqual(self.mod.main(self.args), 0)
            load.assert_not_called()
        self.assertFalse((self.project / '记录').exists())

    def test_single_request_complete_prompt(self):
        provider = self.provider(len(self.data['cards']))
        with patch.object(self.mod, 'load_provider', return_value=provider):
            self.assertEqual(self.mod.main(self.args + ['--yes']), 0)
            self.assertEqual(self.mod.main(self.args + ['--yes']), 2)
        provider.generate.assert_called_once()
        self.assertEqual(provider.generate.call_args.kwargs['n'], len(self.data['cards']))
        prompt = provider.generate.call_args.args[1]
        for card in self.data['cards']:
            self.assertIn(card['caption'], prompt)
            self.assertIn(card['scene'], prompt)
        manifest = json.loads((self.project / '记录/生成记录.json').read_text())
        self.assertEqual(manifest['status'], 'generated_pending_review')
        self.assertTrue(all(f['card_index'] is None for f in manifest['files']))

    def test_missing_images_no_fallback(self):
        provider = self.provider(1)
        with patch.object(self.mod, 'load_provider', return_value=provider):
            self.assertEqual(self.mod.main(self.args + ['--yes']), 1)
        provider.generate.assert_called_once()
        m = json.loads((self.project / '记录/生成记录.json').read_text())
        self.assertEqual(m['status'], 'incomplete')

    def test_failure_no_retry(self):
        provider = self.provider(0)
        provider.generate.side_effect = OSError('offline')
        with patch.object(self.mod, 'load_provider', return_value=provider):
            self.assertEqual(self.mod.main(self.args + ['--yes']), 1)
            self.assertEqual(self.mod.main(self.args + ['--yes']), 2)
        provider.generate.assert_called_once()

    def test_white_background(self):
        from PIL import Image
        source = self.project / 'transparent.png'
        Image.new('RGBA', (3, 4), (0, 0, 0, 0)).save(source)
        destination = self.project / 'white.png'
        self.mod.normalize_image(source, destination)
        with Image.open(destination) as image:
            self.assertEqual(image.mode, 'RGB')
            self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))

    def test_style_does_not_copy_characters(self):
        from apply_style import apply
        profile = self.project / 'style.json'
        profile.write_text(json.dumps({'id':'test','status':'provisional','style_guide':'新风格','layout':'新版式','characters':'不应复制'}))
        apply(self.project, profile)
        actual = json.loads((self.project / '创作资料/cards.json').read_text())
        self.assertEqual(actual['characters'], self.data['characters'])
        self.assertEqual(actual['cards'], self.data['cards'])
        self.assertEqual(actual['style_guide'], '新风格')
