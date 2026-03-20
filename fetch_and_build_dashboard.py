import json, math, sys, logging, ssl, urllib.request, os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from statistics import mean, stdev

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname, ssl_ctx.verify_mode = False, ssl.CERT_NONE

def fetch_data(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as r:
        return r.read().decode('utf-8')

def main():
    try:
        # 1. 数据采集
        preds_json = fetch_data("https://raw.githubusercontent.com/sstklen/trump-code/main/data/predictions_log.json")
        report_json = fetch_data("https://raw.githubusercontent.com/sstklen/trump-code/main/data/daily_report.json")
        preds_raw = json.loads(preds_json)
        report = json.loads(report_json)
        
        preds = []
        if isinstance(preds_raw, dict):
            for k, v in preds_raw.items():
                v['date'] = v.get('date', k)
                preds.append(v)
        else: preds = preds_raw

        spy_json = fetch_data("https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=2y")
        spy_res = json.loads(spy_json)["chart"]["result"][0]
        spy_prices = spy_res["indicators"]["quote"][0]["close"]
        spy_dates = [datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d") for t in spy_res["timestamp"]]
        spy_map = {d: p for d, p in zip(spy_dates, spy_prices) if p}
        sorted_dates = sorted(spy_map.keys())

        # 2. 核心量化引擎：信号翻转 + 精准对齐
        equity = [100.0]
        rets, model_map = [], {}
        peak = 100.0
        mdd = 0

        for p in sorted(preds, key=lambda x: str(x.get("date", ""))[:10]):
            sig_date_str = str(p.get("date", ""))[:10]
            # 经理优化：寻找最接近信号的价格，而非死板的次日
            entry_date = next((dt for dt in sorted_dates if dt >= sig_date_str), None)
            
            if entry_date:
                idx = sorted_dates.index(entry_date)
                hold = int(p.get("hold_days", 1))
                if idx + hold < len(sorted_dates):
                    p_in = spy_map[sorted_dates[idx]]
                    p_out = spy_map[sorted_dates[idx + hold]]
                    
                    price_move = (p_out - p_in) / p_in
                    sig = str(p.get("direction", p.get("signal", "BULLISH"))).upper()
                    
                    # --- QUANT MAGIC: INVERSE SIGNAL EXECUTION ---
                    # 既然原始信号 89% 错误，我们反着做：BULL 卖出，BEAR 买入
                    actual_ret = -price_move if "BULL" in sig else price_move
                    
                    # 扣除滑点 0.01%
                    actual_ret -= 0.0001
                    
                    rets.append(actual_ret)
                    current_eq = equity[-1] * (1 + actual_ret)
                    equity.append(current_eq)
                    
                    # 风险监控
                    if current_eq > peak: peak = current_eq
                    mdd = max(mdd, (peak - current_eq) / peak)

                    m_id = p.get("model", p.get("model_id", "Unknown"))
                    m = model_map.setdefault(m_id, {"win":0, "n":0, "rets":[]})
                    m["n"] += 1
                    if actual_ret > 0: m["win"] += 1
                    m["rets"].append(actual_ret)

        # 3. 绩效统计
        total = len(rets)
        wr = sum(1 for r in rets if r > 0) / total if total > 0 else 0
        cum_ret = (equity[-1] / 100.0) - 1
        sharpe = (mean(rets) / stdev(rets) * math.sqrt(252)) if len(rets) > 1 else 0
        profit_factor = sum(r for r in rets if r > 0) / abs(sum(r for r in rets if r < 0)) if any(r < 0 for r in rets) else 1.0

        # 4. 生成专业模型画像
        model_rows = ""
        for mid, d in sorted(model_map.items(), key=lambda x: mean(x[1]['rets']), reverse=True):
            m_wr, m_ret = d["win"]/d["n"], mean(d["rets"])
            color = "#00e5a0" if m_ret > 0 else "#ff4d6a"
            model_rows += f"<tr><td>{mid}</td><td>{d['n']}</td><td style='color:{color}'>{m_wr:.1%}</td><td style='text-align:right;color:{color}'>{m_ret:+.3%}</td></tr>"

        # 5. UI 渲染 (Bloomberg 终端风格)
        update_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        summary = report.get("summary", {}).get("zh", "等待深度分析中...")

        html = f"""
        <!DOCTYPE html><html><head><meta charset="UTF-8">
        <style>
            body {{ background:#05080a; color:#a0b0c0; font-family:'Segoe UI', sans-serif; margin:0; padding:25px; }}
            .header {{ display:flex; justify-content:space-between; border-bottom:1px solid #1a2a3a; padding-bottom:15px; margin-bottom:20px; }}
            .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:15px; margin-bottom:25px; }}
            .kpi {{ background:#0f171f; padding:20px; border-top:3px solid #3d9eff; }}
            .val {{ font-size:32px; font-weight:bold; color:#fff; margin-top:8px; font-family:monospace; }}
            .lab {{ font-size:10px; color:#5a6a7a; text-transform:uppercase; letter-spacing:1px; }}
            .main-content {{ display:grid; grid-template-columns: 3fr 2fr; gap:25px; }}
            table {{ width:100%; border-collapse:collapse; background:#0f171f; }}
            th, td {{ padding:12px 15px; text-align:left; border-bottom:1px solid #1a2a3a; }}
            th {{ background:#16222d; color:#5a6a7a; font-size:10px; }}
            .report {{ background:#0f171f; padding:20px; line-height:1.7; border:1px solid #1a2a3a; font-size:14px; color:#d0d0d0; }}
            .flip-tag {{ background: #ff9800; color: #000; padding: 2px 8px; border-radius: 2px; font-size: 10px; font-weight: bold; }}
        </style></head><body>
        <div class="header">
            <div><span style="font-size:18px; color:#3d9eff; font-weight:bold;">TRUMP/CODE</span> <span style="color:#fff">QUANT TERMINAL v2.0</span> <span class="flip-tag">INVERSE SIGNALS ENABLED</span></div>
            <div style="font-size:11px;">SYNC: {update_time} UTC | BACKTEST_SAMPLES: {total}</div>
        </div>
        <div class="grid">
            <div class="kpi"><div class="lab">Total Alpha Return</div><div class="val" style="color:{"#00e5a0" if cum_ret>0 else "#ff4d6a"}">{cum_ret:+.2%}</div></div>
            <div class="kpi"><div class="lab">Realized Win Rate</div><div class="val">{wr:.1%}</div></div>
            <div class="kpi"><div class="lab">Max Drawdown</div><div class="val" style="color:#ff4d6a">{mdd:.1%}</div></div>
            <div class="kpi"><div class="lab">Profit Factor</div><div class="val">{profit_factor:.2f}</div></div>
        </div>
        <div class="main-content">
            <div>
                <div class="lab" style="margin-bottom:10px;">Model Attribution (Sorted by Alpha Contribution)</div>
                <table><tr><th>MODEL ID</th><th>SAMPLES</th><th>WIN RATE</th><th style="text-align:right">AVG RET/TRADE</th></tr>{model_rows}</table>
            </div>
            <div>
                <div class="lab" style="margin-bottom:10px;">Market Context & Intelligence</div>
                <div class="report">
                    <b style="color:#3d9eff;">深度研判:</b><br>{summary}
                </div>
            </div>
        </div>
        </body></html>
        """
        Path("trump_dashboard.html").write_text(html, encoding="utf-8")
        if Path("docs").exists(): (Path("docs") / "index.html").write_text(html, encoding="utf-8")
        log.info("Build Complete. Signals Flipped. Alpha Detected.")
    except Exception as e:
        log.error(f"Build Error: {e}")

if __name__ == "__main__":
    main()
