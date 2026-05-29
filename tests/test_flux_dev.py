#!/usr/bin/env python3
"""
FLUX.1 Dev 4bit - 高质量文生图（需先用 mflux-save 准备模型）
模型路径: ~/.omlx/models/mflux-dev-4bit（mflux 原生格式）

首次使用前，运行一次建模型（下载 30GB bf16，量化保存约 10GB）：
  HF_ENDPOINT=https://hf-mirror.com \\
    mflux-save --model dev --quantize 4 --path ~/.omlx/models/mflux-dev-4bit

Dev vs FLUX.2 Klein:
  - Dev: 更慢，质量最高，适合出最终图
  - FLUX.2 Klein: 更快，适合快速验证 prompt
"""
import subprocess, sys, os
from pathlib import Path

MODEL = Path.home() / ".omlx/models/mflux-dev-4bit"
OUTPUT_DIR = Path.home() / "Desktop/flux_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPTS = [
    ("cityscape", "A futuristic city at night, neon lights reflecting on wet streets, cinematic lighting, ultra detailed"),
    ("portrait",  "Portrait of a young woman with red hair, soft studio lighting, bokeh background, photorealistic"),
    ("nature",    "Ancient forest with rays of sunlight through tall pine trees, misty morning, hyperrealistic"),
]

def run(prompt_name: str, prompt: str, steps: int = 25, seed: int = 42):
    output = OUTPUT_DIR / f"dev_{prompt_name}_s{steps}_seed{seed}.png"
    cmd = [
        "mflux-generate",
        "--model", str(MODEL),
        "--base-model", "dev",
        "--prompt", prompt,
        "--steps", str(steps),
        "--seed", str(seed),
        "--height", "1024",
        "--width", "1024",
        "--guidance", "3.5",
        "--output", str(output),
    ]
    print(f"\n[Dev] {prompt_name} → {output.name}")
    print(f"  步数: {steps}  种子: {seed}")
    subprocess.run(cmd, check=True)
    print(f"  已保存: {output}")
    return output

if __name__ == "__main__":
    if not MODEL.exists():
        print(f"模型不存在: {MODEL}")
        print()
        print("请先建模（走 hf-mirror 下载，约 30GB，量化后保存 ~10GB）：")
        print("  HF_ENDPOINT=https://hf-mirror.com \\")
        print("    mflux-save --model dev --quantize 4 --path ~/.omlx/models/mflux-dev-4bit")
        sys.exit(1)

    name, prompt = PROMPTS[0]
    run(name, prompt, steps=25, seed=42)
    print(f"\n输出目录: {OUTPUT_DIR}")
