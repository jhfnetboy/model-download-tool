#!/usr/bin/env python3
"""
FLUX.1 Schnell 4bit - 极速文生图（本地模型，4步极速）
模型路径: ~/.omlx/models/flux.1-schnell-mflux-4bit（mflux 原生格式）

首次使用前下载模型：
  mdt download madroid/flux.1-schnell-mflux-4bit

Schnell = "快"（德语），4步出图，适合快速验证 prompt，
质量不如 Dev，但速度快 5-6 倍。
"""
import subprocess, sys
from pathlib import Path

MODEL = Path.home() / ".omlx/models/flux.1-schnell-mflux-4bit"
OUTPUT_DIR = Path.home() / "Desktop/flux_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPTS = [
    ("red_panda", "A red panda sitting on a bamboo branch, cute, detailed fur, soft lighting"),
    ("landscape", "Mountain lake at dawn, mirror reflection, misty atmosphere, photorealistic"),
    ("abstract",  "Abstract geometric shapes in vibrant neon colors on dark background"),
]

def run(prompt_name: str, prompt: str, steps: int = 4, seed: int = 42,
        width: int = 1024, height: int = 1024):
    output = OUTPUT_DIR / f"schnell_{prompt_name}_s{steps}_seed{seed}.png"
    cmd = [
        "mflux-generate",
        "--model", str(MODEL),
        "--base-model", "schnell",
        "--prompt", prompt,
        "--steps", str(steps),
        "--seed", str(seed),
        "--width", str(width),
        "--height", str(height),
        "--low-ram",
        "--output", str(output),
    ]
    print(f"\n[Schnell] {prompt_name} → {output.name}")
    print(f"  步数: {steps}  分辨率: {width}x{height}  种子: {seed}")
    subprocess.run(cmd, check=True)
    print(f"  已保存: {output}")
    return output

if __name__ == "__main__":
    if not MODEL.exists():
        print(f"模型不存在: {MODEL}")
        print("请先下载：")
        print("  source ~/venvs/ml/bin/activate")
        print("  mdt download madroid/flux.1-schnell-mflux-4bit")
        sys.exit(1)

    name, prompt = PROMPTS[0]
    run(name, prompt, steps=4, seed=42)
    print(f"\n输出目录: {OUTPUT_DIR}")
