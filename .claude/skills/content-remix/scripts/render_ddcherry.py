#!/usr/bin/env python3
"""Render cards through the locally installed DDCherry skill; dry-run by default."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
import re
import struct
import sys
from pathlib import Path
from build_prompt import image_prompt, load_project

DEFAULT_SCRIPT = Path.home() / '.codex/skills/ddcherry-image/scripts/generate.py'


def load_provider(path):
    spec = importlib.util.spec_from_file_location('content_remix_ddcherry', path)
    if spec is None or spec.loader is None:
        raise ValueError('无法加载 DDCherry 脚本')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect_image(raw):
    if len(raw) >= 33 and raw.startswith(b'\x89PNG\r\n\x1a\n') and raw[12:16] == b'IHDR':
        width, height = struct.unpack('>II', raw[16:24])
        if not width or not height:
            raise ValueError('PNG 尺寸无效')
        return '.png', width, height
    # Other formats are retained honestly, but must be visually checked/converted before final/.
    if raw.startswith(b'\xff\xd8\xff'):
        return '.jpg', None, None
    if raw.startswith(b'RIFF') and raw[8:12] == b'WEBP':
        return '.webp', None, None
    raise ValueError('返回文件不是可识别的 PNG/JPEG/WebP')


def normalize_image(source, destination):
    """Decode, flatten transparency onto white, and save a real RGB PNG."""
    from PIL import Image
    with Image.open(source) as image:
        image.load()
        rgba = image.convert('RGBA')
        alpha_min, alpha_max = rgba.getchannel('A').getextrema()
        background = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
        output = Image.alpha_composite(background, rgba).convert('RGB')
        temp = destination.with_suffix('.tmp')
        output.save(temp, format='PNG')
        temp.replace(destination)
        return {'actual_size': list(output.size), 'normalization': 'white_background_rgb_png',
                'source_alpha_extrema': [alpha_min, alpha_max]}


def save_manifest(path, manifest):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--script', type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument('--size', default='768x1024')
    parser.add_argument('--quality', choices=['auto', 'low', 'medium', 'high'])
    parser.add_argument('--run', default='ddcherry', help='独立生成批次名，保留旧版结果')
    parser.add_argument('--card', type=int, help='只生成指定卡片，适合先试一张')
    parser.add_argument('--yes', action='store_true', help='授权实际调用；默认仅预览')
    args = parser.parse_args(argv)
    project = args.project.expanduser().resolve()
    try:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', args.run):
            raise ValueError('批次名仅允许字母、数字、下划线与连字符')
        data = load_project(project)
        match = re.fullmatch(r'([1-9]\d*)x([1-9]\d*)', args.size)
        if not match:
            raise ValueError('size 必须是正整数宽x高')
        width, height = map(int, match.groups())
        rw, rh = map(int, data['aspect_ratio'].split(':'))
        if width * rh != height * rw:
            raise ValueError('请求尺寸与 cards.json 的 aspect_ratio 不一致')
        cards = [c for c in data['cards'] if args.card is None or c['index'] == args.card]
        if not cards:
            raise ValueError('未找到指定卡片')
        jobs = [(c['index'], image_prompt(data, c) + '\n本次只输出这一张独立图片，不要拼图、联系表或额外图片。') for c in cards]
        print(f'提供方：DDCherry；尺寸：{args.size}；选中：{len(jobs)} 张')
        if not args.yes:
            for index, prompt in jobs:
                print(f'卡片 {index:02d}；提示词 {len(prompt)} 字符')
            print('预览完成，未加载服务配置、未调用接口。实际调用添加 --yes。')
            return 0
        try:
            import PIL.Image  # Preflight before any API request.
        except ImportError:
            raise ValueError('直接生图需 Pillow：请在所用Python环境执行 python -m pip install Pillow')
        from project_paths import resolve, organized
        target = resolve(project, 'generated') / args.run
        target.mkdir(parents=True, exist_ok=True)
        manifest_path = (project / '记录/生成记录.json') if organized(project) else target / 'manifest.json'
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'schema_version': 1, 'cards': {}}
        provider = load_provider(args.script.expanduser().resolve())
        for index, prompt in jobs:
            fingerprint = hashlib.sha256(json.dumps([prompt, args.size, args.quality, provider.MODEL], ensure_ascii=False).encode()).hexdigest()
            key = str(index)
            old = manifest['cards'].get(key)
            if old:
                if str(old.get('review', '')).startswith('fail'):
                    raise ValueError(f'卡片 {index} 审核失败，停止整组生成；先查看审核报告')
                if old.get('status') == 'generated' and old.get('fingerprint') == fingerprint and (project / old['path']).is_file():
                    print(f'跳过已有卡片 {index:02d}：{old["path"]}')
                    continue
                raise ValueError(f'卡片 {index} 有旧记录或未完成请求；请先人工核对，避免重复生成或覆盖')
            entry = {'fingerprint': fingerprint, 'status': 'requesting', 'model': provider.MODEL, 'size': args.size, 'review': 'pending'}
            manifest['cards'][key] = entry
            save_manifest(manifest_path, manifest)
            try:
                previous = Path.cwd()
                try:
                    os.chdir(project)
                    output_root = project / '.tmp' if organized(project) else project
                    model, paths = provider.generate(output_root, prompt, args.size, args.quality)
                finally:
                    os.chdir(previous)
                entry['source_paths'] = [str(p) for p in paths]
                if len(paths) != 1:
                    raise ValueError('接口未返回恰好一张图片，原始结果保留待人工核对')
                destination = target / f'{index:02d}.png'
                if destination.exists():
                    raise ValueError('目标图片已存在，停止以避免覆盖')
                normalized = normalize_image(Path(paths[0]), destination)
                actual_w, actual_h = normalized['actual_size']
                entry.update(model=model, path=str(destination.relative_to(project)), **normalized)
                if actual_w and actual_w * rh != actual_h * rw:
                    raise ValueError('实际图片比例不符，图片已保留待检查')
                entry['status'] = 'generated'
                save_manifest(manifest_path, manifest)
                print(f'已生成（待审核）：{destination}；模型：{model}')
            except Exception as exc:
                reason = str(exc) if isinstance(exc, ValueError) or type(exc).__name__ == 'GenerationError' else type(exc).__name__
                entry.update(status='failed', error_type=type(exc).__name__, error=reason)
                save_manifest(manifest_path, manifest)
                print(f'卡片 {index} 失败：{reason}；已停止，不自动重试。', file=sys.stderr)
                return 1
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'准备失败：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
