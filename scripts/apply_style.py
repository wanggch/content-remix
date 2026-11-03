#!/usr/bin/env python3
"""Explicitly copy a workspace visual profile into project cards, never identities/text."""
import argparse
import json
from pathlib import Path
from project_paths import CARDS


def apply(project, profile):
    path = Path(project) / CARDS
    data = json.loads(path.read_text())
    style = json.loads(Path(profile).read_text())
    for key in ['style_guide', 'layout']:
        if not isinstance(style.get(key), str) or not style[key].strip():
            raise ValueError(f'风格缺少{key}')
        data[key] = style[key]
    data['style_profile'] = {'id': style['id'], 'status': style['status']}
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    args = parser.parse_args()
    apply(args.project, args.profile)
    print('已应用视觉配置；人物、主题与文案未修改。请同步形式约束后重新编译整组提示词。')
