#!/usr/bin/env bash
# 一键初始化模型下载工具
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 初始化模型下载工具 ==="

# Python check
python3 --version || { echo "需要 Python 3"; exit 1; }

# Run Python setup
python3 mdt.py setup

# Suggest alias
SHELL_RC="$HOME/.zshrc"
[[ "$SHELL" == *bash* ]] && SHELL_RC="$HOME/.bashrc"

echo ""
echo "─── 可选：添加全局别名 ───"
echo "在 $SHELL_RC 中添加以下两行，让 'mdt' 命令全局可用："
echo ""
echo "  export HF_ENDPOINT=https://hf-mirror.com"
echo "  alias mdt='python3 $SCRIPT_DIR/mdt.py'"
echo ""
echo "然后执行: source $SHELL_RC"
echo ""
echo "使用方法："
echo "  mdt setup              # 初始化"
echo "  mdt search 'OCR'       # 搜索模型"
echo "  mdt list               # 查看已下载"
