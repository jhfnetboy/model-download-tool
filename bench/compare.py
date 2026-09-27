import json, pathlib
R = pathlib.Path(__file__).parent / "results"
a = json.loads((R / "omlx-mlx8bit.json").read_text())
b = json.loads((R / "llamacpp-q8_0.json").read_text())
rows = [
 ("单流生成 tok/s (均值)", a["decode_tps"]["mean"], b["decode_tps"]["mean"]),
 ("prefill tok/s (5.8K)", a["prefill_tps"]["mean"], b["prefill_tps"]["mean"]),
 ("短prompt 并发8 聚合", a["conc8"]["agg_tps"], b["conc8"]["agg_tps"]),
 ("短prompt 并发16 聚合", a["conc16"]["agg_tps"], b["conc16"]["agg_tps"]),
 ("长prompt 并发8 聚合", a["long_conc8"]["agg_tps"], b["long_conc8"]["agg_tps"]),
 ("长prompt 并发8 墙钟s", a["long_conc8"]["wall"], b["long_conc8"]["wall"]),
 ("前缀缓存加速 ×", a["prefix_cache"]["speedup"], b["prefix_cache"]["speedup"]),
 ("引擎内存峰值 GB", a["mem"]["engine_peak_gb"], b["mem"]["engine_peak_gb"]),
]
print("\n══════════ 35B 同模型对照：oMLX(MLX 8bit) vs llama-server(GGUF Q8_0) ══════════")
print(f"{'指标':<22}{'oMLX':>12}{'llama.cpp':>12}{'llama/oMLX':>12}")
for k, x, y in rows: print(f"{k:<22}{x:>12.1f}{y:>12.1f}{(y/x if x else 0):>11.0%}")
for k in ["conc8", "conc16", "long_conc8"]:
    print(f"{k+' 完成率':<22}{a[k]['ok']:>9}/{a[k]['n']}{b[k]['ok']:>9}/{b[k]['n']}")
print(f"{'工具调用完整':<22}{a['toolcall']['complete']:>9}/10{b['toolcall']['complete']:>9}/10")
ratio = b["decode_tps"]["mean"] / a["decode_tps"]["mean"]
passed = all(b[k]["ok"] == b[k]["n"] for k in ["conc8", "conc16", "long_conc8"])
print(f"\n预设条件：llama.cpp 单流生成 ≥ oMLX 的 90% 且并发/长prompt 全部完成")
print(f"  生成速度比 {ratio:.0%}（{'达标' if ratio >= .9 else '未达标'}）；并发与长prompt {'全部完成' if passed else '有失败'}")
print(f"  → {'满足切换条件，可考虑全平台统一 llama.cpp' if ratio >= .9 and passed else '不满足切换条件，Mac 继续用 oMLX'}")
