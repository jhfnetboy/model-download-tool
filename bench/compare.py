import json, pathlib
R = pathlib.Path(__file__).parent / "results"
def L(n):
    p = R / f"{n}.json"
    return json.loads(p.read_text()) if p.exists() else None
COLS = [("oMLX 8bit", "omlx-mlx8bit"), ("oMLX 6bit", "omlx-mlx6bit"),
        ("OptiQ 4bit", "omlx-optiq4bit"), ("llama Q8_0", "llamacpp-q8_0")]
D = [(n, L(f)) for n, f in COLS]
D = [(n, d) for n, d in D if d]
base = dict(D)["oMLX 8bit"]
MET = [("单流生成 tok/s", lambda x: x["decode_tps"]["mean"]),
       ("prefill tok/s(5.8K冷)", lambda x: x["prefill_tps"]["mean"]),
       ("前缀缓存 ×", lambda x: x["prefix_cache"]["speedup"]),
       ("短并发8 聚合", lambda x: x["conc8"]["agg_tps"]),
       ("短并发16 聚合", lambda x: x["conc16"]["agg_tps"]),
       ("长并发8 聚合", lambda x: x["long_conc8"]["agg_tps"]),
       ("长并发8 墙钟 s", lambda x: x["long_conc8"]["wall"]),
       ("模型加载后内存 GB", lambda x: x["mem"]["loaded_gb"]),
       ("引擎内存峰值 GB", lambda x: x["mem"]["engine_peak_gb"])]
print("\n══════ Qwen3.6-35B-A3B 对照（同一客户端，引擎轮流独占） ══════")
print(f"{'指标':<20}" + "".join(f"{n:>12}" for n, _ in D))
for k, f in MET: print(f"{k:<20}" + "".join(f"{f(d):>12.1f}" for _, d in D))
for k in ["conc8", "conc16", "long_conc8"]:
    print(f"{k+' 完成':<20}" + "".join(f"{str(d[k]['ok'])+'/'+str(d[k]['n']):>12}" for _, d in D))
print(f"{'工具调用完整 /10':<20}" + "".join(f"{d['toolcall']['complete']:>12}" for _, d in D))

allok = lambda d: all(d[k]["ok"] == d[k]["n"] for k in ["conc8", "conc16", "long_conc8"])
def verdict(name, d, tool_slack):
    tc, tb = d["toolcall"]["complete"], base["toolcall"]["complete"]
    c1 = tc >= tb - tool_slack; c2 = allok(d); c3 = d["decode_tps"]["mean"] >= base["decode_tps"]["mean"]
    save = base["mem"]["engine_peak_gb"] - d["mem"]["engine_peak_gb"]
    print(f"\n【{name} vs 8bit】工具调用 {tc} vs {tb}（允许少 {tool_slack}）→ {'过' if c1 else '不过'}；"
          f"并发 → {'过' if c2 else '不过'}；生成 {d['decode_tps']['mean']:.1f} vs {base['decode_tps']['mean']:.1f} → {'过' if c3 else '不过'}；"
          f"内存峰值省 {save:.1f} GB；办公任务 → 待人工比对")
dd = dict(D)
if "oMLX 6bit" in dd: verdict("6bit 甜点区", dd["oMLX 6bit"], 0)
if "OptiQ 4bit" in dd: verdict("OptiQ-4bit 可否常驻", dd["OptiQ 4bit"], 1)
b = dd.get("llama Q8_0")
if b is None: print("\n【Mac 是否改用 llama.cpp】llama.cpp 数据未就绪（段 2）")
else:
    r = b["decode_tps"]["mean"] / base["decode_tps"]["mean"]
    print(f"\n【Mac 是否改用 llama.cpp】参考线：生成 ≥ oMLX 8bit 的 90% 且并发全过")
    print(f"  生成比 {r:.0%}，并发 {'全过' if allok(b) else '有失败'} → {'达到参考线' if r >= .9 and allok(b) else '未达参考线'}（最终由 jason 决定）")
print("\n注：办公任务输出原文在 results/*.json 的 tasks 字段，需人工比对。")
