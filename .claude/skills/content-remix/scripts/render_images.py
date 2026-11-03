#!/usr/bin/env python3
"""Legacy per-card OpenAI renderer is intentionally disabled."""
import sys

if __name__ == '__main__':
    print('逐张生图入口已停用。请使用整组创作提示词，或render_ddcherry.py进行单次整组请求。', file=sys.stderr)
    raise SystemExit(2)
