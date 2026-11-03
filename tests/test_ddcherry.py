import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from test_skill import load_script, sample_data, write_data, write_png


class DDCherryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.data = sample_data()
        write_data(self.project, self.data)
        self.mod = load_script('render_ddcherry')
        self.args = ['--project', str(self.project)]

    def provider(self):
        image = self.project / 'output/images/test.png'
        write_png(image)
        return SimpleNamespace(MODEL='test-model', generate=Mock(return_value=('test-model', [image])))

    def test_preview_no_provider_or_files(self):
        with patch.object(self.mod, 'load_provider') as load:
            self.assertEqual(self.mod.main(self.args), 0)
            load.assert_not_called()
        self.assertFalse((self.project / 'generated').exists())

    def test_generate_mapping_text_and_skip(self):
        provider = self.provider()
        with patch.object(self.mod, 'load_provider', return_value=provider):
            self.assertEqual(self.mod.main(self.args + ['--yes']), 0)
            self.assertEqual(provider.generate.call_count, len(self.data['cards']))
            for call, card in zip(provider.generate.call_args_list, self.data['cards']):
                self.assertIn(card['caption'], call.args[1])
                self.assertEqual(call.args[2], '768x1024')
            self.assertEqual(self.mod.main(self.args + ['--yes']), 0)
            self.assertEqual(provider.generate.call_count, len(self.data['cards']))
        manifest = json.loads((self.project / 'generated/ddcherry/manifest.json').read_text())
        self.assertTrue(all(e['review'] == 'pending' for e in manifest['cards'].values()))

    def test_failure_stops_and_blocks_retry(self):
        provider = self.provider()
        provider.generate.side_effect = OSError('offline')
        with patch.object(self.mod, 'load_provider', return_value=provider):
            self.assertEqual(self.mod.main(self.args + ['--yes']), 1)
            self.assertEqual(self.mod.main(self.args + ['--yes']), 2)
        self.assertEqual(provider.generate.call_count, 1)

    def test_ratio_and_invalid_image(self):
        self.assertEqual(self.mod.main(self.args + ['--size', '1024x1024']), 2)
        with self.assertRaises(ValueError):
            self.mod.inspect_image(b'not an image')

    def test_white_background_normalization(self):
        from PIL import Image
        source = self.project / 'transparent.png'
        image = Image.new('RGBA', (3, 4), (0, 0, 0, 0))
        image.putpixel((1, 1), (0, 0, 0, 255))
        image.putpixel((2, 1), (0, 0, 0, 128))
        image.save(source)
        destination = self.project / 'white.png'
        result = self.mod.normalize_image(source, destination)
        self.assertEqual(result['source_alpha_extrema'], [0, 255])
        with Image.open(destination) as output:
            self.assertEqual(output.mode, 'RGB')
            self.assertEqual(output.size, (3, 4))
            self.assertEqual(output.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(output.getpixel((1, 1)), (0, 0, 0))
            self.assertEqual(output.getpixel((2, 1)), (127, 127, 127))
        with Image.open(source) as original:
            self.assertEqual(original.mode, 'RGBA')

    def test_single_card(self):
        provider = self.provider()
        with patch.object(self.mod, 'load_provider', return_value=provider):
            self.assertEqual(self.mod.main(self.args + ['--card', '1', '--yes']), 0)
        self.assertEqual(provider.generate.call_count, 1)
