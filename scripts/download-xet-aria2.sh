#!/bin/bash
# 通用 xet 仓库下载器 —— 直连 HF 拿签名 URL + aria2 多连接
#
# 为什么需要它：HF 的 xet 存储仓库(重定向带 xet-bridge)在国内网络下,
#   - `hf download` 自带的 xet 客户端会卡死(进程活着、零字节、零流量)
#   - hf-mirror 对 xet 仓库实测只有 85 KB/s
#   - 直连拿签名 URL 后 aria2 -x16 可达 5-7 MB/s(签名 URL 接受 range 请求)
# 详见 docs/qwen38-uncensored-mlx.md
#
# 用法:
#   ./scripts/download-xet-aria2.sh <repo_id> <目标目录> [子目录前缀]
# 例:
#   ./scripts/download-xet-aria2.sh mlx-community/dots.ocr-4bit ~/.omlx/models/dots.ocr-4bit
#   ./scripts/download-xet-aria2.sh orcarouter/Qwen3.8-27B-Uncensored-MLX ~/.omlx/models/Q38 6-bit
#
# 不用关联数组，兼容 macOS 自带 bash 3.2
set -u
REPO="${1:?用法: $0 <repo_id> <目标目录> [子目录前缀]}"
DEST="${2:?用法: $0 <repo_id> <目标目录> [子目录前缀]}"
PREFIX="${3:-}"
CFG="$HOME/Dev/tools/model-download-tool/config.json"
# 必须用 venv 的 python —— 系统 python3 没有 huggingface_hub
PY="${PYTHON:-$HOME/venvs/ml/bin/python}"
[ -x "$PY" ] || { echo "找不到 venv python: $PY（可用 PYTHON=... 覆盖）"; exit 1; }
TOKEN=$("$PY" -c "import json;print(json.load(open('$CFG')).get('token',''))" 2>/dev/null)
mkdir -p "$DEST"

# 从 HF API 取文件清单和准确字节数(用于校验)
LIST=$(HF_ENDPOINT=https://huggingface.co HF_TOKEN="$TOKEN" "$PY" - "$REPO" "$PREFIX" <<'PYEOF'
import sys
from huggingface_hub import HfApi
repo, prefix = sys.argv[1], sys.argv[2]
info = HfApi().model_info(repo, files_metadata=True)
for f in info.siblings:
    if prefix and not f.rfilename.startswith(prefix + "/"): continue
    if f.rfilename.endswith(".gitattributes"): continue
    print(f"{f.rfilename}\t{f.size or 0}")
PYEOF
)
[ -z "$LIST" ] && { echo "取不到文件清单，检查 repo_id / 网络 / token"; exit 1; }
echo "$LIST" | wc -l | xargs echo "待处理文件数:"

BAD=0
echo "$LIST" | while IFS=$'\t' read -r RPATH WANT; do
  [ -z "$RPATH" ] && continue
  OUT="$DEST/${PREFIX:+${RPATH#$PREFIX/}}"; [ -z "$PREFIX" ] && OUT="$DEST/$RPATH"
  mkdir -p "$(dirname "$OUT")"
  if [ -f "$OUT" ] && [ "$(stat -f %z "$OUT")" = "$WANT" ]; then echo "[跳过] $RPATH"; continue; fi
  echo "=== $RPATH ($(( WANT/1024/1024 )) MB) ==="
  for attempt in 1 2 3 4 5; do
    SIGNED=$(curl -s -o /dev/null -w "%{redirect_url}" -H "Authorization: Bearer $TOKEN" \
      "https://huggingface.co/$REPO/resolve/main/$RPATH")
    [ -z "$SIGNED" ] && SIGNED="https://huggingface.co/$REPO/resolve/main/$RPATH"
    aria2c -x16 -s16 -k10M -c --console-log-level=warn --summary-interval=60 \
           --retry-wait=5 --max-tries=3 -d "$(dirname "$OUT")" -o "$(basename "$OUT")" "$SIGNED" && break
    echo "  第 $attempt 次失败，重新取签名后重试"; sleep 5
  done
  HAVE=$(stat -f %z "$OUT" 2>/dev/null || echo 0)
  [ "$HAVE" = "$WANT" ] && echo "[OK] $RPATH" || echo "[!!失败] $RPATH  $HAVE != $WANT"
done

echo "=== 校验 ==="
echo "$LIST" | while IFS=$'\t' read -r RPATH WANT; do
  [ -z "$RPATH" ] && continue
  OUT="$DEST/${PREFIX:+${RPATH#$PREFIX/}}"; [ -z "$PREFIX" ] && OUT="$DEST/$RPATH"
  HAVE=$(stat -f %z "$OUT" 2>/dev/null || echo 0)
  [ "$HAVE" != "$WANT" ] && echo "缺失/不完整: $RPATH ($HAVE != $WANT)"
done
du -sh "$DEST"
