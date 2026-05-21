# mdt — Model Download Tool

AI 模型搜索与下载工具。支持模糊搜索、交互式选择、断点续传，自动选择最优下载器。

**默认适配 Mac M 芯片**，搜索结果自动过滤为 MLX 格式（Apple Silicon 原生加速）。

## 快速开始

```bash
# 激活 ML 虚拟环境（推荐）
source ~/venvs/ml/bin/activate

# 1. 初始化（下载 hfd.sh、检查工具链、生成 config.json）
python3 mdt.py setup

# 2. 搜索模型（默认 Mac MLX 格式）
python3 mdt.py search "llama"
python3 mdt.py search "OCR"

# 3. 直接下载指定模型
python3 mdt.py download mlx-community/Qwen3-8B-4bit-mlx

# 4. 查看已下载模型
python3 mdt.py list

# 5. 查看/修改配置
python3 mdt.py config
```

## 全局命令（可选）

在 `~/.zshrc` 中添加以下内容，让 `mdt` 命令全局可用：

```bash
source ~/venvs/ml/bin/activate
export HF_ENDPOINT=https://hf-mirror.com
alias mdt='python3 /Users/jason/Dev/tools/model-download-tool/mdt.py'
```

然后执行 `source ~/.zshrc`。

## 平台过滤（Mac M 芯片）

通过 `--platform` 指定目标平台，默认为 `mac`：

| 平台 | 过滤格式 | 说明 |
|------|---------|------|
| `mac` | MLX | Apple Silicon 原生加速（**默认**）|
| `mac-gguf` | GGUF | llama.cpp + Metal 加速，适合 LLM |
| `gguf` | GGUF | 跨平台，CPU/GPU 均可运行 |
| `windows` | 无 | Windows (CUDA / CPU) |
| `linux` | 无 | Linux (CUDA / CPU) |
| `all` | 无 | 不过滤，显示全部 |

```bash
python3 mdt.py search "llama"                      # 默认：Mac MLX
python3 mdt.py search "llama" --platform mac-gguf  # GGUF + Metal
python3 mdt.py search "llama" --platform all       # 全平台不过滤
```

## config.json 配置文件

运行 `setup` 后自动生成 `config.json`，所有默认值可在此修改，无需每次传参。

```json
{
  "download_dir": "~/.omlx/models",
  "mirror":       "https://hf-mirror.com",
  "platform":     "mac",
  "source":       "huggingface",
  "limit":        20,
  "threads":      8,
  "jobs":         5,
  "token":        ""
}
```

| 配置项 | 说明 | 可选值 |
|--------|------|--------|
| `download_dir` | 模型保存目录 | 任意路径 |
| `mirror` | HuggingFace 镜像站 | URL |
| `platform` | 默认平台过滤 | mac / mac-gguf / gguf / windows / linux / all |
| `source` | 默认搜索来源 | huggingface / modelscope / all |
| `limit` | 搜索结果条数 | 整数 |
| `threads` | 单文件下载线程数 | 整数（建议 4-8）|
| `jobs` | 并行下载文件数 | 整数（建议 3-5）|
| `token` | HuggingFace Token | hf_xxx（下载受限模型用）|

通过命令行修改单项配置：

```bash
python3 mdt.py config platform all     # 改为全平台搜索
python3 mdt.py config limit 30         # 默认显示 30 条结果
python3 mdt.py config token hf_xxx     # 设置 HF token
```

## 命令参考

### `setup` — 初始化工具链

```bash
python3 mdt.py setup
```

自动完成：下载 `hfd.sh`、安装 `huggingface_hub`、检查 `aria2c`、生成 `config.json`。

### `config` — 查看/修改配置

```bash
python3 mdt.py config                  # 查看所有配置
python3 mdt.py config platform all    # 修改单项
```

### `search` — 搜索并交互式下载

```bash
python3 mdt.py search [关键词] [选项]

选项:
  --platform      平台过滤 (默认来自 config.json)
  --source        来源: huggingface / modelscope / all
  -n N            显示 N 条结果
  --token TOKEN   HuggingFace Access Token
  --dir PATH      下载目录
```

交互操作：输入序号下载，`s <关键词>` 重新搜索，`q` 退出。

### `download` — 直接下载指定模型

```bash
python3 mdt.py download <模型ID> [选项]

选项:
  --source        来源: huggingface / modelscope
  --token TOKEN   HuggingFace Access Token
  -x N            单文件线程数 (默认 8)
  -j N            并行文件数 (默认 5)
  --include PAT   只下载匹配文件 (如 '*.safetensors')
  --exclude PAT   排除匹配文件 (如 '*.bin')
  --dir PATH      下载目录
```

### `list` — 查看已下载模型

```bash
python3 mdt.py list
```

显示 `~/.omlx/models/` 下所有模型及占用空间。

## 下载器优先级

工具自动选择最优下载器，无需手动配置：

1. **hfd.sh + aria2c** — 多线程，速度最快（推荐）
2. **huggingface-cli** — HuggingFace 官方，支持断点续传
3. 首次 `setup` 时自动下载 `hfd.sh` 并安装 `huggingface_hub`

## 受限模型下载

部分模型（如 Llama 系列）需要 HuggingFace 账号授权：

1. 在 [huggingface.co](https://huggingface.co) 登录并申请模型访问权限
2. 在 [设置页](https://huggingface.co/settings/tokens) 创建 Access Token
3. 填入 config.json 的 `token` 字段，或通过 `--token` 参数传入

```bash
python3 mdt.py download meta-llama/Llama-2-7b --token hf_xxx
```

## 镜像站

默认使用 [hf-mirror.com](https://hf-mirror.com)，国内直连无需代理。可在 `config.json` 中修改 `mirror` 字段。

## 依赖

- Python 3.8+（搜索功能仅用标准库，无强制第三方依赖）
- aria2c（推荐）：`brew install aria2`
- 可选：`pip install huggingface_hub`（提供 huggingface-cli）
- 推荐虚拟环境：`python3.12 -m venv ~/venvs/ml`
