"""Resolve organized article paths while retaining legacy project compatibility."""
from pathlib import Path

MAPPING = {
    'cards.json': '创作资料/cards.json',
    '01-analysis.md': '创作资料/对标分析.md',
    '02-topics.md': '创作资料/选题与分镜.md',
    '03-storyboard.md': '创作资料/选题与分镜.md',
    '02-创作约束.md': '创作资料/创作约束.md',
    '04-publish.md': '发布文案.md',
    '05-review.md': '记录/审核.md',
    '06-performance.md': '记录/发布数据.md',
    'prompts/创作提示词.md': '创作提示词.md',
    '00-source': '对标素材',
    'final': '图片',
    'generated': '.tmp/generated',
}


def organized(root):
    return (Path(root) / '创作资料').is_dir()


def resolve(root, relative):
    root = Path(root)
    text = str(relative)
    if organized(root):
        for old, new in MAPPING.items():
            if text == old or text.startswith(old + '/'):
                return root / (new + text[len(old):])
    return root / relative
