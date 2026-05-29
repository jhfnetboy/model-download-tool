# 图像/视频模型测试脚本

```bash
source ~/venvs/ml/bin/activate
cd ~/Dev/tools/model-download-tool/tests
```

---

## ✅ 立即可用

### FLUX.2 Klein — 文生图（推荐首选）

```bash
python test_flux2_klein.py
# 输出: ~/Desktop/flux_outputs/flux2_panda_s20_seed42.png
```

模型路径: `~/.omlx/models/FLUX.2-klein-4B-mflux-4bit`（mflux 原生格式）

### FLUX.1 Schnell — 极速文生图（4步，首次自动下载）

```bash
python test_flux_schnell.py
# 首次运行通过 hf-mirror 下载 ~30GB，之后缓存本地
```

### Lance-3B-Video — 文生视频

```bash
pip install git+https://github.com/xocialize/lance-mlx.git
python test_lance_video.py
```

### qwen3-fluxassistant — Prompt 扩写助手（文字模型）

```bash
python test_fluxassistant.py "一只熊猫在竹林里打太极"
# 输出扩写后的 FLUX prompt，再喂给 FLUX.2 Klein 出图
```

---

## ⏳ 需先准备模型（mflux-save）

### FLUX.1 Dev — 最高质量文生图

```bash
# 第一步：下载并量化（走 hf-mirror，下载 ~30GB，保存 ~10GB）
HF_ENDPOINT=https://hf-mirror.com \
  mflux-save --model dev --quantize 4 --path ~/.omlx/models/mflux-dev-4bit

# 第二步：跑测试
python test_flux_dev.py
```

### FLUX.1 Kontext — 图生图编辑

```bash
# 第一步：下载并量化（~34GB 下载，~10GB 保存）
HF_ENDPOINT=https://hf-mirror.com \
  mflux-save --model kontext --quantize 4 --path ~/.omlx/models/mflux-kontext-4bit

# 第二步：跑测试（图片放 ~/Downloads，不要放 Desktop）
python test_flux_kontext.py ~/Downloads/photo.jpg
```

---

## 推荐工作流

```
fluxassistant → 生成精细 prompt
      ↓
flux2_klein   → 快速出图验证构图（20步，约1分钟）
      ↓
flux_dev      → 出最终高质量图（25步，约3分钟）
      ↓
flux_kontext  → 局部修改满意的图
```

## 已删除的废弃模型

| 模型 | 格式 | 原因 |
|------|------|------|
| flux1.dev.4bit.mlx | FluxSwift（私有量化）| mflux Python 不兼容 |
| flux1.kontext.4bit.mlx | FluxSwift（私有量化）| mflux Python 不兼容 |
| mlx-FLUX.1-schnell-4bit-quantized | DiffusionKit | 需要 diffusionkit（与 mflux 冲突）|
