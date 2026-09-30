#!/usr/bin/env python3
"""
FLUX.1 Schnell - 已废弃，用 FLUX.2 Klein 代替

社区预量化的 schnell 模型（madroid/dhairyashil）用旧版 mflux 保存，
混合了量化/未量化层，与 mflux 0.17.5 不兼容，无法修复。

替代方案（更好）:
  python test_flux2_klein.py fast    # 8步，~40秒，FLUX.2 Klein

如果坚持用 schnell，需要从 black-forest-labs 官方下载 bf16 原版（30GB）：
  HF_ENDPOINT=https://hf-mirror.com \\
    mflux-save --model schnell --quantize 4 --path ~/.omlx/models/mflux-schnell-4bit
然后把 MODEL 改成上面的路径，用 mflux-generate --model ~/.omlx/models/mflux-schnell-4bit ...
"""
print("Schnell 与 mflux 0.17.5 不兼容，请改用 FLUX.2 Klein:")
print("  python test_flux2_klein.py fast")
print()
print("或用 HF 官方原版 schnell（需下载 30GB）:")
print("  HF_ENDPOINT=https://hf-mirror.com \\")
print("    mflux-save --model schnell --quantize 4 --path ~/.omlx/models/mflux-schnell-4bit")
