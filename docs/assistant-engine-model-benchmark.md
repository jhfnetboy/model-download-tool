# 个人助理引擎与模型选型评测（2026-09-27）

机器：MacBook Pro，Apple M1 Max，64 GB 统一内存。全部数据本机实测。

> **结论先行**
> - **引擎：继续用 oMLX**（8088），长上下文场景用 `mlx_vlm server` 兜底。**不要切 vllm-metal**。
> - **模型：MoE `Qwen3.6-35B-A3B-8bit` 当默认主力**，`Qwen3.8-27B-OptiQ-4bit` 当硬任务备胎。
> - **必须全局关闭 thinking** —— 这比选哪个模型影响更大。
> - **MTP 投机解码在本机无效**，别浪费时间。

---

## 一、三个被推翻的前提

做这轮评测之前，有三条我们一直当成事实的结论，实测后全部不成立。

### 1.1 「oMLX 冻在 mlx 0.31.2，跑不了新架构」—— 已过期

本机 oMLX 已经是 **0.6.4**（不是记忆里的 0.4.3），内置：

```
mlx-0.32.0   mlx_metal-0.32.0   mlx_lm-0.31.3   mlx_vlm-0.6.3
```

`mlx_vlm/models/` 下 `qwen3_5`、`qwen3_5_moe`、`glm4v`、`glm4v_moe` 都在。**版本天花板问题不存在了。**

上游也没停止开发：仓库 [jundot/omlx](https://github.com/jundot/omlx) 最后提交 2026-09-27（当天），22.3k star，最新稳定版 v0.6.4，已有 v0.7.0rc1。单人维护、1508 个 open issue，属于活跃但年轻的项目（2026-02 开源）。

### 1.2 「SiliconBench 说 mlx_lm 系并发会吞请求」—— 在 mlx_vlm 上没复现

[SiliconBench](https://arxiv.org/pdf/2609.19169) 主表把 `mlx_lm` 标为「c=16 崩溃」，附录 F.2 里 dense 27B 上 100 个请求只完成 23–31 个。

本机实测 `mlx_vlm server` 0.6.15 + MoE：

| 场景 | 完成率 | 聚合吞吐 |
|---|---|---|
| 短 prompt 并发 8 | **8/8** | 77.1 tok/s |
| 短 prompt 并发 16 | **16/16** | 96.6 tok/s |
| 长 prompt(5769 tok) 并发 8 | **8/8** | 28.5 tok/s（墙钟 84.3s） |

零失败。原因：论文测的是 `mlx_lm`（Table 1 里标为 padded batch），而 `mlx_vlm` 0.6.15 启动日志明确写 `continuous batching enabled`，是不同实现。**论文的警告不能直接套到 mlx_vlm 上。**

### 1.3 「MTP 投机解码能把 dense 的速度补回来」—— 完全错误

见第三节。

---

## 二、引擎对比（同模型 Qwen3.6-35B-A3B-8bit）

| 场景 | oMLX 0.6.4 | mlx_vlm 0.6.15 | 胜者 |
|---|---|---|---|
| 单流（预热后） | 40.6 tok/s | ~54 tok/s（`mlx_lm generate`） | mlx_vlm |
| 短 prompt 并发 8 | **87.8 tok/s** | 77.1 tok/s | oMLX |
| 短 prompt 并发 16 | 95.0 tok/s | **96.6 tok/s** | 平 |
| 长 prompt(5.8K) 并发 8 | 13.9 tok/s（172.5s） | **28.5 tok/s（84.3s）** | **mlx_vlm 快 2 倍** |
| 完成率（全部场景） | 100% | 100% | 平 |

**oMLX 长 prompt 弱的原因不是 chunked_prefill。** 试过把 `scheduler.chunked_prefill` 从 false 改成 true：长 prompt 并发 8 变成 187.6s（比原来 172.5s 还略差），短 prompt 91.3 tok/s（+4%，在噪声内）。已恢复原设置。真实原因应该是 SiliconBench Table 1 记的 oMLX 设计：**prompt batching = "One prompt"**，prefill 一次只处理一个请求。

### 为什么不切 vllm-metal

SiliconBench 里 `vllm-metal` 并发扩展性最好（c=16 时 456 tok/s，是单流的 4.5 倍），三项审计门槛也全过。但有一条否决性理由：

> **MoE 是 vllm-metal 最不成熟的部分** —— 社区报告称 MLX 后端上的 **MoE 专家路由正确性仍是开放问题**，GGUF 格式的 MoE 模型直接被拒绝。

我们的主脑正是 MoE。切过去等于把核心押在它最弱的地方。项目本身是健康的（[vllm-project/vllm-metal](https://github.com/vllm-project/vllm-metal) 1782 star，当天有提交，仅 23 个 open issue，`brew tap vllm-project/vllm-metal` 可装），**等 MoE 路由验证成熟再评估**。

### 引擎建议

**主力 oMLX**，理由：
- 已装好、已在跑、已指向 `~/.omlx/models`，零迁移成本
- SiliconBench 三项门槛（速度/内存/保真度）全过，只有 3 个引擎做到
- 内存策略「有界增长」，而 `mlx_lm` 是「无界」
- 同时暴露所有模型为独立 API model ID，**切换不重启、不额外占内存** —— 正好满足多档位切换需求
- 短 prompt 并发比 mlx_vlm 略好

**长上下文任务用 mlx_vlm 兜底**：5.8K token 并发场景它快 2 倍。助理的三年期目标历史回溯属于这类，值得为它单独起一个 8090 端口的服务。

---

## 三、MTP 投机解码：实测无效，原因已定位

`mlx-community/Qwen3.8-27B-MTP-4bit`（239 MB）/ `-8bit`（456 MB）是**独立的 MTP 草稿头**，不是完整模型。`mlx_vlm server --draft-model X --draft-kind mtp` 能正常加载（日志 `Drafter ready; speculative decoding enabled.`）。

### 严格 A/B（同 server、同 prompt、temp=0、各 6 次）

| 配置 | 均值 | 中位 | 范围 |
|---|---|---|---|
| 无草稿头 | **10.5 tok/s** | 10.8 | 8.7–11.4 |
| MTP-8bit 草稿头 | **10.4 tok/s** | 10.7 | 9.3–11.1 |

**完全无差异。** 草稿深度调参也只会更差：block-size=2 → 11.5，默认 → 10.3，4 → 8.9，6 → 6.5 tok/s。

### 三个根因（查证得到）

1. **量化的 MTP 权重接受率极低。** BF16 的 MTP 头接受率 79–85%，而量化版只有 5–11% —— 量化误差会沿着专家路由预测逐级放大。本机能拿到的只有 4bit / 8bit，**mlx-community 没有 bf16 的 Qwen3.8-27B MTP 头**。
2. **温度 > 0 会静默关闭投机解码。** Qwen3.5/3.6 系的 MTP 草稿模型设了 `requiresGreedySampling = true`，温度非 0 时直接退化成 target-only 生成。我第一轮用 temp=0.2 测，等于根本没开。
3. **带宽饱和。** 27B dense 在 fp16 下实测是 0.61×（更慢）—— MTP 的额外开销超过节省。

参考：[mlx-lm PR #990](https://github.com/ml-explore/mlx-lm/pull/990)（原生 MTP 实现）、[温度限制 issue](https://github.com/T0mSIlver/mlx-swift-lm/issues/1)、[为什么 MTP 不加速](https://dev.to/alanwest/why-mtp-doesnt-speed-up-your-llamacpp-inference-and-how-to-actually-fix-it-2m2m)、[FastMTP](https://arxiv.org/pdf/2509.18362)。

**踩坑记录**：`mlx_lm` 根本不认这个架构（`ValueError: Model type qwen3_5_mtp not supported`），只有 `mlx_vlm` 的 `--draft-kind mtp` 能加载。

### 其他加速路线（未测，按性价比排序）

1. **关 thinking** —— 见第五节，这是**目前唯一确认有效且收益巨大**的加速手段
2. **oMLX 的 SSD prefix cache**（`cache.enabled` 现在是 false）—— 对助理这种「系统提示词固定 + 历史反复读」的场景可能收益大，值得单独测
3. **`--kv-bits` KV cache 量化** —— 注意 Qwen3.8/qwen3_5 架构**不支持**（mlx-engine#286）
4. 换更小量化档（4bit）—— 但 dense 本来就不是主力，意义不大

---

## 四、模型速度实测（`mlx_lm generate`，4 个真实任务）

| 模型 | 架构 | 权重 | 速度 | 峰值内存 |
|---|---|---|---|---|
| **Qwen3.6-35B-A3B-8bit** | **MoE**（3B 激活） | 40 GB | **47.6–54.4 tok/s** | 37.0 GB |
| Qwen3.8-27B-OptiQ-4bit | dense 3.8 | 19 GB | 10.0–11.4 tok/s | 20.0 GB |
| Qwen3.6-27B-6bit | dense 3.6 | 21 GB | 5.8–8.2 tok/s | 22.3 GB |

**MoE 比新代 dense 快 5 倍，比同代 dense 快 7–9 倍。** 比文献的 3–5 倍更夸张。

两个意外：

- **代差也体现在速度上**：同为 dense 27B、同为 Gated DeltaNet，3.8 代比 3.6 代快近一倍（10.2 vs 6.1 tok/s）。3.8 明显做了推理优化。
- **不要再用「有效带宽 283 GB/s」这个系数推算速度**。它是从 `mlx_vlm server` 的测量反推的，`mlx_lm generate` 是另一条代码路径。用它推出的「Qwen3.8 4bit 能到 17.6 tok/s」实际只有 10.2。

### 各量化档参考（Qwen3.8-27B）

| 档位 | 权重 | 备注 |
|---|---|---|
| 4bit | 16.1 GB | 下载量最大 |
| **OptiQ-4bit** | 19.4 GB(+1.2 GB 附件) | **混合精度：498 层里 261 层保 8bit**，KL 散度敏感度分析选层；自带 MTP 头 + bf16 视觉 sidecar |
| 6bit | 22.8 GB | |
| 8bit | 29.5 GB | |
| bf16 | 54.7 GB | **超过 Metal 建议工作集上限，不要用** |

OptiQ 的坑：**视觉塔在 sidecar 里，stock `mlx-lm` 只能跑纯文本**，图文需要它自己的 `mlx-optiq` 运行时。

---

## 五、质量实测：thinking 是最大的坑

4 个任务（加重试逻辑的代码改写 / 婉拒邮件 / 会议记录转结构化纪要 / 多工具调用计划）× 3 个模型。

### 默认配置下，工具调用任务三个模型全部失败

700 token 预算**全部烧在 thinking 上，没有一个输出最终 JSON**，全部中途截断：

- MoE：中文思考，反复纠结「JSON 里怎么传递上一步结果」
- dense-3.8：**中文 prompt 下用英文思考**，同样纠结同一个问题
- dense-3.6：英文 thinking process，眼看要出 JSON 时被截断

### 关闭 thinking 后结果反转

`mlx_lm --chat-template-config '{"enable_thinking": false}'`，或 API 里 `chat_template_kwargs: {"enable_thinking": false}`：

| 模型 | 工具调用计划 |
|---|---|
| **MoE-3.6-35B-A3B** | ✅ 完整两步（query_db + send_email），邮箱正确，SQL 合理，结果位置留占位符 |
| dense-3.8-27B-OptiQ | ❌ **只给了一步，漏掉 send_email** |
| dense-3.6-27B | ✅ 完整两步 |

**这条结果和文献预期相反** —— 文献说 dense 的工具保真度更高（Terminal-Bench +11.1 分），但本机实测新代 dense 在这个任务上漏了一个工具调用。单个样本不足以定论，但这是真实证据，而且方向对助理需求 5（自主调数据库）不利。

**结论：thinking 必须全局关闭。** 它的影响远大于模型选择 —— 开着的时候三个模型全挂，关掉之后两个满分。

---

## 六、最终建议

### 引擎

| 用途 | 引擎 | 端口 |
|---|---|---|
| **默认** | oMLX 0.6.4 | 8088 |
| 长上下文（>4K prompt） | mlx_vlm server | 8090 |
| 暂不考虑 | vllm-metal（MoE 路由未验证）、llama.cpp（无 MLX 加速） | — |

### 模型分层

| 层 | 模型 | 何时用 |
|---|---|---|
| **主脑（默认）** | `Qwen3.6-35B-A3B-MLX-8bit` | 目标管理、周计划、邮件、文档整理、工具调用 —— 即绝大多数场景 |
| 硬任务备胎 | `Qwen3.8-27B-OptiQ-4bit` | 跨文件重构、复杂多步调试。**注意它在工具调用上实测更差，别用于 agent 循环** |
| 同代对照 | `Qwen3.6-27B-MLX-6bit` | 只做基准对照，日常不用（最慢） |
| OCR/表格 | `GLM-OCR-bf16` | 截图记账、票据、表格 |

### 强制配置

```jsonc
{
  "chat_template_kwargs": { "enable_thinking": false },  // 必须，否则工具调用必挂
  // 不要设 kv_bits —— qwen3_5 架构不支持 KV cache 量化
  // 不要挂 MTP 草稿头 —— 实测零收益
}
```

### 切换方式

oMLX 把 `~/.omlx/models` 下所有模型**同时**暴露为独立 API model ID，切换只是换请求里的 `model` 字段 —— 不重启、不额外占内存。

```bash
./scripts/assistant-model.sh            # 看当前档位
./scripts/assistant-model.sh moe        # 切主力(默认)
./scripts/assistant-model.sh dense      # 切 3.8 OptiQ
./scripts/assistant-model.sh dense36    # 切 3.6 dense
./scripts/assistant-model.sh ocr        # 切 OCR
./scripts/assistant-model.sh list       # 列出 oMLX 全部模型
./scripts/assistant-model.sh test moe   # 实发请求验证
```

档位记在 `~/.omlx/assistant-model`，供 harness 读取。

---

## 七、待办 / 未验证

- [ ] **oMLX SSD prefix cache**（`cache.enabled=false` → true）对助理场景的收益 —— 系统提示词固定 + 历史反复读，理论收益大
- [ ] MoE 在 `mlx_vlm` 上跑长上下文并发的**内存上限**（本次 c=8 时系统空闲内存降到 31%）
- [ ] 质量对比只做了单样本，`dense-3.8 漏工具调用` 需要更多样本确认是稳定缺陷还是偶发
- [ ] vllm-metal 的 MoE 专家路由何时验证成熟，届时重新评估（它的并发扩展性是三个引擎里最好的）
- [ ] Qwen3.8-27B 若出 **bf16 MTP 头**，MTP 值得重测（接受率 79–85% vs 现在 5–11%）
