#!/usr/bin/env python3
"""
qwen3-fluxassistant-mlx-6bit - FLUX 提示词助手（文字生成模型）
模型路径: ~/.omlx/models/qwen3-fluxassistant-mlx-6bit
框架: mlx-lm (pip install mlx-lm)

这不是图像生成模型。它是 Qwen3 语言模型，专门微调用于：
  - 把你的简单描述扩写成高质量 FLUX prompt
  - 分析图片并生成对应 prompt（反推）
  - 给出风格、光线、构图的专业建议

工作流: 用此模型生成 prompt → 喂给 FLUX Dev/Schnell 出图
"""
import sys
from pathlib import Path

try:
    from mlx_lm import load, generate
    from mlx_lm.utils import load as mlx_load
except ImportError:
    print("mlx-lm 未安装，请运行: pip install mlx-lm")
    sys.exit(1)

MODEL_PATH = str(Path.home() / ".omlx/models/qwen3-fluxassistant-mlx-6bit")

SYSTEM_PROMPT = (
    "You are an expert FLUX image generation prompt engineer. "
    "When given a simple description, expand it into a detailed, high-quality FLUX prompt. "
    "Include: subject details, lighting, camera angle, style, mood, color palette, and technical quality tags. "
    "Output only the prompt, no explanation."
)

EXAMPLES = [
    "一只熊猫在竹林里打太极",
    "赛博朋克风格的上海街头",
    "古典中国水墨山水画风格的桂林山水",
]

def generate_prompt(user_input: str, max_tokens: int = 300) -> str:
    print(f"加载模型: {MODEL_PATH}")
    model, tokenizer = load(MODEL_PATH)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_input},
    ]

    # 使用 chat template
    if hasattr(tokenizer, "apply_chat_template"):
        formatted = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        formatted = f"System: {SYSTEM_PROMPT}\nUser: {user_input}\nAssistant:"

    response = generate(
        model, tokenizer,
        prompt=formatted,
        max_tokens=max_tokens,
        verbose=False,
    )
    return response

if __name__ == "__main__":
    if not Path(MODEL_PATH).exists():
        print(f"模型不存在: {MODEL_PATH}")
        sys.exit(1)

    user_input = sys.argv[1] if len(sys.argv) > 1 else EXAMPLES[0]
    print(f"\n输入描述: {user_input}")
    print("-" * 60)

    result = generate_prompt(user_input)
    print(f"生成的 FLUX Prompt:\n{result}")
    print("-" * 60)
    print("\n复制上方 prompt，粘贴到 test_flux_dev.py 的 PROMPTS 列表中使用")
