#!/usr/bin/env python3
"""mdt - Model Download Tool
Fuzzy search + smart download for AI models from HuggingFace / ModelScope
"""

import os
import sys
import json
import subprocess
import argparse
import shutil
from pathlib import Path
from typing import List, Dict, Optional
import urllib.request as _urlrequest
from urllib.request import urlretrieve, Request
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.json"

# ─── config ──────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "download_dir": "~/.omlx/models",
    "mirror":       "https://hf-mirror.com",
    "platform":     "mac",        # mac | mac-gguf | gguf | windows | linux | all
    "source":       "huggingface",# huggingface | modelscope | all
    "limit":        20,
    "threads":      8,
    "jobs":         5,
    "token":        "",
}

# platform → HuggingFace filter tag (None = no filter)
PLATFORM_FILTERS: Dict[str, Optional[str]] = {
    "mac":      "mlx",   # Apple MLX — best for M-chip
    "mac-gguf": "gguf",  # GGUF via llama.cpp + Metal
    "gguf":     "gguf",  # GGUF cross-platform
    "windows":  None,    # all (CUDA / CPU)
    "linux":    None,    # all
    "all":      None,
}

PLATFORM_LABELS: Dict[str, str] = {
    "mac":      "Mac M-chip (MLX)",
    "mac-gguf": "Mac M-chip (GGUF)",
    "gguf":     "GGUF",
    "windows":  "Windows",
    "linux":    "Linux",
    "all":      "全平台",
}

# Priority order: platform-specific formats first, safetensors is fallback only
PRIORITY_FORMATS = ["mlx", "gguf", "ggml", "coreml", "onnx"]


def load_config() -> Dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg: Dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print(f"  ✓ 配置已保存: {CONFIG_PATH}")


CFG = load_config()

HF_MIRROR = os.environ.get("HF_ENDPOINT", CFG["mirror"])
HF_API = "https://huggingface.co"
MODELSCOPE_API = "https://modelscope.cn/api/v1"
HFD_URL = "https://hf-mirror.com/hfd/hfd.sh"


# ─── search ──────────────────────────────────────────────────────────────────

class _RedirectHandler(_urlrequest.HTTPRedirectHandler):
    """Follow HTTP 308 Permanent Redirect (Python < 3.11 omits it)."""
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)

_OPENER = _urlrequest.build_opener(_RedirectHandler())


def _http_get(url: str, timeout: int = 15) -> Optional[dict]:
    try:
        req = Request(url, headers={"User-Agent": "mdt/1.0"})
        with _OPENER.open(req, timeout=timeout) as r:
            return json.loads(r.read())
    except (URLError, HTTPError, json.JSONDecodeError) as e:
        print(f"  请求失败: {e}")
        return None


def _extract_format(tags: List[str]) -> str:
    lower = [t.lower() for t in tags]
    # Show platform-specific formats first (mlx/gguf/etc); safetensors only as fallback
    found = [f for f in PRIORITY_FORMATS if f in lower]
    if found:
        return "/".join(found[:2])
    return "safetensors" if "safetensors" in lower else "-"


def search_huggingface(query: str, limit: int = 20, platform: str = "all") -> List[Dict]:
    hf_filter = PLATFORM_FILTERS.get(platform)
    params: Dict = {"search": query, "limit": limit, "sort": "downloads", "direction": -1}
    if hf_filter:
        params["filter"] = hf_filter
    data = _http_get(f"{HF_API}/api/models?{urlencode(params)}")
    if not data:
        return []
    results = []
    for m in data:
        tags = m.get("tags") or []
        results.append({
            "source":    "huggingface",
            "id":        m.get("id", ""),
            "downloads": m.get("downloads", 0),
            "likes":     m.get("likes", 0),
            "updated":   (m.get("lastModified") or "")[:10],
            "task":      m.get("pipeline_tag") or "-",
            "format":    _extract_format(tags),
            "tags":      tags,
        })
    return results


def search_modelscope(query: str, limit: int = 20) -> List[Dict]:
    params = urlencode({
        "PageSize": limit, "PageNumber": 1,
        "Query": query, "Target": "model", "SortBy": "Downloads",
    })
    data = _http_get(f"{MODELSCOPE_API}/models?{params}")
    if not data or not data.get("Data"):
        return []
    results = []
    for m in (data.get("Data", {}).get("Models") or []):
        results.append({
            "source":    "modelscope",
            "id":        m.get("Path", ""),
            "downloads": m.get("Downloads", 0),
            "likes":     m.get("Likes", 0),
            "updated":   (m.get("UpdatedAt") or "")[:10],
            "task":      m.get("Tasks", [{"Name": "-"}])[0].get("Name", "-") if m.get("Tasks") else "-",
            "format":    "-",
            "tags":      [],
        })
    return results


def search_models(query: str, limit: int = 20, source: str = "huggingface",
                  platform: str = "all") -> List[Dict]:
    label = PLATFORM_LABELS.get(platform, platform)
    print(f"  正在搜索「{query}」(来源: {source} | 平台: {label})...")
    if source == "modelscope":
        return search_modelscope(query, limit)
    if source == "all":
        hf = search_huggingface(query, limit // 2 + 1, platform)
        ms = search_modelscope(query, limit // 2 + 1)
        return hf + ms
    return search_huggingface(query, limit, platform)


# ─── model size ──────────────────────────────────────────────────────────────

def fetch_model_size(model_id: str) -> Optional[int]:
    """Return total repo size in bytes via HF API usedStorage field."""
    # hf-mirror.com redirects /api/models/{id} to huggingface.co; call official API directly
    data = _http_get(f"{HF_API}/api/models/{model_id}")
    if not data:
        return None
    return data.get("usedStorage") or None


def _fmt_size(n: Optional[int]) -> str:
    if not n:
        return "未知"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ─── display ─────────────────────────────────────────────────────────────────

def _fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def display_models(models: List[Dict], platform: str = "all") -> None:
    src_tag = {"huggingface": "\033[33mHF\033[0m", "modelscope": "\033[36mMS\033[0m"}
    label = PLATFORM_LABELS.get(platform, platform)
    print(f"\n  平台过滤: {label}\n")
    # Column widths (visible chars): seq=4 src=2 mid=44 dl=7 lk=6 fmt=14 task=rest
    hdr = (f"{'序号':>4}  {'来':>2}  {'模型 ID':<44} {'下载量':>7}  {'点赞':>6}  "
           f"{'格式(mlx/gguf…)':<14}  {'任务类型'}")
    print(hdr)
    print("─" * 108)
    for i, m in enumerate(models, 1):
        src  = src_tag.get(m["source"], m["source"])
        mid  = m["id"][:43]
        dl   = _fmt_num(m["downloads"])
        lk   = _fmt_num(m["likes"])
        fmt  = m.get("format", "-")          # no truncation — logic now returns short strings
        task = m["task"][:20]
        print(f"{i:>4}  {src}  {mid:<44} {dl:>7}  {lk:>6}  {fmt:<14}  {task}")
    print()


# ─── downloader ───────────────────────────────────────────────────────────────

def _cmd_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _hfd_path() -> Optional[Path]:
    p = SCRIPT_DIR / "hfd.sh"
    return p if p.exists() else None


def get_downloader() -> str:
    if _hfd_path():
        return "hfd"
    if _cmd_exists("huggingface-cli"):
        return "huggingface-cli"
    if _cmd_exists("hf"):
        return "hf"
    if _cmd_exists("aria2c") or _cmd_exists("wget"):
        return "aria2c-fallback"
    return "none"


def setup_tools(verbose: bool = True) -> str:
    dl = get_downloader()
    if dl != "none":
        return dl

    hfd = SCRIPT_DIR / "hfd.sh"
    if verbose:
        print("  正在下载 hfd.sh ...")
    try:
        urlretrieve(HFD_URL, hfd)
        hfd.chmod(0o755)
        if verbose:
            print("  hfd.sh 下载完成")
        return "hfd"
    except Exception as e:
        if verbose:
            print(f"  hfd.sh 下载失败: {e}")

    if verbose:
        print("  正在安装 huggingface_hub ...")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-U", "huggingface_hub"],
        capture_output=True,
    )
    if r.returncode == 0 and (_cmd_exists("huggingface-cli") or _cmd_exists("hf")):
        if verbose:
            print("  huggingface_hub 安装完成")
        return get_downloader()

    if verbose:
        print("  未找到可用下载器，请手动: pip install huggingface_hub  或  brew install aria2")
    return "none"


# ─── download ─────────────────────────────────────────────────────────────────

def download_model(
    model_id: str,
    download_dir: Path,
    source: str = "huggingface",
    token: Optional[str] = None,
    threads: int = 8,
    jobs: int = 5,
    include: Optional[str] = None,
    exclude: Optional[str] = None,
) -> bool:
    download_dir.mkdir(parents=True, exist_ok=True)
    model_name = model_id.split("/")[-1]
    local_dir  = download_dir / model_name

    env = os.environ.copy()
    env["HF_ENDPOINT"] = HF_MIRROR

    dl = setup_tools(verbose=False)
    if dl == "none":
        print("错误：未找到可用下载器。请运行:  python3 mdt.py setup")
        return False

    print(f"\n  下载器: {dl}")
    print(f"  镜像站: {HF_MIRROR}")
    print(f"  保存至: {local_dir}\n")

    if source == "modelscope":
        return _download_modelscope(model_id, local_dir)

    # Always exclude macOS metadata files — they 403 on mirrors and are useless for models
    DEFAULT_EXCLUDE = [".DS_Store", "__MACOSX"]
    effective_exclude = " ".join(DEFAULT_EXCLUDE + ([exclude] if exclude else []))

    if dl == "hfd":
        hfd = str(_hfd_path())
        cmd = [hfd, model_id,
               "--tool", "aria2c" if _cmd_exists("aria2c") else "wget",
               "-x", str(threads), "-j", str(jobs),
               "--local-dir", str(local_dir),
               "--exclude", effective_exclude]
        if token:   cmd += ["--hf_token", token]
        if include: cmd += ["--include", include]

    elif dl in ("huggingface-cli", "hf"):
        cmd = [dl, "download", "--resume-download",
               "--local-dir", str(local_dir),
               "--local-dir-use-symlinks", "False",
               model_id]
        if token: cmd += ["--token", token]
    else:
        print("  请先运行: python3 mdt.py setup")
        return False

    print(f"  命令: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, env=env)
    return result.returncode == 0


def _download_modelscope(model_id: str, local_dir: Path) -> bool:
    if _cmd_exists("git"):
        url = f"https://www.modelscope.cn/{model_id}.git"
        cmd = ["git", "clone", "--depth=1", url, str(local_dir)]
        print(f"  命令: {' '.join(cmd)}\n")
        return subprocess.run(cmd).returncode == 0
    try:
        from modelscope import snapshot_download
        snapshot_download(model_id, local_dir=str(local_dir))
        return True
    except ImportError:
        print("  请安装 modelscope: pip install modelscope")
        return False


# ─── interactive flow ─────────────────────────────────────────────────────────

def interactive_search(
    query: str,
    download_dir: Path,
    limit: int = 20,
    source: str = "huggingface",
    platform: str = "all",
    token: Optional[str] = None,
):
    while True:
        models = search_models(query, limit, source, platform)

        if not models:
            hf_filter = PLATFORM_FILTERS.get(platform)
            if hf_filter:
                print(f"  未找到 {PLATFORM_LABELS.get(platform)} 模型")
                print(f"  提示: 可用 --platform all 查看全平台结果")
            else:
                print("  未找到相关模型")
            again = input("\n重新搜索 (输入关键词) 或按 Enter 退出: ").strip()
            if not again:
                return
            query = again
            continue

        display_models(models, platform)
        print(f"共 {len(models)} 个结果  |  序号下载  |  's <关键词>' 重搜  |  'q' 退出")

        while True:
            try:
                raw = input("\n> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n已退出")
                return

            if raw.lower() == "q":
                return

            if raw.lower().startswith("s "):
                query = raw[2:].strip()
                if query:
                    break
                continue

            try:
                idx = int(raw) - 1
            except ValueError:
                print("请输入有效数字")
                continue

            if not (0 <= idx < len(models)):
                print(f"请输入 1 ~ {len(models)}")
                continue

            m   = models[idx]
            mid = m["id"]
            src = m["source"]
            dest = download_dir / mid.split("/")[-1]

            print(f"\n  模型: {mid}")
            print(f"  格式: {m.get('format', '-')}  |  任务: {m['task']}")
            print(f"  下载量: {m['downloads']:,}  ♥ {m['likes']:,}")

            # Fetch size before asking user to confirm
            if src == "huggingface":
                print("  正在获取模型大小...", end="\r")
                size = fetch_model_size(mid)
                size_str = _fmt_size(size)
                print(f"  大小: {size_str}            ")  # spaces overwrite the "获取中" line
            else:
                size_str = "未知（ModelScope）"
                print(f"  大小: {size_str}")

            try:
                confirm = input(f"\n  确认下载到 {dest}? [y/N] ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print()
                return

            if confirm != "y":
                print("  已取消")
                continue

            success = download_model(mid, download_dir, source=src, token=token)
            if success:
                print(f"\n  ✓ 下载完成 → {dest}")
            else:
                print("\n  ✗ 下载失败，请检查网络或使用 --token 参数")
            return


# ─── CLI commands ─────────────────────────────────────────────────────────────

def cmd_setup(args):
    global HF_MIRROR
    print("=== 初始化模型下载工具 ===\n")

    hfd = SCRIPT_DIR / "hfd.sh"
    if not hfd.exists():
        print("下载 hfd.sh ...")
        try:
            urlretrieve(HFD_URL, hfd)
            hfd.chmod(0o755)
            print("  ✓ hfd.sh 已就绪")
        except Exception as e:
            print(f"  ✗ hfd.sh 下载失败: {e}")
    else:
        print("  ✓ hfd.sh 已存在")

    if not (_cmd_exists("huggingface-cli") or _cmd_exists("hf")):
        print("安装 huggingface_hub ...")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "huggingface_hub"])
        print("  ✓ 安装完成" if r.returncode == 0 else "  ✗ 安装失败，请手动: pip install huggingface_hub")
    else:
        print("  ✓ huggingface-cli 已就绪")

    if _cmd_exists("aria2c"):
        print("  ✓ aria2c 已就绪")
    else:
        print("  ⚠ aria2c 未安装 (推荐安装以提升下载速度)")
        print("      Mac: brew install aria2    Ubuntu: sudo apt-get install aria2")

    dl_dir = Path(args.dir)
    dl_dir.mkdir(parents=True, exist_ok=True)
    print(f"  ✓ 下载目录: {dl_dir}")

    # Write/show config
    cfg = load_config()
    cfg["download_dir"] = str(dl_dir)
    cfg["mirror"] = HF_MIRROR
    if not CONFIG_PATH.exists():
        save_config(cfg)
        print(f"\n已生成配置文件: {CONFIG_PATH}")
        print("可直接编辑该文件修改默认值，无需每次传参\n")
    else:
        print(f"\n当前配置文件: {CONFIG_PATH}")
        _print_config(cfg)

    print(f"\n当前下载器: {get_downloader()}")
    print("\n使用示例:")
    print("  python3 mdt.py search 'OCR'")
    print("  python3 mdt.py search 'llama 7b' --platform all")
    print("  python3 mdt.py download Qwen/Qwen2-7B-Instruct")


def cmd_config(args):
    """Show or edit config."""
    cfg = load_config()
    if args.key and args.value:
        # validate known keys
        if args.key not in DEFAULT_CONFIG:
            known = ", ".join(DEFAULT_CONFIG.keys())
            print(f"未知配置项: {args.key}  (可用: {known})")
            return
        # cast to original type
        orig = DEFAULT_CONFIG[args.key]
        try:
            cfg[args.key] = type(orig)(args.value) if not isinstance(orig, str) else args.value
        except (ValueError, TypeError):
            cfg[args.key] = args.value
        save_config(cfg)
    else:
        print(f"\n配置文件: {CONFIG_PATH}\n")
        _print_config(cfg)
        print("\n修改方法:")
        print("  python3 mdt.py config platform all        # 设置单项")
        print(f"  编辑文件: {CONFIG_PATH}")


def _print_config(cfg: Dict) -> None:
    platform_opts = " | ".join(PLATFORM_FILTERS.keys())
    notes = {
        "platform": f"({platform_opts})",
        "source":   "(huggingface | modelscope | all)",
    }
    for k, v in cfg.items():
        note = notes.get(k, "")
        print(f"  {k:<14} = {v!r:<30} {note}")


def cmd_search(args):
    query = args.query or input("请输入搜索关键词: ").strip()
    if not query:
        print("搜索关键词不能为空")
        return
    interactive_search(
        query=query,
        download_dir=Path(args.dir),
        limit=args.limit,
        source=args.source,
        platform=args.platform,
        token=args.token or CFG.get("token") or None,
    )


def cmd_download(args):
    if not args.model_id:
        print("请提供模型 ID，例如: python3 mdt.py download Qwen/Qwen2-7B-Instruct")
        return
    success = download_model(
        model_id=args.model_id,
        download_dir=Path(args.dir),
        source=args.source,
        token=args.token or CFG.get("token") or None,
        threads=args.threads,
        jobs=args.jobs,
        include=args.include,
        exclude=args.exclude,
    )
    if success:
        name = args.model_id.split("/")[-1]
        print(f"\n✓ 下载完成 → {Path(args.dir) / name}")


def cmd_list(args):
    dl_dir = Path(args.dir)
    if not dl_dir.exists():
        print(f"目录不存在: {dl_dir}")
        return
    items = sorted(dl_dir.iterdir())
    if not items:
        print("暂无已下载模型")
        return
    print(f"\n已下载模型 ({dl_dir}):\n")
    for p in items:
        if p.is_dir():
            try:
                size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                size_str = f"{size/1024**3:.1f} GB" if size > 1024**3 else f"{size/1024**2:.0f} MB"
            except Exception:
                size_str = "?"
            print(f"  {p.name:<40} {size_str:>8}")


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    global HF_MIRROR

    parser = argparse.ArgumentParser(
        prog="mdt",
        description="mdt — AI 模型搜索与下载工具 (默认适配 Mac M 芯片)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
平台选项 (--platform):
  mac       MLX 格式，Apple Silicon 原生加速 (默认)
  mac-gguf  GGUF 格式，llama.cpp + Metal 加速
  gguf      GGUF 跨平台格式
  windows   Windows (无格式过滤)
  linux     Linux  (无格式过滤)
  all       全平台，不过滤

示例:
  python3 mdt.py setup                              # 初始化 + 生成 config.json
  python3 mdt.py config                             # 查看当前配置
  python3 mdt.py config platform all               # 修改默认平台
  python3 mdt.py search "OCR"                       # 搜索 Mac MLX 模型 (默认)
  python3 mdt.py search "llama" --platform all      # 搜索全平台
  python3 mdt.py search "llama" --platform mac-gguf # 搜索 GGUF 模型
  python3 mdt.py download mlx-community/Qwen3-8B-4bit-mlx  # 直接下载
  python3 mdt.py list                               # 查看已下载模型

配置文件: {CONFIG_PATH}
        """,
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dir", default=str(Path(CFG["download_dir"]).expanduser()),
                        metavar="PATH", help=f"下载目录 (默认: {CFG['download_dir']})")
    common.add_argument("--mirror", default=CFG["mirror"], metavar="URL",
                        help="HuggingFace 镜像站")

    platform_choices = list(PLATFORM_FILTERS.keys())

    sub = parser.add_subparsers(dest="cmd", metavar="命令")

    # setup
    sub.add_parser("setup", parents=[common], help="初始化工具链并生成 config.json")

    # config
    p_cfg = sub.add_parser("config", help="查看或修改配置")
    p_cfg.add_argument("key",   nargs="?", help="配置项名称")
    p_cfg.add_argument("value", nargs="?", help="配置项值")

    # search
    p_search = sub.add_parser("search", parents=[common], help="搜索并交互式下载模型")
    p_search.add_argument("query", nargs="?", metavar="关键词")
    p_search.add_argument("-n", "--limit", type=int, default=CFG["limit"], metavar="N",
                          help=f"显示条数 (默认: {CFG['limit']})")
    p_search.add_argument("--source", default=CFG["source"],
                          choices=["huggingface", "modelscope", "all"])
    p_search.add_argument("--platform", default=CFG["platform"],
                          choices=platform_choices,
                          help=f"目标平台 (默认: {CFG['platform']})")
    p_search.add_argument("--token", metavar="TOKEN", default="")

    # download
    p_dl = sub.add_parser("download", parents=[common], help="直接下载指定模型")
    p_dl.add_argument("model_id", nargs="?", metavar="模型ID")
    p_dl.add_argument("--source", default=CFG["source"],
                      choices=["huggingface", "modelscope"])
    p_dl.add_argument("--token",   metavar="TOKEN", default="")
    p_dl.add_argument("-x", "--threads", type=int, default=CFG["threads"])
    p_dl.add_argument("-j", "--jobs",    type=int, default=CFG["jobs"])
    p_dl.add_argument("--include", metavar="PATTERN")
    p_dl.add_argument("--exclude", metavar="PATTERN")

    # list
    sub.add_parser("list", parents=[common], help="列出已下载模型")

    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()
    HF_MIRROR = getattr(args, "mirror", CFG["mirror"])
    os.environ["HF_ENDPOINT"] = HF_MIRROR

    dispatch = {
        "setup":    cmd_setup,
        "config":   cmd_config,
        "search":   cmd_search,
        "download": cmd_download,
        "list":     cmd_list,
    }
    fn = dispatch.get(args.cmd)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
