---
name: flux-gen
description: Generate images locally with FLUX.2 Klein via MLX on Apple Silicon. Checks model availability, sources the ML venv, and produces PNG output from a text prompt. Use when the user wants to generate an image using their local FLUX.2 model.
origin: model-download-tool
---

# FLUX.2 Local Image Generation

Generate images on Apple Silicon using the local FLUX.2 Klein MLX model.

## When to Activate

- User says "generate an image", "画一张", "生成图片", or provides a visual description
- User invokes `/flux-gen` directly, with or without a prompt
- User wants to test or use the local FLUX.2 model

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python venv at `~/venvs/ml` with `mflux` installed
- Model: `~/.omlx/models/FLUX.2-klein-4B-mflux-4bit`

## Workflow

### Step 1: Check Environment

Run these checks in parallel:

```bash
# Check model
ls ~/.omlx/models/FLUX.2-klein-4B-mflux-4bit 2>/dev/null && echo "MODEL_OK" || echo "MODEL_MISSING"

# Check venv + mflux
source ~/venvs/ml/bin/activate && python3 -c "import mflux; print('MFLUX_OK')" 2>/dev/null || echo "MFLUX_MISSING"
```

**If MODEL_MISSING**: Tell the user to run:
```bash
source ~/venvs/ml/bin/activate
mdt download Runpod/FLUX.2-klein-4B-mflux-4bit
```
Stop here until they confirm it's downloaded.

**If MFLUX_MISSING**: Tell the user to run:
```bash
source ~/venvs/ml/bin/activate
pip install mflux
```

### Step 2: Get the Prompt

If the user provided a prompt in the args, use it directly.

If no prompt was given, ask:
> "请描述你想生成的图片内容（中英文均可）："

Keep the prompt as-is — do NOT rewrite or expand it unless the user asks. If the user asks for help writing a good prompt, offer a richer version.

### Step 3: Choose Mode

If the user didn't specify a mode, default to **fast**.

| 模式 | 步数 | 分辨率 | 预计时间 |
|------|------|--------|---------|
| fast    | 8步  | 768×768   | ~40秒  |
| quality | 16步 | 1024×1024 | ~90秒  |
| full    | 20步 | 1024×1024 | ~150秒 |

Ask only if the user seems to care about quality vs speed. Otherwise just use fast.

### Step 4: Generate

Create output directory and run:

```bash
source ~/venvs/ml/bin/activate
mkdir -p ~/Desktop/flux_outputs

mflux-generate-flux2 \
  --model ~/.omlx/models/FLUX.2-klein-4B-mflux-4bit \
  --base-model flux2-klein-4b \
  --prompt "<PROMPT>" \
  --steps <STEPS> \
  --seed 42 \
  --width <WIDTH> \
  --height <HEIGHT> \
  --low-ram \
  --output ~/Desktop/flux_outputs/flux2_<SLUG>_<TIMESTAMP>.png
```

Where:
- `<PROMPT>` = the user's prompt (quote carefully if it contains special chars)
- `<STEPS>` = 8 / 16 / 20 depending on mode
- `<WIDTH>/<HEIGHT>` = 768 or 1024 depending on mode
- `<SLUG>` = first 3 words of prompt, snake_case, truncated to 30 chars
- `<TIMESTAMP>` = current time as `HHMM`

### Step 5: Report Result

On success:
- Tell the user the output path
- Mention the generation time (from the mflux output)
- Offer: "想换个 seed 重新生成，或者调整 prompt 吗？"

On failure:
- Show the last 10 lines of error output
- Diagnose: OOM (reduce resolution), mflux crash (check venv), wrong model path

## Tips to Share with User

- **Seed**: same seed + same prompt = same image. Change seed to get variations.
- **Prompt language**: English prompts generally produce better results.
- **Style keywords**: add `photorealistic`, `cinematic`, `oil painting`, `anime style`, `8k` etc.
- **Negative space**: FLUX.2 doesn't support negative prompts natively; describe what you WANT instead.
- **Multiple outputs**: run with `--auto-seeds 4` to get 4 variations in one go.

## Installation (for other repos)

Copy this skill to your global Claude skills directory:

```bash
cp -r <path-to-model-download-tool>/skills/flux-gen ~/.claude/skills/
```

Or run the install script from the model-download-tool repo:

```bash
bash <path-to-model-download-tool>/install_skills.sh
```
