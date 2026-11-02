#!/usr/bin/env bash
set -euo pipefail

# 源文件相对脚本定位；安装目标相对调用目录定位，避免写入全局 Skill 目录。
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(pwd)"
MODE="${1:-all}"
FORCE="${2:-}"

if [[ "$MODE" != "all" && "$MODE" != "claude" && "$MODE" != "codex" ]]; then
  echo "Usage: bash install.sh [all|claude|codex] [--force]" >&2
  exit 2
fi

install_one() {
  local name="$1" destination="$2"
  mkdir -p "$(dirname "$destination")"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ "$FORCE" != "--force" ]]; then
      echo "Skip $name: $destination already exists (add --force to replace)"
      return
    fi
    # --force 会替换整个安装副本，其中的本地修改和 .venv 也会被删除。
    rm -rf "$destination"
  fi
  # 仅复制运行所需文件，不将测试和开发辅助目录带入目标项目。
  mkdir -p "$destination/scripts" "$destination/references"
  cp "$SOURCE/SKILL.md" "$SOURCE/README.md" "$destination/"
  cp "$SOURCE"/scripts/*.py "$destination/scripts/"
  cp "$SOURCE"/references/*.md "$destination/references/"
  echo "Installed $name: $destination"
}

if [[ "$MODE" == "all" || "$MODE" == "claude" ]]; then
  install_one "Claude Code" "$PROJECT_DIR/.claude/skills/content-remix"
fi
if [[ "$MODE" == "all" || "$MODE" == "codex" ]]; then
  install_one "Codex" "$PROJECT_DIR/.agents/skills/content-remix"
fi

echo "Done. Start a new Claude Code / Codex session and invoke the skill."
