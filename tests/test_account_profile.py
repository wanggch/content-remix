import json
import tempfile
import unittest
from pathlib import Path
from test_skill import load_script


class AccountProfileTest(unittest.TestCase):
    def setUp(self):
        self.module = load_script('project_memory')

    def test_profile_is_returned_in_full_and_scoped_to_workspace(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            root = Path(a)
            p = root / '.content-remix/account-profile.md'
            p.parent.mkdir()
            text = '# 定位\n受众为宝妈，不强加育儿主题。\n'
            p.write_text(text)
            result = self.module.context(root)
            self.assertEqual(result['account_profile']['content'], text)
            self.assertEqual(result['account_profile']['status'], 'available')
            self.assertEqual(self.module.context(Path(b))['account_profile']['status'], 'missing')
            p.write_text('')
            self.assertEqual(self.module.context(root)['account_profile']['status'], 'empty')

    def test_superseded_cross_key_preference_is_excluded_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = [dict(kind='explicit', key='provider', value='API', evidence='旧要求', scope='workspace', status='superseded'),
                       dict(kind='explicit', key='delivery', value='仅提示词', evidence='新要求', scope='workspace')]
            p = root / '.content-remix/preferences.json'
            p.parent.mkdir()
            p.write_text(json.dumps({'schema_version':1, 'entries':entries}))
            before = p.read_bytes()
            self.assertEqual(self.module.context(root)['preferences'], entries[1:])
            self.assertEqual(p.read_bytes(), before)

    def test_legacy_entries_remain_active(self):
        entry = dict(kind='explicit', key='audience', value='宝妈', evidence='用户原话', scope='workspace')
        self.assertEqual(self.module.effective_preferences([entry]), [entry])
