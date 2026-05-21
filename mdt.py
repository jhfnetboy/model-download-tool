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
from urllib.request import urlopen, urlretrieve, Request
from urllib.parse import urlencode, quote
from urllib.error import URLError, HTTPError

DEFAULT_DOWNLOAD_DIR = Path.home() / ".omlx" / "models"
HF_MIRROR = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
HF_API = "https://huggingface.co"
MODELSCOPE_API = "https://modelscope.cn/api/v1"
HFD_URL = "https://hf-mirror.com/hfd/hfd.sh"
SCRIPT_DIR = Path(__file__).parent


# ─── search ──────────────────────────────────────────────────────────────────

def _http_get(url: str, timeout: int = 15) -> Optional[dict]:
    try:
        req = Request(url, headers={"User-Agent": "mdt/1.0"})
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except (URLError, HTTPError, json.JSONDecodeError) as e:
        print(f"  请求失败: {e}")
        return None


def search_huggingface(query: str, limit: int = 20) -> List[Dict]:
    params = urlencode({"search": query, "limit": limit, "sort": "downloads", "direction": -1})
    data = _http_get(f"{HF_API}/api/models?{params}")
    if not data:
        return []
    results = []
    for m in data:
        results.append({
            "source": "huggingface",
            "id": m.get("id", ""),
            "downloads": m.get("downloads", 0),
            "likes": m.get("likes", 0),
            "updated": (m.get("lastModified") or "")[:10],
            "task": m.get("pipeline_tag") or "-",
            "tags": m.get("tags", []),
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
            "source": "modelscope",
            "id": m.get("Path", ""),
            "downloads": m.get("Downloads", 0),
            "likes": m.get("Likes", 0),
            "updated": (m.get("UpdatedAt") or "")[:10],
            "task": m.get("Tasks", [{"Name": "-"}])[0].get("Name", "-") if m.get("Tasks") else "-",
            "tags": [],
        })
    return results


def search_models(query: str, limit: int = 20, source: str = "huggingface") -> List[Dict]:
    print(f"  正在搜索「{query}」(来源: {source})...")
    if source == "modelscope":
        return search_modelscope(query, limit)
    if source == "all":
        hf = search_huggingface(query, limit // 2 + 1)
        ms = search_modelscope(query, limit // 2 + 1)
        return hf + ms
    return search_huggingface(query, limit)


# ─── display ─────────────────────────────────────────────────────────────────

def _fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def display_models(models: List[Dict]) -> None:
    src_colors = {"huggingface": "\033[33m HF\033[0m", "modelscope": "\033[36m MS\033[0m"}
    print(f"\n{'#':>3}  {'来源':>4}  {'模型 ID':<48} {'下载':>7}  {'♥':>5}  {'任务':<18}  {'更新'}")
    print("─" * 100)
    for i, m in enumerate(models, 1):
        src = src_colors.get(m["source"], m["source"])
        mid = m["id"][:47]
        dl = _fmt_num(m["downloads"])
        lk = _fmt_num(m["likes"])
        task = m["task"][:17]
        print(f"{i:>3}  {src}  {mid:<48} {dl:>7}  {lk:>5}  {task:<18}  {m['updated']}")
    print()


# ─── downloader detection ─────────────────────────────────────────────────────

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
    """Ensure at least one downloader is available. Returns downloader name."""
    dl = get_downloader()
    if dl != "none":
        return dl

    # Try to download hfd.sh
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

    # Try pip install huggingface_hub
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
        print("  未找到可用下载器，请手动安装: pip install huggingface_hub  或  brew install aria2")
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
    local_dir = download_dir / model_name

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

    if dl == "hfd":
        hfd = str(_hfd_path())
        cmd = [hfd, model_id, "--tool", "aria2c" if _cmd_exists("aria2c") else "wget",
               "-x", str(threads), "-j", str(jobs), "--local-dir", str(local_dir)]
        if token:
            cmd += ["--hf_token", token]
        if include:
            cmd += ["--include", include]
        if exclude:
            cmd += ["--exclude", exclude]

    elif dl in ("huggingface-cli", "hf"):
        cmd = [dl, "download", "--resume-download",
               "--local-dir", str(local_dir),
               "--local-dir-use-symlinks", "False",
               model_id]
        if token:
            cmd += ["--token", token]
    else:
        print("  请先运行: python3 mdt.py setup")
        return False

    print(f"  命令: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, env=env)
    return result.returncode == 0


def _download_modelscope(model_id: str, local_dir: Path) -> bool:
    """Download from ModelScope using git or modelscope sdk."""
    if _cmd_exists("git"):
        url = f"https://www.modelscope.cn/{model_id}.git"
        cmd = ["git", "clone", "--depth=1", url, str(local_dir)]
        print(f"  命令: {' '.join(cmd)}\n")
        r = subprocess.run(cmd)
        return r.returncode == 0
    # Fallback: try modelscope Python SDK
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
    token: Optional[str] = None,
):
    while True:
        models = search_models(query, limit, source)

        if not models:
            print("  未找到相关模型")
            again = input("\n重新搜索 (输入关键词) 或按 Enter 退出: ").strip()
            if not again:
                return
            query = again
            continue

        display_models(models)
        print(f"共 {len(models)} 个结果  |  输入序号下载  |  's <关键词>' 重搜  |  'q' 退出")

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
                    break  # re-search
                continue

            try:
                idx = int(raw) - 1
            except ValueError:
                print("请输入有效数字")
                continue

            if not (0 <= idx < len(models)):
                print(f"请输入 1 ~ {len(models)}")
                continue

            m = models[idx]
            model_id = m["id"]
            src = m["source"]
            local_name = model_id.split("/")[-1]
            dest = download_dir / local_name

            print(f"\n  模型: {model_id}")
            print(f"  来源: {src}")
            print(f"  下载: {m['downloads']:,}  ♥ {m['likes']:,}")
            print(f"  任务: {m['task']}")
            try:
                confirm = input(f"\n  确认下载到 {dest}? [y/N] ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print()
                return

            if confirm != "y":
                print("  已取消")
                continue

            success = download_model(model_id, download_dir, source=src, token=token)
            if success:
                print(f"\n  ✓ 下载完成 → {dest}")
            else:
                print("\n  ✗ 下载失败，请检查网络连接或使用 --token 参数")
            return


# ─── CLI ─────────────────────────────────────────────────────────────────────

def cmd_setup(args):
    print("=== 初始化模型下载工具 ===\n")

    # hfd.sh
    hfd = SCRIPT_DIR / "hfd.sh"
    if not hfd.exists():
        print("下载 hfd.sh (hf-mirror.com 多线程下载脚本)...")
        try:
            urlretrieve(HFD_URL, hfd)
            hfd.chmod(0o755)
            print("  ✓ hfd.sh 已就绪")
        except Exception as e:
            print(f"  ✗ hfd.sh 下载失败: {e}")
    else:
        print("  ✓ hfd.sh 已存在")

    # huggingface_hub
    if not (_cmd_exists("huggingface-cli") or _cmd_exists("hf")):
        print("安装 huggingface_hub ...")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "huggingface_hub"])
        if r.returncode == 0:
            print("  ✓ huggingface_hub 已安装")
        else:
            print("  ✗ 安装失败，请手动运行: pip install huggingface_hub")
    else:
        print("  ✓ huggingface-cli 已就绪")

    # aria2c
    if _cmd_exists("aria2c"):
        print("  ✓ aria2c 已就绪")
    else:
        print("  ⚠ aria2c 未安装 (建议安装以获得最佳速度)")
        print("      Mac: brew install aria2")
        print("      Ubuntu: sudo apt-get install aria2")

    # download dir
    dl_dir = Path(args.dir)
    dl_dir.mkdir(parents=True, exist_ok=True)
    print(f"  ✓ 下载目录: {dl_dir}")

    print(f"\n当前下载器: {get_downloader()}")
    print("\n建议将以下内容加入 ~/.zshrc:")
    print("  export HF_ENDPOINT=https://hf-mirror.com")
    print("\n初始化完成！使用示例:")
    print("  python3 mdt.py search 'OCR'")
    print("  python3 mdt.py search 'llama 7b' --source all")
    print("  python3 mdt.py download Qwen/Qwen2-7B-Instruct")


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
        token=args.token,
    )


def cmd_download(args):
    if not args.model_id:
        print("请提供模型 ID，例如: python3 mdt.py download Qwen/Qwen2-7B-Instruct")
        return
    success = download_model(
        model_id=args.model_id,
        download_dir=Path(args.dir),
        source=args.source,
        token=args.token,
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
    models = sorted(dl_dir.iterdir())
    if not models:
        print("暂无已下载模型")
        return
    print(f"\n已下载模型 ({dl_dir}):\n")
    for p in models:
        if p.is_dir():
            try:
                size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                size_str = f"{size/1024**3:.1f} GB" if size > 1024**3 else f"{size/1024**2:.0f} MB"
            except Exception:
                size_str = "?"
            print(f"  {p.name:<40} {size_str:>8}")


def main():
    global HF_MIRROR
    parser = argparse.ArgumentParser(
        prog="mdt",
        description="mdt — AI 模型搜索与下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 mdt.py setup                              # 初始化工具链
  python3 mdt.py search "OCR"                       # 搜索 OCR 相关模型
  python3 mdt.py search "llama 7b" --source all     # 同时搜索 HF + ModelScope
  python3 mdt.py search "stable diffusion" -n 30    # 显示 30 条结果
  python3 mdt.py download Qwen/Qwen2-7B-Instruct    # 直接下载指定模型
  python3 mdt.py download meta-llama/Llama-2-7b --token hf_xxx  # 带 token 下载
  python3 mdt.py list                               # 查看已下载模型
        """,
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dir", default=str(DEFAULT_DOWNLOAD_DIR),
                        metavar="PATH", help=f"下载目录 (默认: {DEFAULT_DOWNLOAD_DIR})")
    common.add_argument("--mirror", default=HF_MIRROR, metavar="URL",
                        help="HuggingFace 镜像站 (默认: hf-mirror.com)")

    sub = parser.add_subparsers(dest="cmd", metavar="命令")

    # setup
    p_setup = sub.add_parser("setup", parents=[common], help="初始化/检查工具链")

    # search
    p_search = sub.add_parser("search", parents=[common], help="搜索并交互式下载模型")
    p_search.add_argument("query", nargs="?", metavar="关键词", help="搜索关键词")
    p_search.add_argument("-n", "--limit", type=int, default=20, metavar="N",
                          help="最多显示 N 条结果 (默认: 20)")
    p_search.add_argument("--source", default="huggingface",
                          choices=["huggingface", "modelscope", "all"],
                          help="搜索来源 (默认: huggingface)")
    p_search.add_argument("--token", metavar="TOKEN", help="HuggingFace Access Token")

    # download
    p_dl = sub.add_parser("download", parents=[common], help="直接下载指定模型")
    p_dl.add_argument("model_id", nargs="?", metavar="模型ID",
                      help="模型 ID，如 Qwen/Qwen2-7B-Instruct")
    p_dl.add_argument("--source", default="huggingface",
                      choices=["huggingface", "modelscope"],
                      help="下载来源 (默认: huggingface)")
    p_dl.add_argument("--token", metavar="TOKEN", help="HuggingFace Access Token")
    p_dl.add_argument("-x", "--threads", type=int, default=8, help="单文件线程数 (默认: 8)")
    p_dl.add_argument("-j", "--jobs", type=int, default=5, help="并行文件数 (默认: 5)")
    p_dl.add_argument("--include", metavar="PATTERN", help="只下载匹配的文件 (如 '*.safetensors')")
    p_dl.add_argument("--exclude", metavar="PATTERN", help="排除匹配的文件 (如 '*.bin')")

    # list
    p_list = sub.add_parser("list", parents=[common], help="列出已下载模型")

    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()

    # Apply mirror
    HF_MIRROR = getattr(args, "mirror", HF_MIRROR)
    os.environ["HF_ENDPOINT"] = HF_MIRROR

    dispatch = {"setup": cmd_setup, "search": cmd_search, "download": cmd_download, "list": cmd_list}
    fn = dispatch.get(args.cmd)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
