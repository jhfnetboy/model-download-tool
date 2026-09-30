#!/bin/bash
# Qwen3.6-35B-A3B 三方对照，分两段跑（同一客户端 h2h.py，引擎轮流独占机器）
#   段1：6bit/OptiQ 下完即跑 —— oMLX 8bit vs 6bit vs OptiQ-4bit → 哪个量化档做常驻
#   段2：续传 GGUF 下完再跑 —— llama-server Q8_0        → Mac 是否改用 llama.cpp
set -u
cd "$(dirname "$0")"; mkdir -p results
GGUF="$HOME/gguf-models/Qwen3.6-35B-A3B-Q8_0.gguf"
M6="$HOME/.omlx/models/Qwen3.6-35B-A3B-MLX-6bit"
M6LOG="${M6LOG:?需要 6bit 下载日志路径}"
MQ="$HOME/.omlx/models/Qwen3.6-35B-A3B-OptiQ-4bit"
MQLOG="${MQLOG:?需要 OptiQ 下载日志路径}"
PY="$HOME/venvs/ml/bin/python"
KEY=$(python3 -c "import json;print(json.load(open('$HOME/.omlx/settings.json'))['auth']['api_key'])")
log(){ echo "[$(date +%H:%M:%S)] $*"; }
fp(){ footprint -p "$1" 2>/dev/null | grep -m1 -oE "Footprint: [0-9.]+ [KMG]B"; }

omlx_phase(){ # $1=label $2=model_id
  log "重启 oMLX（清空已加载模型）→ 测 $2"
  omlx stop >/dev/null 2>&1; sleep 15; omlx start >/dev/null 2>&1; sleep 15
  until curl -s -m 4 -H "Authorization: Bearer $KEY" http://127.0.0.1:8088/v1/models | grep -q "\"$2\""; do sleep 5; done
  OPID=$(pgrep -x omlx-server | head -1); log "oMLX pid=$OPID 空载 $(fp $OPID)"
  ENGINE_PID=$OPID "$PY" h2h.py "$1" http://127.0.0.1:8088 "$2" "$KEY"
}

# ================= 段 1 =================
wait_dl(){ # $1=目录 $2=日志 $3=名字
  log "等待 $3 下载完成…"
  until grep -q "=== 校验 ===" "$2" 2>/dev/null && ! find "$1" -name "*.aria2" | grep -q .; do sleep 60; done
  grep -A40 "=== 校验 ===" "$2" | grep -q "缺失\|不完整" && { log "$3 校验失败，终止"; exit 1; }
  log "$3 就绪 ($(du -sh "$1" | cut -f1))"
}
wait_dl "$M6" "$M6LOG" "6bit"
wait_dl "$MQ" "$MQLOG" "OptiQ-4bit"
pkill -f "mlx_vlm server" 2>/dev/null
omlx_phase omlx-mlx8bit Qwen3.6-35B-A3B-MLX-8bit
omlx_phase omlx-mlx6bit Qwen3.6-35B-A3B-MLX-6bit
omlx_phase omlx-optiq4bit Qwen3.6-35B-A3B-OptiQ-4bit
log "段 1 完成"; "$PY" compare.py

# ================= 段 2 =================
log "续传 GGUF…"
[ -f "$GGUF.aria2" ] && ./resume_gguf.sh > results/gguf_resume.log 2>&1
[ ! -f "$GGUF.aria2" ] && [ "$(stat -f %z "$GGUF")" = "36903139328" ] || { log "GGUF 未完整，终止"; exit 1; }
log "GGUF 就绪"
omlx stop >/dev/null 2>&1; sleep 15
OPID=$(pgrep -x omlx-server | head -1); [ -n "$OPID" ] && log "oMLX 停止后残留占用 $(fp $OPID)"
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
log "恢复 oMLX"; omlx start >/dev/null 2>&1
"$PY" compare.py
