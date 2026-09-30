#!/bin/bash
# 用新的签名 URL 续传 GGUF（签名会过期，所以每次重新取）
cd ~/Dev/tools/model-download-tool
TOKEN=$(python3 -c "import json;print(json.load(open('config.json'))['token'])")
S=$(curl -s -o /dev/null -w "%{redirect_url}" -H "Authorization: Bearer $TOKEN" \
  "https://huggingface.co/ggml-org/Qwen3.6-35B-A3B-GGUF/resolve/main/Qwen3.6-35B-A3B-Q8_0.gguf")
aria2c -x16 -s16 -k10M -c --console-log-level=warn --summary-interval=60 \
  -d ~/gguf-models -o Qwen3.6-35B-A3B-Q8_0.gguf "$S"
