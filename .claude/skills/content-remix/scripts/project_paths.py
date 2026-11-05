"""Canonical project paths. No legacy layout detection or migration."""
import json
from pathlib import Path

CARDS = Path('创作资料/cards.json')
BATCH = Path('创作提示词.md')
CONTRACT = Path('创作资料/创作约束.md')
SOURCE = Path('对标素材')
IMAGES = Path('图片')
TEMP = Path('.tmp/generated')
MANIFEST = Path('记录/生成记录.json')


def source_root(root):
    """An article may reference shared material instead of owning a copy."""
    root = Path(root).resolve()
    reference = root / '创作资料/对标引用.json'
    if not reference.exists():
        return root / SOURCE
    data = json.loads(reference.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('对标引用格式非法')
    value = data.get('reference_path')
    if not isinstance(value, str) or not value.strip() or Path(value).is_absolute():
        raise ValueError('reference_path必须为相对文章目录的路径')
    target = (root / value).resolve()
    if not (target / '对标分析.md').is_file():
        raise ValueError('引用的对标分析不存在')
    return target / SOURCE


def resolve(root, relative):
    return Path(root) / relative
