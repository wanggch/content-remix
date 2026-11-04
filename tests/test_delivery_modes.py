import copy
import json
import tempfile
import unittest
from pathlib import Path
from test_skill import load_script, sample_data, complete_project


class DeliveryModesTest(unittest.TestCase):
    def test_images_are_opt_in_even_if_invalid_files_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            complete_project(root, sample_data())
            (root / '图片').mkdir()
            (root / '图片/01.png').write_text('invalid')
            mod = load_script('quality_check')
            errors, warnings, info = mod.inspect(root)
            self.assertEqual(errors, [])
            self.assertFalse(any('图片' in s or '带字图' in s for s in warnings + info))
            self.assertTrue(mod.inspect(root, check_images=True)[0])

    def test_explicit_regions_compile_positions_and_validate(self):
        mod = load_script('build_prompt')
        data = sample_data()
        card = data['cards'][0]
        card.pop('bubble_text', None)
        card.pop('body_text', None)
        card['text_regions'] = [dict(kind='heading', position='顶部', text='观点'),
                                dict(kind='body', position='标题下面', text='第一行\n第二行'),
                                dict(kind='bubble', position='下方妻子头顶', text='一句话')]
        card['caption'] = '\n'.join(r['text'] for r in card['text_regions'])
        mod.validate(data)
        text = mod.card_section(card)
        self.assertIn('第4—4行（bubble）放在下方妻子头顶', text)
        self.assertNotIn('底部解释区', text)
        for mutate in ['mismatch', 'mixed', 'invalid']:
            bad = copy.deepcopy(data)
            c = bad['cards'][0]
            if mutate == 'mismatch': c['caption'] += '错字'
            elif mutate == 'mixed': c['bubble_text'] = '重复'
            else: c['text_regions'][0]['kind'] = 'invalid'
            with self.assertRaises(ValueError): mod.validate(bad)

    def test_style_preserves_layout_unless_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            complete_project(root, sample_data())
            path = root / '创作资料/cards.json'
            before = json.loads(path.read_text())
            profile = root / 'style.json'
            profile.write_text(json.dumps(dict(id='x', status='provisional', style_guide='new', layout='other')))
            mod = load_script('apply_style')
            mod.apply(root, profile)
            after = json.loads(path.read_text())
            self.assertEqual(after['layout'], before['layout'])
            self.assertEqual(after['cards'], before['cards'])
            mod.apply(root, profile, include_layout=True)
            self.assertEqual(json.loads(path.read_text())['layout'], 'other')

    def test_prompt_uses_neutral_structure_and_prompt_endpoint(self):
        text = load_script('build_prompt').render_batch(sample_data())
        self.assertIn('并列卡片', text)
        self.assertNotIn('并列话术卡', text)
        self.assertNotIn('整组结果检查', text)
        self.assertIn('不要求回传', text)
