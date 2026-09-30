#!/usr/bin/env python3
"""oMLX Status & Performance Query Tool

查询 oMLX 内存中当前加载的模型及各项性能指标（显存占用、TPS 吞吐、缓存效率、请求统计等）。
"""

import os
import sys
import time
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, List


def get_api_key(cli_key: Optional[str] = None) -> str:
    """自动获取 API Key：命令行参数 > 环境变量 > ~/.omlx/settings.json"""
    if cli_key:
        return cli_key
    if "OMLX_API_KEY" in os.environ:
        return os.environ["OMLX_API_KEY"]

    settings_path = Path.home() / ".omlx" / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                key = data.get("auth", {}).get("api_key")
                if key:
                    return str(key)
        except Exception:
            pass
    return ""


def request_json(url: str, api_key: str = "", timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "omlx-status/1.0")
    req.add_header("Accept", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise RuntimeError(f"认证失败 (401 Unauthorized)。请检查 API Key（可通过 OMLX_API_KEY 或 --key 提供）。")
        raise RuntimeError(f"HTTP 请求失败 ({e.code} {e.reason})：{url}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接到 oMLX 服务 ({url})：{e.reason}。请确认 oMLX 是否正在运行。")
    except Exception as e:
        raise RuntimeError(f"请求失败 ({url})：{e}")


def format_bytes(num_bytes: Optional[int]) -> str:
    if num_bytes is None or num_bytes < 0:
        return "N/A"
    if num_bytes == 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} PB"


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "N/A"
    s = int(seconds)
    days, rem = divmod(s, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0 or days > 0:
        parts.append(f"{hours}小时")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}分")
    parts.append(f"{secs}秒")
    return "".join(parts)


def format_time_ago(ts: Optional[float]) -> str:
    if not ts:
        return "未记录"
    delta = time.time() - ts
    if delta < 0:
        return "刚刚"
    if delta < 60:
        return f"{int(delta)} 秒前"
    if delta < 3600:
        return f"{int(delta // 60)} 分钟前"
    if delta < 86400:
        return f"{delta / 3600:.1f} 小时前"
    return f"{delta / 86400:.1f} 天前"


def fetch_omlx_data(base_url: str, api_key: str) -> Dict[str, Any]:
    base = base_url.rstrip("/")
    status_data = request_json(f"{base}/api/status", api_key) or {}
    models_status_data = request_json(f"{base}/v1/models/status", api_key) or {}

    raw_models = models_status_data.get("models", {})
    all_models: List[Dict[str, Any]] = []

    if isinstance(raw_models, dict):
        all_models = list(raw_models.values())
    elif isinstance(raw_models, list):
        all_models = raw_models

    loaded_models: List[Dict[str, Any]] = []
    unloaded_models: List[Dict[str, Any]] = []

    for m in all_models:
        if not isinstance(m, dict):
            continue
        is_loaded = m.get("loaded", False)
        if is_loaded:
            loaded_models.append(m)
        else:
            unloaded_models.append(m)

    # 排序：常驻/加载的模型按显存占用降序排列
    loaded_models.sort(
        key=lambda x: (
            x.get("resident_estimated_size")
            or x.get("actual_size")
            or x.get("estimated_size")
            or 0
        ),
        reverse=True,
    )

    return {
        "status": status_data,
        "models_status": models_status_data,
        "loaded_models": loaded_models,
        "unloaded_models": unloaded_models,
    }


def render_terminal_dashboard(data: Dict[str, Any], base_url: str) -> None:
    status = data["status"]
    models_status = data["models_status"]
    loaded = data["loaded_models"]
    unloaded = data["unloaded_models"]

    # 颜色 ANSI 码
    C_RESET = "\033[0m"
    C_BOLD = "\033[1m"
    C_GREEN = "\033[32m"
    C_CYAN = "\033[36m"
    C_YELLOW = "\033[33m"
    C_MAGENTA = "\033[35m"
    C_DIM = "\033[2m"

    version = status.get("version", "未知")
    uptime = format_duration(status.get("uptime_seconds"))
    server_status = status.get("status", "未知")
    status_color = C_GREEN if server_status.lower() in ("ok", "healthy") else C_YELLOW

    print(f"\n{C_BOLD}{'=' * 68}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}  oMLX 服务状态与性能指标看板{C_RESET}  {C_DIM}({base_url}){C_RESET}")
    print(f"{C_BOLD}{'=' * 68}{C_RESET}")

    # 1. 基础状态
    print(f"  服务状态: {status_color}{server_status.upper()}{C_RESET}  |  版本: {C_BOLD}{version}{C_RESET}  |  运行时间: {uptime}")

    # 2. 显存/内存信息
    mem_used = status.get("model_memory_used")
    mem_max = status.get("model_memory_max")
    mem_used_fmt = status.get("model_memory_used_formatted") or format_bytes(mem_used)
    mem_max_fmt = status.get("model_memory_max_formatted") or format_bytes(mem_max)

    pct_str = ""
    if mem_used and mem_max and mem_max > 0:
        pct = (mem_used / mem_max) * 100
        pct_color = C_GREEN if pct < 70 else (C_YELLOW if pct < 85 else C_MAGENTA)
        pct_str = f" ({pct_color}{pct:.1f}%{C_RESET})"

    print(f"  模型显存占用: {C_BOLD}{mem_used_fmt}{C_RESET} / 配额上限: {mem_max_fmt}{pct_str}")
    print(f"  模型统计: 共发现 {len(loaded) + len(unloaded)} 个模型，当前内存已加载: {C_BOLD}{C_GREEN}{len(loaded)}{C_RESET} 个")

    # 3. 内存中已加载模型列表
    print(f"\n{C_BOLD}─── 内存中已加载的模型 ({len(loaded)}) ─────────────────────────────────{C_RESET}")
    if not loaded:
        print(f"  {C_DIM}(当前内存中未常驻任何模型){C_RESET}")
    else:
        for idx, m in enumerate(loaded, 1):
            m_id = m.get("id", "未知ID")
            engine = m.get("engine_type", "batched")
            m_type = m.get("model_type", "llm")
            size_bytes = m.get("actual_size") or m.get("resident_estimated_size") or m.get("estimated_size")
            size_fmt = format_bytes(size_bytes)
            ctx_len = m.get("model_context_length") or m.get("max_context_window")
            ctx_fmt = f"{ctx_len:,} tok" if ctx_len else "默认"
            pinned = " [Pinned 常驻]" if m.get("pinned") else ""
            last_act = format_time_ago(m.get("last_access"))

            print(f"  {C_BOLD}{idx}. {C_GREEN}{m_id}{C_RESET}{C_YELLOW}{pinned}{C_RESET}")
            print(f"     • 显存大小: {C_BOLD}{size_fmt}{C_RESET}  |  类型: {m_type} ({engine})  |  上下文窗口: {ctx_fmt}")
            print(f"     • 最近访问: {last_act}  |  路径: {C_DIM}{m.get('model_path', '-')}{C_RESET}")

    # 4. 性能与吞吐指标
    avg_gen_tps = status.get("avg_generation_tps")
    avg_pref_tps = status.get("avg_prefill_tps")
    tps_gen_str = f"{avg_gen_tps:.1f} tok/s" if avg_gen_tps is not None else "N/A"
    tps_pref_str = f"{avg_pref_tps:.1f} tok/s" if avg_pref_tps is not None else "N/A"

    print(f"\n{C_BOLD}─── 推理性能吞吐 (实时/历史平均) ───────────────────────{C_RESET}")
    print(f"  平均生成速度 (Decode): {C_BOLD}{C_CYAN}{tps_gen_str:>10}{C_RESET}   (生成阶段逐字吞吐)")
    print(f"  平均首字速度 (Prefill): {C_BOLD}{C_CYAN}{tps_pref_str:>9}{C_RESET}   (提示词预填充吞吐)")

    # 5. Token 与缓存效率
    p_tokens = status.get("total_prompt_tokens", 0)
    c_tokens = status.get("total_completion_tokens", 0)
    cached_tokens = status.get("total_cached_tokens", 0)
    cache_eff = status.get("cache_efficiency")
    cache_eff_str = f"{cache_eff:.1f}%" if cache_eff is not None else "N/A"

    print(f"\n{C_BOLD}─── Token 与前缀缓存统计 ───────────────────────────────{C_RESET}")
    print(f"  Prompt Tokens:     {p_tokens:,}")
    print(f"  Completion Tokens: {c_tokens:,}")
    print(f"  Cached Tokens:     {cached_tokens:,}  (前缀命中缓存)")
    print(f"  前缀缓存效率:      {C_BOLD}{C_GREEN}{cache_eff_str}{C_RESET}")

    # 6. 请求统计
    req_total = status.get("total_requests", 0)
    req_active = status.get("active_requests", 0)
    req_waiting = status.get("waiting_requests", 0)

    print(f"\n{C_BOLD}─── 请求队列 ───────────────────────────────────────────{C_RESET}")
    print(f"  累计请求: {req_total} 次  |  当前活跃: {C_BOLD}{req_active}{C_RESET}  |  等待队列: {req_waiting}")

    # 7. 硬件加速特性 (Custom Kernels / ANE)
    kernels = status.get("custom_kernels", {})
    avail_kernels = [k for k, v in kernels.items() if isinstance(v, dict) and v.get("available")]
    ane = status.get("ane_prefill", {})
    ane_ok = ane.get("patch_available", False)

    print(f"\n{C_BOLD}─── 加速扩展与硬件特性 ─────────────────────────────────{C_RESET}")
    print(f"  Apple Neural Engine (ANE) Prefill: {'已就绪 (可用)' if ane_ok else '未启用'}")
    if avail_kernels:
        print(f"  已就绪自定义 MLX 算子内核: {', '.join(avail_kernels)}")
    else:
        print(f"  已就绪自定义 MLX 算子内核: 无")

    print(f"{C_BOLD}{'=' * 68}{C_RESET}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="查询 oMLX 内存中加载的模型及性能指标",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("OMLX_BASE_URL", "http://127.0.0.1:8088"),
        help="oMLX 服务基础 URL（默认：http://127.0.0.1:8088）",
    )
    parser.add_argument(
        "--key",
        default=None,
        help="oMLX API Key（默认优先从环境变量 OMLX_API_KEY 或 ~/.omlx/settings.json 自动提取）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出原始完整状态数据",
    )
    parser.add_argument(
        "-w",
        "--watch",
        type=float,
        nargs="?",
        const=2.0,
        default=None,
        metavar="SECONDS",
        help="持续刷新看板（可选间隔秒数，默认 2 秒）",
    )

    args = parser.parse_args()
    api_key = get_api_key(args.key)

    if args.watch is not None:
        interval = max(0.5, args.watch)
        try:
            while True:
                # 清屏
                print("\033[2J\033[H", end="")
                data = fetch_omlx_data(args.url, api_key)
                if args.json:
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                else:
                    render_terminal_dashboard(data, args.url)
                print(f"\033[2m按 Ctrl+C 退出监控 (刷新间隔: {interval}s)...\033[0m", flush=True)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n已退出监控。")
            sys.exit(0)
    else:
        data = fetch_omlx_data(args.url, api_key)
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            render_terminal_dashboard(data, args.url)


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"\033[31m[错误] {err}\033[0m", file=sys.stderr)
        sys.exit(1)
