#!/usr/bin/env python3
"""
FLUX.2 Klein 4B - 文生图（mflux 原生格式，直接可用）
模型路径: ~/.omlx/models/FLUX.2-klein-4B-mflux-4bit

用法:
  python test_flux2_klein.py          # 快速模式：8步 768x768 (~40秒)
  python test_flux2_klein.py quality  # 质量模式：16步 1024x1024 (~90秒)
  python test_flux2_klein.py full     # 原始模式：20步 1024x1024 (~2.5分钟)

速度参考（M2 Max）:
  8步  768×768  → ~40秒   (测试 prompt 用)
  12步 768×768  → ~60秒   (日常出图)
  16步 1024×1024→ ~90秒   (高质量)
  20步 1024×1024→ ~150秒  (最高质量，当前默认)

red panda = 小熊猫（Ailurus fulgens）✓ 不是大熊猫
"""
import subprocess, sys
from pathlib import Path

MODEL = Path.home() / ".omlx/models/FLUX.2-klein-4B-mflux-4bit"
OUTPUT_DIR = Path.home() / "Desktop/flux_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 三种预设
PRESETS = {
    "fast":    {"steps": 8,  "width": 768,  "height": 768},   # ~40s
    "quality": {"steps": 16, "width": 1024, "height": 1024},  # ~90s
    "full":    {"steps": 20, "width": 1024, "height": 1024},  # ~150s
}

PROMPTS = [
    ("red_panda", "A red panda (小熊猫) sitting on a bamboo branch in a misty forest, "
                  "detailed fluffy fur, rust-red coat with white ear tips, "
                  "soft natural lighting, photorealistic, 8k"),
    ("cityscape",  "Futuristic city at night, neon lights reflecting on wet streets, cinematic, ultra detailed"),
    ("portrait",   "Portrait of a young woman with red hair, soft studio lighting, bokeh, photorealistic"),
    ("nature",     "Ancient forest with sunrays through tall pine trees, misty morning, hyperrealistic"),
]

def run(prompt_name: str, prompt: str, steps: int, width: int, height: int, seed: int = 42):
    output = OUTPUT_DIR / f"flux2_{prompt_name}_s{steps}_{width}x{height}_seed{seed}.png"
    cmd = [
        "mflux-generate-flux2",
        "--model", str(MODEL),
        "--base-model", "flux2-klein-4b",
        "--prompt", prompt,
        "--steps", str(steps),
        "--seed", str(seed),
        "--width", str(width),
        "--height", str(height),
        "--low-ram",   # 减少内存压力，与其他大模型共存
        "--output", str(output),
    ]
    print(f"\n[FLUX.2 Klein] {prompt_name}")
    print(f"  步数: {steps}  分辨率: {width}x{height}  种子: {seed}")
    print(f"  Prompt: {prompt[:80]}...")
    subprocess.run(cmd, check=True)
    print(f"  已保存: {output}")
    return output

if __name__ == "__main__":
    if not MODEL.exists():
        print(f"模型不存在: {MODEL}")
        print("请先运行: mdt download Runpod/FLUX.2-klein-4B-mflux-4bit")
        sys.exit(1)

    mode = sys.argv[1] if len(sys.argv) > 1 else "fast"
    if mode not in PRESETS:
        print(f"模式: fast / quality / full  (当前: {mode})")
        sys.exit(1)

    preset = PRESETS[mode]
    print(f"模式: {mode}  预计耗时: fast~40s / quality~90s / full~150s")

    name, prompt = PROMPTS[0]
    run(name, prompt, seed=42, **preset)

    # 全量测试（取消注释）：
    # for name, prompt in PROMPTS:
    #     run(name, prompt, seed=42, **preset)

    print(f"\n输出目录: {OUTPUT_DIR}")
