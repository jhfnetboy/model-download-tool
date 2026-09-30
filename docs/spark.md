已完成。oMLX 0.6.4 现在可以直接运行 Spark-X2.5-4B OptiQ 量化模型。

  ## 实施方式

  我没有直接替换 oMLX 内置的整套 MLX-LM，因为 oMLX 对固定版本做了大量缓存、批处理和模型兼容补丁，强行升级容易破坏其他模型。

  采用的是更安全的用户级 OptiQ 兼容覆盖层：

  - 保留 oMLX 0.6.4
  - 保留内置 MLX-LM 0.31.3
  - 安装 mlx-optiq 0.5.10
  - 启动 oMLX 时自动注册 OptiQ 的 spark2_5 架构
  - 不修改 /Applications/oMLX.app
  - App 代码签名仍然有效
  - 未来 oMLX 原生支持 spark2_5 后，覆盖层会自动停止介入

  安装位置：

  ~/.local/share/omlx-extensions/mlx-optiq-spark/0.5.10

  启动钩子：

  ~/.local/lib/python3.11/site-packages/omlx_optiq_spark_bootstrap.py
  ~/.local/lib/python3.11/site-packages/omlx_optiq_spark_bootstrap.pth

  ## 验证结果

  后台服务已经恢复：

  http://127.0.0.1:8088

  模型 ID：

  Spark-X2.5-4B-OptiQ-4bit

  oMLX 正确识别了模型结构：

  36 层
  9 个全局 KVCache
  27 个 RotatingKVCache
  滑动窗口：512 tokens
  最大上下文：1,048,576 tokens

  OpenAI 兼容 API 实测结果：

  常驻 oMLX OptiQ 运行成功。

  性能测试：

  - 首次请求，包括模型加载：约 2.63 秒
  - 模型加载耗时：约 1.96 秒
  - 第二次请求：约 0.34 秒
  - 日志生成速度：约 31–36 tokens/s
  - 当前模型内存：约 3.19 GB
  - oMLX 健康状态：healthy
  - App 代码签名：有效

  ## 现在怎么使用

  可以直接在 oMLX 界面里选择：

  Spark-X2.5-4B-OptiQ-4bit

  或通过现有的 OpenAI 兼容 API 调用：

  http://127.0.0.1:8088/v1/chat/completions

  API Key 安全设置保持原样，我没有修改或输出密钥。

  ## 注意事项

  当前 oMLX 设置中 Paged SSD KV Cache 是关闭的，因此第二次请求变快主要是因为模型已经常驻内存，而不是 SSD 前缀缓存命中。这不影响正常运行；如果需要超长上下文或 Agent 多轮对话的缓存复用，可以再单独开启。

  截至 2026 年 9 月 17 日：

  - oMLX 最新稳定版仍是 0.6.4。
  - oMLX 主分支已在 9 月 14 日加入 Spark-X2.5 支持。
  - 9 月 17 日又更新了 MLX-LM 引擎并改用上游原生实现。
  - 下一正式版预计会原生支持；届时当前覆盖层会检测到原生模块并自动让位。

  ## 回滚方法

  如需临时禁用：

  export OMLX_OPTIQ_DISABLE=1

  如需永久移除覆盖层：

  omlx stop

  mv ~/.local/lib/python3.11/site-packages/omlx_optiq_spark_bootstrap.pth \
     ~/.local/lib/python3.11/site-packages/omlx_optiq_spark_bootstrap.pth.disabled

  omlx start

  当前仓库中的原有未提交文件没有被修改。
