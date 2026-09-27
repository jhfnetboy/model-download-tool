#!/bin/bash
# 35B 同模型双引擎对照：oMLX (MLX 8bit) vs llama-server (GGUF Q8_0)
# 两个引擎轮流独占机器，不同时加载（各 37 GB，一起加载会超出 Metal 上限）
set -u
cd "$(dirname "$0")"; mkdir -p results
GGUF="$HOME/gguf-models/Qwen3.6-35B-A3B-Q8_0.gguf"
PY="$HOME/venvs/ml/bin/python"
KEY=$(python3 -c "import json;print(json.load(open('$HOME/.omlx/settings.json'))['auth']['api_key'])")
log(){ echo "[$(date +%H:%M:%S)] $*"; }
used(){ vm_stat | awk -F: '/Pages active|Pages wired down|Pages occupied by compressor/{gsub(/[ .]/,"",$2); s+=$2} END{printf "%.2f", s*16384/1e9}'; }

log "等待 GGUF 下载完成…"
while [ -f "$GGUF.aria2" ]; do sleep 60; done
[ "$(stat -f %z "$GGUF")" = "36903139328" ] || { log "GGUF 大小不对，终止"; exit 1; }
log "GGUF 就绪 ($(du -h "$GGUF" | cut -f1))"

# ---------- A: oMLX ----------
log "A. 重启 oMLX，确保只加载一个模型"
pkill -f "mlx_vlm server" 2>/dev/null
omlx stop >/dev/null 2>&1; sleep 15
PRE_A=$(used); log "引擎启动前整机占用 ${PRE_A} GB"
omlx start >/dev/null 2>&1; sleep 15
until curl -s -m 4 -H "Authorization: Bearer $KEY" http://127.0.0.1:8088/v1/models >/dev/null; do sleep 3; done
OPID=$(pgrep -x omlx-server | head -1); log "oMLX pid=$OPID"
ENGINE_PID=$OPID "$PY" h2h.py omlx-mlx8bit http://127.0.0.1:8088 Qwen3.6-35B-A3B-MLX-8bit "$KEY"

# ---------- B: llama-server ----------
log "B. 停 oMLX，启动 llama-server"
omlx stop >/dev/null 2>&1; sleep 15
PRE_B=$(used); log "引擎启动前整机占用 ${PRE_B} GB"
llama-server -m "$GGUF" -ngl 99 -c 65536 -np 8 --jinja \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --host 127.0.0.1 --port 8094 > results/llama-server.log 2>&1 &
LPID=$!
until curl -s -m 4 http://127.0.0.1:8094/health | grep -q ok; do
  kill -0 $LPID 2>/dev/null || { log "llama-server 启动失败"; tail -20 results/llama-server.log; omlx start; exit 1; }
  sleep 5
done
ENGINE_PID=$LPID "$PY" h2h.py llamacpp-q8_0 http://127.0.0.1:8094 qwen
kill $LPID; sleep 5

# ---------- 收尾 ----------
log "恢复 oMLX"
omlx start >/dev/null 2>&1
"$PY" compare.py
