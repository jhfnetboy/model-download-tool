# Mage-VL 本地实验（2026-08）

用 mdt 下 microsoft/Mage-VL 之后，在本仓库里跑通的一个视觉理解实验。
**代码在 `vendor/mage-vl-local-mac/`，该目录已 gitignore，不随本仓库提交。**

## 是什么

Mage-VL 是微软的视觉语言模型，能读图片和视频，还能做「主动流式解说」——
按片段边看边输出，而不是等整段处理完。

跑的是社区包装 [`karlazx/mage-vl-local-mac`](https://github.com/karlazx/mage-vl-local-mac)
（不是官方 `microsoft/Mage`），它把研究代码包成了 React UI + FastAPI + SSE，走 Apple MPS。

- 权重：`~/.omlx/models/Mage-VL`（约 10GB，78 个文件）
- 服务：后端 `127.0.0.1:8000`，UI `127.0.0.1:3000`
- 实测（M1 Max 64GB）：图片 4–13 秒，30 秒视频约 45s 预处理 + 100s 生成

## 复现

```bash
git clone https://github.com/karlazx/mage-vl-local-mac.git vendor/mage-vl-local-mac
cd vendor/mage-vl-local-mac

# 权重不要走 mdt 的镜像，原因见下
~/venvs/ml/bin/hf download microsoft/Mage-VL --local-dir ~/.omlx/models/Mage-VL

# .env.local 指向已下好的权重，避免在 vendor 里再占一份 10GB
cat > .env.local <<'EOF'
MAGE_MODEL_ID=microsoft/Mage-VL
MAGE_MODEL_DIR=/Users/jason/.omlx/models/Mage-VL
MAGE_RUNTIME_DIR=runtime
HF_HOME=.cache/huggingface
PYTORCH_ENABLE_MPS_FALLBACK=1
DCVC_FORCE_PYTORCH=1
EOF

/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci && npm run build
./start.command
```

没有跑上游的 `setup.command`——它会用 brew 装 node@22，而本机 nvm 已有 22.x。
其余步骤和它等价。

## 三个踩过的坑

**1. hf-mirror 下不了这个模型。** 镜像会 302 到 HF 的 xet CDN 签名 URL，签名里绑死了
byte-range，aria2 的多连接分片全部 403。也就是 **mdt / hfd.sh 走镜像这条路对 xet 存储的
仓库整体失效**。解法是用 `hf download`（huggingface_hub 自带 xet 客户端）直连
huggingface.co。以后看到 403 且 URL 里带 `xet-bridge`，直接换路子，别调镜像参数。

**2. UI 要用 `127.0.0.1:3000`，不能用 `localhost:3000`。** 本机 `~/Dev/aastar/YetAnotherAA`
的 NestJS 服务绑在 `*:3000` 的 IPv6 通配地址上，而 Mage-VL 前端只绑 IPv4。浏览器把
`localhost` 优先解析成 `::1`，就打到 aastar 去了，返回 `{"message":"Cannot GET /"}`。

**3. 图片精细度的 API 取值是 `quick|balanced|high`**，不是各处文章写的 `original`。

## 能力边界

模型 config 里只有 `vision_config` + qwen3 文本塔，**没有音频塔**——
视频里的语音转文字它做不了，问它「这段视频说了什么」它是在看画面猜。
要转录得另配 ASR（mlx-whisper / whisper.cpp / ququ 里的 FunASR）。

## 已封装成 skill

日常用不需要碰这个目录。能力已经包成 blog 仓库的 project skill：

- 源：`~/Dev/mycelium/blog/.agents/skills/mage-vl/`
- 客户端：`scripts/mage.py`，纯标准库，`status/up/down/image/video/stream/batch`
- 只在 blog 仓库生效，其他仓库不加载

选 skill 没选 MCP，是因为服务本身已经是 HTTP API，套 MCP 等于在 server 外面再包一个
server；而且 MCP 的 tool schema 每个 session 开局就常驻上下文，skill 只在触发时才读正文。
