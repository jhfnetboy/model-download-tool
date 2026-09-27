# xet 仓库下载 + mlx-vlm 踩坑记（2026-08-20/21）

> **模型已删除（2026-08-21）**：Qwen3.8-27B-Uncensored 6-bit 在 M1 Max 上只有 12.4 tok/s，
> 对日常交互太慢，已删。本文保留是因为**下载方案和 mlx-vlm 的坑对后续所有模型都适用**。
> 通用下载器：`scripts/download-xet-aria2.sh <repo_id> <目标目录> [子目录]`。

## 原始实验：Qwen3.8-27B-Uncensored-MLX

跑通了 `orcarouter/Qwen3.8-27B-Uncensored-MLX` 6-bit。
出处：https://blog.mushroom.cv/blog/qwen3-8-27b-uncensored-mlx-abliterated-gated-deltanet-vision/

## 是什么

Qwen3.8-27B 的 abliterated（消融去审查）MLX 量化版。abliteration 是在权重空间里
定位并正交消去「拒绝方向」向量，不是重新微调。

`config.json` 实测：
- `model_type: qwen3_5`，`Qwen3_5ForConditionalGeneration`
- 64 层混合注意力：48 层 Gated DeltaNet 线性注意力 + 每 4 层一个全注意力（共 16 个）
- 原生视觉塔（index.json 里 333 个 vision 张量），vision/norm/conv1d 保持 BF16
- 262144 上下文

各量化实际大小（HF API 查的真实值，比博客表格略大）：
8-bit 29.53 GB / **6-bit 22.80 GB** / 4-bit 16.08 GB / 2-bit 9.36 GB。仓库根目录是 4-bit 的副本。

## 怎么跑

```bash
# 通用起法（脚本已随模型一起删除）
~/venvs/ml/bin/python -m mlx_vlm server --model <模型目录> --port 8090 --host 127.0.0.1
```

权重在 `~/.omlx/models/Qwen3.8-27B-Uncensored-MLX/6-bit`，用全局 venv `~/venvs/ml`
（2026-08-21 已升到 mlx 0.32.1 + mlx-vlm 0.6.15 + jinja2）。

M1 Max 64GB 实测：模型加载 10 秒，**稳定 12.4 tok/s**（首次请求含预热只有 4.4 tok/s），
带图请求 11 秒出结果，视觉识别准确（能读出图里的随机串 `MDT-TEST-7391`）。
服务空载时系统内存仍有 78% 空闲。

## 五个坑

**1. oMLX 跑不了它，升级 `~/venvs/ml` 也救不了 oMLX。** oMLX 0.4.3 的 app bundle 里冻的是
`mlx-0.31.2` + `mlx_vlm-0.6.2`，位置在
`/Applications/oMLX.app/Contents/Resources/Python/framework-mlx-base/lib/python3.11/site-packages/`。
它只读自己 bundle 里的这份，跟系统上装了什么无关。改签名过的 .app 内部依赖既脆弱又会被更新冲掉，不要试。
要用这个模型只能走 mlx-vlm。

2026-08-21 把 `~/venvs/ml` 升到了 mlx 0.32.1 + mlx-vlm 0.6.15。pip 会报
`mflux 0.17.5 requires mlx<0.32.0` 的冲突警告，**实测是保守 pin，mflux 照常出图**
（4 步 512×512 用时 11 秒），flux-gen skill 不受影响。transformers 一并从 5.9.0 升到 5.15.1。

**2. `hf download` 自带的 xet 客户端在国内网络会直接卡死。**
进程活着、有 .incomplete 文件、但两分钟零字节零网络流量。
加 `HF_XET_HIGH_PERFORMANCE=1` + 48 并发也一样。

**3. 但 aria2 直连 xet 是可以的 —— 修正 `mage-vl-experiment.md` 里的说法。**
那篇记的「xet 仓库 aria2 必 403」只对**走 hf-mirror 的 302** 成立。
直连 huggingface.co 带 token 拿到的签名 URL **接受 range 请求**（返回 206），
aria2 `-x16` 实测 5.6–6.9 MB/s，比 hf 的 xet 客户端快一个数量级。
做法见 `scripts/download-xet-aria2.sh`：curl 拿 302 的 `redirect_url` → 喂给 aria2（不带
Authorization 头，签名已在 URL 里）→ 每次重试重新取签名（签名会过期）。
hf-mirror 对这个仓库实测只有 85 KB/s，本来也没法用。

**4. 别开 KV cache 量化。** 这架构不支持（mlx-engine#286），`--kv-bits` 不要加。

**5. mlx-vlm 没把 jinja2 声明成依赖。** 不装的话 `/v1/chat/completions` 直接 500，
报 `apply_chat_template requires jinja2`。服务能起、`/v1/models` 也正常，坑在这。

## 和博客不符的一处

博客说模型带 MTP head（可做投机解码加速）。实际查 `model.safetensors.index.json` 的
2180 个张量，**MTP 相关的一个都没有** —— 这个 MLX 量化版把 MTP 头丢了。
所以 `mlx_vlm server --draft-kind mtp` 这条加速路走不通。

## 顺带

写下载脚本时踩过：后台跑的是 macOS 自带 **bash 3.2**，不支持关联数组（`declare -A`），
会报 `unbound variable` 然后空转。`scripts/download-xet-aria2.sh` 已改成兼容写法。

## 选哪个量化 / 什么时候该用它（2026-08-21 实测）

| 模型 | 类型 | 显存峰值 | 速度 |
|---|---|---|---|
| Qwen3.8-27B-Uncensored **6-bit** | dense 27B | ~23 GB | **11.8–12.4 tok/s** |
| Qwen3.6-35B-A3B-MLX-8bit | **MoE**(3B 激活) | 37.0 GB | **54.7 tok/s** |

同一个 prompt（拆解季度目标为周里程碑，400 tok）实测，MoE 快 **4.6 倍**。

**6-bit 是这个模型的甜点，不要上 8-bit。** M1 Max 带宽 400 GB/s，6-bit 实测有效带宽
约 283 GB/s（≈71% 峰值）。按同样效率推算 8-bit（29.5 GB）约 **9.6 tok/s**，
多吃 6.7 GB 内存换约 23% 的速度损失，而 6-bit→8-bit 的质量差异本就极小。

**但日常助理类用途（工作计划、目标跟踪、建议）应该用 Qwen3.6-35B-A3B，不是这个。**
理由：快 4.6 倍；abliteration 消的是拒绝行为，对做计划毫无价值，反而可能轻微伤到指令遵循。
Qwen3.8 的不可替代之处是**视觉 + 无审查**，只在需要这两样时才拿出来用。

注：mlx_lm 直接跑 Qwen3.6-35B-A3B 时 thinking 过程会混进输出，接入助理前要处理下 thinking 标签。
