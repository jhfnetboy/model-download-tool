#!/usr/bin/env python3
"""
修复 mflux 社区模型的 T5 shared embedding 量化问题。
症状: ValueError: [dequantize] The matrix should be given as a uint32
原因: 社区打包模型的 T5 shared.weight 是 bf16，mflux 0.17+ 期望 uint32。
修复: 用 group_size=64, bits=4 量化 shared.weight，写回 safetensors。

用法: python patch_t5_shared.py [模型路径...]
默认修复所有 ~/.omlx/models/ 下的 FLUX 模型。
"""
import sys, os, shutil, glob
from pathlib import Path

def patch_model(model_dir: str) -> bool:
    model_dir = Path(model_dir).expanduser()
    t5_dir = model_dir / "text_encoder_2"
    if not t5_dir.exists():
        print(f"  跳过（无 text_encoder_2）: {model_dir.name}")
        return False

    try:
        import mlx.core as mx
    except ImportError:
        print("需要先: source ~/venvs/ml/bin/activate")
        sys.exit(1)

    for shard in sorted(glob.glob(str(t5_dir / "*.safetensors"))):
        weights = mx.load(shard)
        if "shared.weight" not in weights:
            continue

        shared = weights["shared.weight"]
        if shared.dtype != mx.bfloat16:
            print(f"  已是量化格式，跳过: {model_dir.name}")
            return False

        print(f"  shared.weight: {shared.dtype} {shared.shape} → 量化中...")

        backup = shard + ".backup"
        if not os.path.exists(backup):
            shutil.copy2(shard, backup)
            print(f"  已备份: {os.path.basename(backup)}")

        quantized, scales, biases = mx.quantize(shared, group_size=64, bits=4)
        mx.eval(quantized, scales, biases)

        new_weights = dict(weights)
        new_weights["shared.weight"]  = quantized
        new_weights["shared.scales"]  = scales
        new_weights["shared.biases"]  = biases

        mx.save_safetensors(shard, new_weights)
        print(f"  ✓ 写回: {os.path.basename(shard)}  "
              f"({quantized.shape} uint32, scales {scales.shape})")
        return True

    print(f"  未找到 shared.weight: {model_dir.name}")
    return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        models = sys.argv[1:]
    else:
        # 默认扫描所有 FLUX 相关模型
        base = Path.home() / ".omlx/models"
        models = [
            str(p) for p in base.iterdir()
            if p.is_dir() and any(
                kw in p.name.lower()
                for kw in ["flux", "schnell", "kontext", "dev"]
            )
        ]

    if not models:
        print("没有找到 FLUX 模型，请手动指定路径")
        sys.exit(1)

    print(f"扫描 {len(models)} 个模型目录...\n")
    fixed = 0
    for m in models:
        name = Path(m).name
        print(f"[{name}]")
        if patch_model(m):
            fixed += 1
        print()

    print(f"完成: {fixed}/{len(models)} 个模型已修复")
    if fixed:
        print("现在可以正常运行 mflux-generate 了")
