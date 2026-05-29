#!/usr/bin/env python3
"""
Lance-3B-Video-bf16 - 文生视频 (ByteDance, MLX port)
模型路径: ~/.omlx/models/Lance-3B-Video-bf16
框架: lance-mlx (需要从 GitHub 安装)

安装命令:
  pip install git+https://github.com/xocialize/lance-mlx.git

Alpha 状态说明（来自模型 README）:
  ✅ 生产可用: 256x256~768x768, ≤25帧
  ❌ 有问题:   768x768 × 49帧+ (内存峰值 84GB，有网格噪声)
  推荐分辨率: 512x512 × 17帧 (最稳定，约33秒/clip on M2 Max)
"""
import subprocess, sys
from pathlib import Path

MODEL = Path.home() / ".omlx/models/Lance-3B-Video-bf16"
OUTPUT_DIR = Path.home() / "Desktop/lance_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# 从保守分辨率开始测试
TESTS = [
    {
        "name":    "panda_surf_256",
        "prompt":  "A red panda surfing on ocean waves, dynamic motion, vivid colors",
        "width":   256,
        "height":  256,
        "frames":  17,
        "steps":   30,
        "seed":    42,
    },
    {
        "name":    "city_walk_512",
        "prompt":  "A person walking through a neon-lit Tokyo street at night, cinematic, slow motion",
        "width":   512,
        "height":  512,
        "frames":  17,
        "steps":   30,
        "seed":    42,
    },
]

def check_lance_mlx():
    result = subprocess.run(
        [sys.executable, "-c", "import lance_mlx"],
        capture_output=True
    )
    if result.returncode != 0:
        print("lance-mlx 未安装，请先运行:")
        print("  pip install git+https://github.com/xocialize/lance-mlx.git")
        print()
        print("安装后重新运行此脚本")
        return False
    return True

def run_t2v(cfg: dict):
    output = OUTPUT_DIR / f"lance_{cfg['name']}.mp4"
    cmd = [
        sys.executable, "-m", "lance_mlx.generate",
        "--model-path", str(MODEL),
        "--task", "t2v",
        "--prompt", cfg["prompt"],
        "--width",  str(cfg["width"]),
        "--height", str(cfg["height"]),
        "--num-frames", str(cfg["frames"]),
        "--num-inference-steps", str(cfg["steps"]),
        "--seed", str(cfg["seed"]),
        "--cfg-renorm-type", "global",   # Phase 5m fix，必须加
        "--output-path", str(output),
    ]
    print(f"\n[Lance t2v] {cfg['name']}")
    print(f"  分辨率: {cfg['width']}x{cfg['height']} × {cfg['frames']}帧")
    print(f"  Prompt: {cfg['prompt'][:70]}...")
    print(f"  预计耗时: {cfg['width']//256 * cfg['frames'] * 2}~{cfg['width']//256 * cfg['frames'] * 4} 秒")
    subprocess.run(cmd, check=True)
    print(f"  已保存: {output}")
    return output

if __name__ == "__main__":
    if not MODEL.exists():
        print(f"模型不存在: {MODEL}")
        sys.exit(1)

    if not check_lance_mlx():
        sys.exit(1)

    # 从最小分辨率开始，验证环境
    run_t2v(TESTS[0])

    print(f"\n输出目录: {OUTPUT_DIR}")
    print("成功后可尝试 TESTS[1]（512x512，更好质量）")
