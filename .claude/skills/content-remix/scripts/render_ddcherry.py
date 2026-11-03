#!/usr/bin/env python3
"""One batch prompt, one provider call, no per-card fallback or automatic retry."""
from __future__ import annotations
import argparse
import importlib.util
import inspect
import json
import os
import re
import sys
from pathlib import Path
from build_prompt import load_project, batch_prompt
from project_paths import MANIFEST, TEMP

DEFAULT_SCRIPT = Path.home() / '.codex/skills/ddcherry-image/scripts/generate.py'


def load_provider(path):
    spec = importlib.util.spec_from_file_location('content_remix_ddcherry', path)
    if spec is None or spec.loader is None:
        raise ValueError('无法加载DDCherry脚本')
    provider = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provider)
    return provider


def normalize_image(source, destination):
    from PIL import Image
    with Image.open(source) as image:
        image.load()
        rgba = image.convert('RGBA')
        extrema = rgba.getchannel('A').getextrema()
        output = Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('RGB')
        temp = destination.with_suffix('.tmp')
        output.save(temp, format='PNG')
        temp.replace(destination)
        return {'actual_size': list(output.size), 'normalization': 'white_background_rgb_png',
                'source_alpha_extrema': list(extrema)}


def save_manifest(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--script', type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument('--size', default='768x1024')
    parser.add_argument('--quality', choices=['auto', 'low', 'medium', 'high'])
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args(argv)
    project = args.project.expanduser().resolve()
    try:
        data = load_project(project)
        prompt = batch_prompt(data)
        match = re.fullmatch(r'([1-9]\d*)x([1-9]\d*)', args.size)
        if not match:
            raise ValueError('size必须为宽x高')
        w, h = map(int, match.groups())
        rw, rh = map(int, data['aspect_ratio'].split(':'))
        if w * rh != h * rw:
            raise ValueError('尺寸与创作比例不一致')
        expected = len(data['cards'])
        print(f'整组单次请求；计划{expected}张独立图片；提示词{len(prompt)}字符。')
        if not args.yes:
            print('仅预览。DDCherry单次返回多图能力待实测，不自动逐张回退。')
            return 0
        from PIL import Image  # Dependency check before loading provider or requesting.
        manifest_path = project / MANIFEST
        if manifest_path.exists() or any((project / '图片').glob('*.png')):
            raise ValueError('已有生成记录或成品，停止以避免重复调用；请先人工核对')
        provider = load_provider(args.script.expanduser().resolve())
        parameters = inspect.signature(provider.generate).parameters
        if 'n' not in parameters and not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values()):
            raise ValueError('DDCherry脚本未支持显式数量n，请先更新适配；不发送可能默认为单图的请求')
        target = project / TEMP
        if target.exists() and any(target.iterdir()):
            raise ValueError('存在待处理的临时图片，请先人工核对')
        target.mkdir(parents=True, exist_ok=True)
        manifest = {'schema_version': 2, 'mode': 'single_request_batch', 'expected_count': expected,
                    'status': 'requesting', 'model': provider.MODEL, 'review': 'pending',
                    'capability': 'unverified', 'requested_n': expected, 'files': []}
        save_manifest(manifest_path, manifest)
        try:
            previous = Path.cwd()
            try:
                os.chdir(project)
                model, paths = provider.generate(project / '.tmp', prompt, args.size, args.quality, n=expected)
            finally:
                os.chdir(previous)
            manifest.update(model=model, actual_count=len(paths), source_paths=[str(p) for p in paths])
            for i, source in enumerate(paths, 1):
                destination = target / f'{i:02d}.png'
                info = normalize_image(Path(source), destination)
                manifest['files'].append({'response_index': i, 'card_index': None,
                                          'path': str(destination.relative_to(project)), **info})
                save_manifest(manifest_path, manifest)
            if len(paths) != expected:
                manifest.update(status='incomplete', blocker='返回图片数量与计划不一致；不自动补图或拆拼图')
            elif any(f['actual_size'][0] * rh != f['actual_size'][1] * rw for f in manifest['files']):
                manifest.update(status='blocked', blocker='返回图片比例不一致')
            else:
                manifest.update(status='generated_pending_review', capability='count_observed_only')
            save_manifest(manifest_path, manifest)
            print(f'实际返回{len(paths)}张；{manifest["status"]}。需看图确认独立图片、顺序、文案与拼图问题。')
            return 0 if manifest['status'] == 'generated_pending_review' else 1
        except Exception as exc:
            reason = str(exc) if isinstance(exc, ValueError) or type(exc).__name__ == 'GenerationError' else type(exc).__name__
            manifest.update(status='failed', blocker=reason)
            save_manifest(manifest_path, manifest)
            print(f'整组请求失败：{reason}；不重试、不逐张回退。', file=sys.stderr)
            return 1
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        print(f'准备失败：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
