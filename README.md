# mdt — Model Download Tool

AI 模型搜索与下载工具。支持模糊搜索、交互式选择、断点续传，自动选择最优下载器。

## 快速开始

```bash
# 1. 初始化 (下载 hfd.sh，检查工具链)
python3 mdt.py setup

# 2. 模糊搜索模型，交互式选择并下载
python3 mdt.py search "OCR"
python3 mdt.py search "image generation"
python3 mdt.py search "llama 7b" --source all   # 同时搜索 HF + ModelScope

# 3. 直接下载指定模型
python3 mdt.py download Qwen/Qwen2-7B-Instruct

# 4. 查看已下载模型
python3 mdt.py list
```

## 全局命令（可选）

在 `~/.zshrc` 中添加：

```bash
export HF_ENDPOINT=https://hf-mirror.com
alias mdt='python3 /Users/jason/Dev/tools/model-download-tool/mdt.py'
```

## 命令参数

### `search`
```
mdt search [关键词] [选项]

选项:
  -n N            显示 N 条结果 (默认 20)
  --source        来源: huggingface / modelscope / all
  --token TOKEN   HuggingFace Access Token (下载受限模型时使用)
  --dir PATH      下载目录 (默认 ~/.omlx/models)
```

### `download`
```
mdt download <模型ID> [选项]

选项:
  --source        来源: huggingface / modelscope
  --token TOKEN   HuggingFace Access Token
  -x N            单文件线程数 (默认 8)
  -j N            并行文件数 (默认 5)
  --include PATTERN  只下载匹配文件 (如 '*.safetensors')
  --exclude PATTERN  排除匹配文件 (如 '*.bin')
  --dir PATH      下载目录
```

## 下载器优先级

1. **hfd.sh** — 基于 aria2c 的多线程专用脚本，推荐，速度最快
2. **huggingface-cli** — HuggingFace 官方工具，支持断点续传
3. 自动安装：首次运行 `setup` 时自动下载 hfd.sh 并安装 huggingface_hub

## 镜像站

默认使用 [hf-mirror.com](https://hf-mirror.com)，可通过环境变量覆盖：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

## 默认下载目录

`~/.omlx/models/`

## 依赖

- Python 3.8+（仅使用标准库，无强制第三方依赖）
- aria2c（推荐）：`brew install aria2`
- 可选：`pip install huggingface_hub`
