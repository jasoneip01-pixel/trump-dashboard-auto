import json, math, random, time, sys, logging, ssl, urllib.request, warnings, subprocess, platform
from pathlib import Path
from datetime import datetime, timezone, timedelta
from statistics import mean, stdev
import bisect

# 配置
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)
RESULTS_DIR = Path("paper_results"); RESULTS_DIR.mkdir(exist_ok=True)

RAW = "https://raw.githubusercontent.com/sstklen/trump-code/main"
FILES = {
    "predictions_log.json": f"{RAW}/data/predictions_log.json",
    "daily_report.json": f"{RAW}/data/daily_report.json",
    "surviving_rules.json": f"{RAW}/data/surviving_rules.json",
    "x_truth_gap.json": f"{RAW}/data/x_truth_gap.json"
}
TICKERS = {
    "market_SP500.json": "SPY",
    "market_BTC.json": "BTC-USD",
    "market_GOLD.json": "GC=F",
    "market_VIX.json": "^VIX"
}

def ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c

def get_data(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, context=ctx(), timeout=timeout) as r:
        return r.read()

def fetch_github():
    print("\n── STEP 1/3 GitHub 真实数据 ─────────────────")
    ok = 0
    for fname, url in FILES.items():
        local = DATA_DIR / fname
        try:
            content = get_data(url)
            data = json.loads(content.decode('utf-8'))
            local.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            log.info("✅ %.1fKB %s", local.stat().st_size / 1024, fname)
            ok += 1
            time.sleep(0.3)
        except Exception as e:
            log.warning("❌ %s → %s", fname, e)
    print(f" {ok}/{len(FILES)} 文件就绪")

def fetch_market():
    print("\n── STEP 2/3 市场价格 Yahoo Finance ──────────")
    ok = 0
    for fname, ticker in TICKERS.items():
        local = DATA_DIR / fname
        try:
            # 使用原生 urllib 抓取，避免依赖 requests 导致 Actions 失败
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2y"
            content = get_data(url)
            raw = json.loads(content.decode('utf-8'))
            
            result = raw["chart"]["result"][0]
            ts = result["timestamp"]
            close = result["indicators"]["quote"][0]["close"]
            open_ = result["indicators"]["quote"][0].get("open", close)
            
            records = {}
            for i, t in enumerate(ts):
                if close[i] is None: continue
                # 转换为本地日期字符串
                d = datetime.fromtimestamp(t).strftime("%Y-%m-%d")
                records[d] = {"open": round(float(open_[i] or close[i]), 4), "close": round(float(close[i]), 4)}
            
            local.write_text(json.dumps(records, indent=2))
            log.info("✅ %s %d天", ticker, len(records))
            ok += 1
            time.sleep(0.5)
        except Exception as e:
            log.warning("❌ %s → %s", ticker, e)
    print(f" {ok}/{len(TICKERS)} 资产就绪")

def wilson(c, n, z=1.96):
    if n == 0: return 0.0, 1.0
    p = c / n; d = 1 + z**2 / n; ctr = (p + z**2 / (2 * n)) / d
    mg = z * math.sqrt(abs(p * (1 - p) / n + z**2 / (4 * n**2))) / d
    return round(max(0, ctr - mg), 4), round(min(1, ctr + mg), 4)

def perm_p(c, n, k=10000):
    if n == 0: return 1.0
    obs = c / n; random.seed(0)
    return round(sum(1 for _ in range(k) if sum(random.random() > .5 for _ in range(n)) / n >= obs) / k, 5)

def spy_ret_robust(target_date, hold, spy, sorted_dates):
    # 找到 target_date 之后最接近的交易日
    idx = bisect.bisect_left(sorted_dates, target_date)
    if idx >= len(sorted_dates): return None
    
    start_idx = idx
    end_idx = start_idx + hold
    if end_idx >= len(sorted_dates): return None
    
    try:
        start_price = spy[sorted_dates[start_idx]]["close"]
        end_price = spy[sorted_dates[end_idx]]["close"]
        return (end_price - start_price) / start_price
    except:
        return None

def backtest():
    print("\n── STEP 3/3 回溯分析 ────────────────────────")
    plog = DATA_DIR / "predictions_log.json"
    spyf = DATA_DIR / "market_SP500.json"
    if not plog.exists(): return {}
    
    raw = json.loads(plog.read_text(encoding="utf-8"))
    preds = raw if isinstance(raw, list) else [{**v, "date": k} for k, v in raw.items() if isinstance(v, dict)]
    spy = json.loads(spyf.read_text()) if spyf.exists() else {}
    sorted_dates = sorted(spy.keys())
    
    total = 0; correct = 0; rets = []; equity = [100.0]; by_model = {}; by_month = {}
    preds_sorted = sorted(preds, key=lambda x: x.get("date", "")[:10])

    for rec in preds_sorted:
        date_str = rec.get("date", "")[:10]
        if not date_str: continue
        
        dir_ = rec.get("direction", rec.get("signal", "BULLISH"))
        hold = int(rec.get("hold_days", rec.get("holding_period", 1)))
        model = rec.get("model", rec.get("model_id", "?"))
        
        actual = spy_ret_robust(date_str, hold, spy, sorted_dates)
        if actual is not None:
            signed = actual if dir_ == "BULLISH" else -actual
            ok = signed > 0
            total += 1; correct += int(ok); rets.append(signed)
            equity.append(equity[-1] * (1 + signed))
            
            m = by_model.setdefault(model, {"c": 0, "n": 0, "r": []}); m["n"] += 1; m["c"] += int(ok); m["r"].append(signed)
            ym = by_month.setdefault(date_str[:7], {"c": 0, "n": 0, "r": []}); ym["n"] += 1; ym["c"] += int(ok); ym["r"].append(signed)

    if total == 0: return {}

    wr = correct / total; clo, chi = wilson(correct, total); z = (wr - .5) / math.sqrt(.25 / total) if total > 0 else 0
    avg = mean(rets); std = stdev(rets) if len(rets) > 1 else 0
    sharpe = (avg / std * math.sqrt(252)) if std > 0 else 0
    peak = equity[0]; mdd = 0
    for v in equity: peak = max(peak, v); mdd = min(mdd, (v - peak) / peak)
    
    models_out = {mid: {"win_rate": round(d["c"]/d["n"], 4), "total": d["n"], "avg_return": round(mean(d["r"]), 6), "ci_lo": wilson(d["c"], d["n"])[0], "ci_hi": wilson(d["c"], d["n"])[1]} for mid, d in by_model.items()}
    months_out = {ym: {"win_rate": round(d["c"]/d["n"], 4), "total": d["n"], "avg_return": mean(d["r"])} for ym, d in sorted(by_month.items())}

    result = {
        "total": total, "correct": correct, "win_rate": round(wr, 4), "win_rate_pct": f"{wr:.1%}",
        "ci_lo": clo, "ci_hi": chi, "ci_str": f"{clo:.1%}–{chi:.1%}", "z_score": round(z, 3),
        "significant": abs(z) > 1.96, "avg_return": round(avg, 6), "sharpe": round(sharpe, 3),
        "max_drawdown": round(mdd, 4), "cumulative_return": round(equity[-1] / equity[0] - 1, 4),
        "equity_curve": [round(v, 4) for v in equity], "models": models_out, "months": months_out,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
    (RESULTS_DIR / "real_backtest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return result

def build_html(bt):
    # 保持之前 UI 的完整逻辑...
    daily_en = daily_zh = ""
    dp = DATA_DIR / "daily_report.json"
    if dp.exists():
        try:
            dr = json.loads(dp.read_text(encoding="utf-8"))
            daily_en = dr.get("summary", {}).get("en", "") or dr.get("en", "")
            daily_zh = dr.get("summary", {}).get("zh", "") or dr.get("zh", "")
        except: pass
    
    eq = bt.get("equity_curve", [100.0])
    step = max(1, len(eq) // 150); eq_s = eq[::step]
    if eq[-1] not in eq_s: eq_s.append(eq[-1])
    
    months = bt.get("months", {}); ml = json.dumps(list(months.keys())); mr = json.dumps([round(v["win_rate"]*100, 1) for v in months.values()])
    
    models = bt.get("models", {}); rows = ""
    for mid, d in sorted(models.items(), key=lambda x: -x[1]["win_rate"]):
        wr = d["win_rate"] * 100; bc = "#00e5a0" if wr >= 65 else ("#f5a623" if wr >= 53 else "#ff4d6a")
        rows += f'<tr><td style="font-family:monospace;font-size:11px">{mid}</td><td style="text-align:right;font-family:monospace;font-size:11px">{d["total"]}</td><td style="text-align:right;font-family:monospace;font-weight:700;color:{bc}">{wr:.1f}%</td><td style="font-size:10px;color:#8aa4b8">{d["ci_lo"]:.0%}–{d["ci_hi"]:.0%}</td><td style="text-align:right;font-family:monospace;font-size:11px;color:{"#00e5a0" if d["avg_return"]>0 else "#ff4d6a"}">{d["avg_return"]:+.3%}</td></tr>'
    
    wrc = "#00e5a0" if bt.get("win_rate", 0) >= .58 else ("#f5a623" if bt.get("win_rate", 0) >= .53 else "#ff4d6a")
    crc = "#00e5a0" if bt.get("cumulative_return", 0) >= 0 else "#ff4d6a"
    sc = "#00e5a0" if bt.get("sharpe", 0) > 1 else ("#f5a623" if bt.get("sharpe", 0) > 0 else "#ff4d6a")
    zc = "#00e5a0" if abs(bt.get("z_score", 0)) > 1.96 else "#f5a623"
    
    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Trump Code 看板</title>
<style>:root{{--bg:#080c10;--bg2:#0d1318;--border:#1e2d3d;--green:#00e5a0;--red:#ff4d6a;--amber:#f5a623;--blue:#3d9eff;--text:#c8daea;--text2:#8aa4b8}}body{{background:var(--bg);color:var(--text);font-family:sans-serif;font-size:13px}}header{{padding:12px 24px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;background:var(--bg2)}}.grid4{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1px;background:var(--border)}}.kpi{{background:var(--bg2);padding:20px}}.kv{{font-family:monospace;font-size:32px;font-weight:700;margin-top:8px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px 4px;border-bottom:1px solid var(--border);text-align:left}}.daily{{background:#111820;padding:15px;border-radius:4px;border:1px solid var(--border)}}</style></head><body>
<header><div style="color:var(--green);font-weight:bold">TRUMP CODE MONITOR</div><div style="font-size:10px;color:var(--text2)">{bt.get("generated_at","")[:19]} UTC</div></header>
<div class="grid4">
<div class="kpi"><div style="font-size:10px;color:var(--text2)">胜率</div><div class="kv" style="color:{wrc}">{bt.get("win_rate_pct","0%")}</div></div>
<div class="kpi"><div style="font-size:10px;color:var(--text2)">显著性 Z-Score</div><div class="kv" style="color:{zc}">{bt.get("z_score",0):+.2f}</div></div>
<div class="kpi"><div style="font-size:10px;color:var(--text2)">累计收益</div><div class="kv" style="color:{crc}">{bt.get("cumulative_return",0):+.2%}</div></div>
<div class="kpi"><div style="font-size:10px;color:var(--text2)">夏普比率</div><div class="kv" style="color:{sc}">{bt.get("sharpe",0):.2f}</div></div>
</div>
<div style="padding:20px;background:var(--bg2);margin-top:1px"><div style="font-size:10px;color:var(--text2);margin-bottom:15px">权益曲线</div><div style="height:200px"><canvas id="eq"></canvas></div></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--border)">
<div style="padding:20px;background:var(--bg2)"><table><tr><th>模型</th><th>次数</th><th>胜率</th><th>CI</th><th>回报</th></tr>{rows}</table></div>
<div style="padding:20px;background:var(--bg2)"><strong>日报摘要</strong><div class="daily" style="margin-top:10px"><b>ZH:</b> {daily_zh}<br><br><b>EN:</b> {daily_en}</div></div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>const ctx=document.getElementById('eq').getContext('2d');new Chart(ctx,{{type:'line',data:{{labels:{list(range(len(eq_s)))},datasets:[{{data:{eq_j},borderColor:'#00e5a0',fill:true,pointRadius:0,borderWidth:2}}]}},options:{{maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{display:false}}}}}}}});</script>
</body></html>"""
    return html

def main():
    fetch_github()
    fetch_market()
    bt = backtest()
    if bt:
        html = build_html(bt)
        Path("trump_dashboard.html").write_text(html, encoding="utf-8")
        log.info("✅ 看板生成成功")
    else:
        log.error("回测数据不足")

if __name__ == "__main__": main()
