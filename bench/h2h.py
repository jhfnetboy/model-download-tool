#!/usr/bin/env python
"""同一模型、两个引擎的对照测试。所有请求走 OpenAI 兼容接口，客户端完全相同。

用法: h2h.py <label> <base_url> <model_id> [api_key]
输出: results/<label>.json + 终端摘要
"""
import json, sys, time, threading, statistics, subprocess, urllib.request, pathlib, os, uuid

LABEL, BASE, MODEL = sys.argv[1], sys.argv[2].rstrip("/"), sys.argv[3]
KEY = sys.argv[4] if len(sys.argv) > 4 else ""
HERE = pathlib.Path(__file__).parent
LONG = (HERE / "long_prompt.txt").read_text()
NOTHINK = {"enable_thinking": False}

SHORT = ["用一句话解释什么是 MoE 架构。", "帮我写一封 50 字的邮件，婉拒一个会议邀约。",
         "把 [3,1,4,1,5,9,2,6] 用 Python 冒泡排序，只给代码。", "列出四象限时间管理法的四个象限名称。",
         "什么是投机解码？一句话。", "把「明天下午三点和老王开会」转成 JSON：{date,time,person}。",
         "写一个 SQL 查询：users 表里注册超过 30 天的用户数。", "一句话说明统一内存架构对本地推理的好处。"]

TOOL = """你有以下工具可用：
- query_db(sql: string) — 在本地 SQLite 上执行只读 SQL
- send_email(to: string, subject: string, body: string) — 发邮件
- search_web(query: string) — 搜索网页

用户说：「查一下我这个月消费超过 500 元的记录，汇总成表格发到我邮箱 jason@idoris.ai」

请按顺序输出你要调用的工具及参数，用 JSON 数组表示，不要执行，只给调用计划。"""

TASKS = {
 "code": "给下面的 Python 函数加上重试逻辑：最多重试 3 次，指数退避(1s/2s/4s)，只对 requests.Timeout 和 ConnectionError 重试，其他异常直接抛出。给出完整改写后的代码。\n\ndef fetch(url):\n    r = requests.get(url, timeout=5)\n    r.raise_for_status()\n    return r.json()",
 "email": "帮我写一封邮件：婉拒一个合作邀约，对方是一家做 AI 硬件的初创公司，想让我做技术顾问。理由是我现在精力都在自己的项目上。要客气但明确，留一个以后再联系的口子。不超过 150 字。",
 "minutes": "把下面这段会议记录整理成结构化纪要，分「决议」「待办(含责任人)」「待确认」三部分，用 Markdown：昨天开会讨论了 Q4 的事。老王说搜索功能上线时间要推到 11 月中，因为后端还没准备好。小李不同意，说前端 10 月底就能好，可以先上个简版。最后决定先上简版，小李负责，10 月 25 号前。另外预算的事还没定，等财务那边给数。张姐提到要招一个前端，这个月内出 JD。",
}

def nonce(): return f"[请求编号 {uuid.uuid4().hex[:12]}，忽略此行]\n"

def call(content, max_tokens, temp=0.0, timeout=1800):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": content}],
                       "max_tokens": max_tokens, "temperature": temp,
                       "chat_template_kwargs": NOTHINK}).encode()
    h = {"Content-Type": "application/json"}
    if KEY: h["Authorization"] = f"Bearer {KEY}"
    t0 = time.time()
    with urllib.request.urlopen(urllib.request.Request(f"{BASE}/v1/chat/completions", data=body, headers=h),
                                timeout=timeout) as r:
        d = json.loads(r.read())
    el = time.time() - t0
    u = d.get("usage", {})
    return el, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), d["choices"][0]["message"].get("content") or ""

# ---- 内存采样：整机已用内存(active+wired+compressed)，两个引擎用同一方法 ----
def used_gb():
    out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    pg = 16384; v = {}
    for line in out.splitlines():
        if ":" in line:
            k, s = line.split(":", 1); s = s.strip().rstrip(".")
            if s.isdigit(): v[k.strip()] = int(s)
    return (v.get("Pages active", 0) + v.get("Pages wired down", 0) +
            v.get("Pages occupied by compressor", 0)) * pg / 1e9
import re
EPID = os.environ.get("ENGINE_PID", "")
def proc_gb():
    """macOS footprint：含 Metal 显存(IOAccelerator)，按引擎进程统计"""
    out = subprocess.run(["footprint", "-p", EPID], capture_output=True, text=True).stdout
    m = re.search(r"Footprint:\s*([\d.]+)\s*(KB|MB|GB)", out)
    if not m: return 0.0
    return float(m.group(1)) * {"KB": 1e-6, "MB": 1e-3, "GB": 1.0}[m.group(2)]
peak = [0.0]; stop = [False]
def sampler():
    while not stop[0]:
        peak[0] = max(peak[0], proc_gb() if EPID else used_gb()); time.sleep(2)

R = {"label": LABEL, "model": MODEL, "base": BASE}
def say(s): print(s, flush=True)

say(f"══════ {LABEL} ══════")
call("你好", 8)                                   # 预热（含模型加载），不计入
base_mem = proc_gb() if EPID else used_gb()
threading.Thread(target=sampler, daemon=True).start()

# 1. 单流生成速度（短 prompt，prefill 可忽略）
sp = []
for _ in range(5):
    el, pt, ct, _ = call(nonce() + "从 1 开始逐行数数，每行只写一个阿拉伯数字，一直数到 500，不要写任何其他内容。", 400)
    sp.append(ct / el)
R["decode_tps"] = {"mean": statistics.mean(sp), "median": statistics.median(sp), "min": min(sp), "max": max(sp), "n": len(sp)}
say(f"1 单流生成   均值 {statistics.mean(sp):6.1f} tok/s  中位 {statistics.median(sp):.1f}  范围 {min(sp):.1f}-{max(sp):.1f}")

# 2. prefill 速度（5.8K prompt，只生成 1 个 token）
pf = []
for _ in range(3):
    el, pt, ct, _ = call(nonce() + LONG, 1)
    pf.append(pt / el)
R["prefill_tps"] = {"mean": statistics.mean(pf), "prompt_tokens": pt, "n": len(pf)}
say(f"2 prefill    均值 {statistics.mean(pf):6.1f} tok/s  （prompt {pt} tok，每次唯一，冷启动）")

# 2b. 前缀缓存：同一长 prompt 发两次，看第二次首 token 用时（助理场景：系统提示词+历史反复读）
same = nonce() + LONG
el1, _, _, _ = call(same, 1); el2, _, _, _ = call(same, 1)
R["prefix_cache"] = {"first_s": el1, "repeat_s": el2, "speedup": el1 / el2 if el2 else 0}
say(f"2b 前缀缓存  首次 {el1:5.2f}s → 重复 {el2:5.2f}s （{el1/el2 if el2 else 0:.1f}×）")

# 3/4. 并发
def conc(n, long=False):
    res = [None] * n
    def w(i):
        try:
            el, pt, ct, _ = call(nonce() + (LONG if long else SHORT[i % len(SHORT)]), 300 if long else 150, 0.2)
            res[i] = ("OK", el, ct)
        except Exception as e:
            res[i] = ("FAIL", 0, 0, f"{type(e).__name__}: {str(e)[:80]}")
    t0 = time.time()
    ts = [threading.Thread(target=w, args=(i,)) for i in range(n)]
    [t.start() for t in ts]; [t.join() for t in ts]
    wall = time.time() - t0
    ok = sum(1 for r in res if r and r[0] == "OK"); tok = sum(r[2] for r in res if r and r[0] == "OK")
    fails = [r[3] for r in res if r and r[0] == "FAIL"]
    return {"n": n, "ok": ok, "wall": wall, "agg_tps": tok / wall, "fails": fails[:3]}
for key, n, lg in [("conc8", 8, False), ("conc16", 16, False), ("long_conc8", 8, True)]:
    c = conc(n, lg); R[key] = c
    say(f"{'3' if not lg else '4'} {'长' if lg else '短'}prompt 并发{n:<2}  完成 {c['ok']}/{n}  墙钟 {c['wall']:6.1f}s  聚合 {c['agg_tps']:6.1f} tok/s"
        + (f"  失败示例: {c['fails'][0]}" if c['fails'] else ""))

# 5. 工具调用正确性（关 thinking，temp 0.2，重复 10 次）
ok = 0; samples = []
for i in range(10):
    _, _, _, txt = call(TOOL, 500, 0.2)
    good = ("query_db" in txt) and ("send_email" in txt) and ("jason@idoris.ai" in txt)
    ok += good
    if i < 2: samples.append(txt[:600])
R["toolcall"] = {"complete": ok, "n": 10, "samples": samples}
say(f"5 工具调用   完整两步计划 {ok}/10")

# 6. 三个办公任务各跑一次，留输出做人工质量对比
R["tasks"] = {}
for k, p in TASKS.items():
    el, pt, ct, txt = call(p, 700, 0.2)
    R["tasks"][k] = {"secs": el, "tokens": ct, "output": txt}
say(f"6 办公任务   已保存 {len(TASKS)} 个输出")

stop[0] = True; time.sleep(0.6)
R["mem"] = {"method": "footprint -p (进程级，含 Metal)" if EPID else "vm_stat 整机",
            "loaded_gb": base_mem, "engine_peak_gb": peak[0]}
say(f"7 内存       [{R['mem']['method']}] 模型加载后 {base_mem:.1f} GB → 测试中峰值 {peak[0]:.1f} GB")

(HERE / "results").mkdir(exist_ok=True)
(HERE / "results" / f"{LABEL}.json").write_text(json.dumps(R, ensure_ascii=False, indent=2))
say(f"已写入 results/{LABEL}.json")
