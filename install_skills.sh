#!/usr/bin/env bash
# 安装 model-download-tool 的 Claude Code skills 到全局 ~/.claude/skills/
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_SRC="$SCRIPT_DIR/skills"
SKILLS_DST="$HOME/.claude/skills"

if [ ! -d "$SKILLS_SRC" ]; then
    echo "没有找到 skills 目录: $SKILLS_SRC"
    exit 1
fi

mkdir -p "$SKILLS_DST"

for skill_dir in "$SKILLS_SRC"/*/; do
    skill_name="$(basename "$skill_dir")"
    dst="$SKILLS_DST/$skill_name"

    if [ -d "$dst" ]; then
        echo "⟳ 更新: $skill_name"
    else
        echo "✓ 安装: $skill_name"
    fi

    cp -r "$skill_dir" "$SKILLS_DST/"
done

echo ""
echo "已安装 skills："
for skill_dir in "$SKILLS_SRC"/*/; do
    echo "  /$(basename "$skill_dir")"
done
echo ""
echo "在 Claude Code 中使用: /flux-gen <你的 prompt>"
