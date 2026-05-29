#!/usr/bin/env python3
"""
FLUX.1 Kontext - 图生图编辑（需先用 mflux-save 准备模型）
模型路径: ~/.omlx/models/mflux-kontext-4bit（mflux 原生格式）

首次使用前，运行一次建模型（下载 ~34GB bf16，量化保存约 10GB）：
  HF_ENDPOINT=https://hf-mirror.com \\
    mflux-save --model kontext --quantize 4 --path ~/.omlx/models/mflux-kontext-4bit

用法: python test_flux_kontext.py <输入图片路径>
  图片放 ~/Downloads/ 或 ~/Pictures/（Desktop 有 macOS 沙盒限制）

Kontext 接受原图 + 文字指令，输出修改后的图：
  - "change the sky to a dramatic sunset"
  - "make the person wear a red jacket"
  - "convert to anime art style"
"""
import subprocess, sys, os
from pathlib import Path

MODEL = Path.home() / ".omlx/models/mflux-kontext-4bit"
OUTPUT_DIR = Path.home() / "Desktop/flux_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EDITS = [
    ("sunset_sky",   "Change the sky to a dramatic golden sunset with orange and purple clouds"),
    ("sketch_style", "Convert to pencil sketch style, black and white, detailed line art"),
    ("anime_style",  "Convert to anime art style, vibrant colors, cel shading"),
]

def run(image_path: Path, edit_name: str, prompt: str, steps: int = 28, seed: int = 42):
    output = OUTPUT_DIR / f"kontext_{edit_name}_seed{seed}.png"
    cmd = [
        "mflux-generate-kontext",
        "--model", str(MODEL),
        "--image-path", str(image_path),
        "--prompt", prompt,
        "--steps", str(steps),
        "--seed", str(seed),
        "--output", str(output),
    ]
    print(f"\n[Kontext] {edit_name} → {output.name}")
    print(f"  原图: {image_path}")
    print(f"  指令: {prompt[:70]}...")
    subprocess.run(cmd, check=True)
    print(f"  已保存: {output}")
    return output

if __name__ == "__main__":
    if not MODEL.exists():
        print(f"模型不存在: {MODEL}")
        print()
        print("请先建模（走 hf-mirror 下载，约 34GB，量化后保存 ~10GB）：")
        print("  HF_ENDPOINT=https://hf-mirror.com \\")
        print("    mflux-save --model kontext --quantize 4 --path ~/.omlx/models/mflux-kontext-4bit")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("用法: python test_flux_kontext.py <输入图片路径>")
        print("例如: python test_flux_kontext.py ~/Downloads/photo.jpg")
        print("注意: 图片放 ~/Downloads 或 ~/Pictures，不要放 Desktop（macOS 沙盒）")
        sys.exit(1)

    image_path = Path(sys.argv[1]).expanduser()
    if not image_path.exists():
        print(f"图片不存在: {image_path}")
        sys.exit(1)

    edit_name, prompt = EDITS[0]
    run(image_path, edit_name, prompt, steps=28, seed=42)
    print(f"\n输出目录: {OUTPUT_DIR}")
