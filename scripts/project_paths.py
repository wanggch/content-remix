"""Canonical project paths. No legacy layout detection or migration."""
from pathlib import Path

CARDS = Path('创作资料/cards.json')
BATCH = Path('创作提示词.md')
CONTRACT = Path('创作资料/创作约束.md')
SOURCE = Path('对标素材')
IMAGES = Path('图片')
TEMP = Path('.tmp/generated')
MANIFEST = Path('记录/生成记录.json')


def resolve(root, relative):
    return Path(root) / relative
