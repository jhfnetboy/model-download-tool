#!/bin/bash
# 个人助理的模型切换器
#
# oMLX 把 ~/.omlx/models 下所有模型同时暴露为 API model ID，
# 切换不需要重启、不额外占内存 —— 只是换请求里的 model 字段。
# 本脚本把「当前档位」写进 ~/.omlx/assistant-model，供 harness 读取。
#
# 用法:
#   ./scripts/assistant-model.sh                # 看当前档位
#   ./scripts/assistant-model.sh moe            # 切到主力(默认)
#   ./scripts/assistant-model.sh dense          # 切到 dense 3.8 OptiQ
#   ./scripts/assistant-model.sh dense36        # 切到 dense 3.6
#   ./scripts/assistant-model.sh list           # 列出 oMLX 暴露的全部模型
#   ./scripts/assistant-model.sh test <档位>     # 实发一个请求验证
set -u
STATE="$HOME/.omlx/assistant-model"
PORT=8088
KEY=$(python3 -c "import json;print(json.load(open('$HOME/.omlx/settings.json'))['auth']['api_key'])" 2>/dev/null)

id_for(){ case "$1" in
  moe)      echo "Qwen3.6-35B-A3B-MLX-8bit" ;;   # MoE 3B激活 40GB — 默认主力
  dense)    echo "Qwen3.8-27B-OptiQ-4bit"    ;;   # dense 3.8 混合精度 19GB — 硬任务
  dense36)  echo "Qwen3.6-27B-MLX-6bit"      ;;   # dense 3.6 21GB — 同代对照
  ocr)      echo "GLM-OCR-bf16"              ;;   # 表格/票据 2.1GB
  *)        echo "" ;;
esac; }

case "${1:-show}" in
  show)
    CUR=$(cat "$STATE" 2>/dev/null || echo "(未设置，默认 moe)")
    echo "当前档位: $CUR"
    echo "可选: moe(默认主力) / dense(3.8 OptiQ 硬任务) / dense36(3.6 对照) / ocr"
    ;;
  list)
    curl -s --max-time 15 -H "Authorization: Bearer $KEY" "http://127.0.0.1:$PORT/v1/models" \
      | python3 -c "import json,sys;[print(' ',m['id']) for m in json.load(sys.stdin).get('data',[])]"
    ;;
  test)
    ID=$(id_for "${2:-moe}"); [ -z "$ID" ] && { echo "未知档位: ${2:-}"; exit 1; }
    echo "测试 $ID ..."
    S=$(date +%s)
    curl -s --max-time 300 "http://127.0.0.1:$PORT/v1/chat/completions" \
      -H "Content-Type: application/json" -H "Authorization: Bearer $KEY" \
      -d "{\"model\":\"$ID\",\"messages\":[{\"role\":\"user\",\"content\":\"用一句话自我介绍\"}],\"max_tokens\":60,\"temperature\":0.2,\"chat_template_kwargs\":{\"enable_thinking\":false}}" \
      | python3 -c "
import json,sys
d=json.load(sys.stdin)
if 'choices' in d:
    u=d.get('usage',{})
    print(' 回答:', d['choices'][0]['message']['content'][:120])
    print(f\" 用量: {u.get('completion_tokens',0)} tok，耗时 $(( $(date +%s)-S )) 秒\")
else: print(' 错误:', str(d)[:200])"
    ;;
  moe|dense|dense36|ocr)
    ID=$(id_for "$1"); echo "$1" > "$STATE"
    echo "已切到 $1 → model ID: $ID"
    echo "（oMLX 同时暴露所有模型，切换不重启、不额外占内存）"
    ;;
  *) echo "用法: $0 [show|list|moe|dense|dense36|ocr|test <档位>]"; exit 1 ;;
esac
