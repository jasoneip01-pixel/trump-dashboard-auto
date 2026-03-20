import json, math, sys, logging, ssl, urllib.request, os
from pathlib import Path
from datetime import datetime, timezone
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
        # 1. 核心数据获取
        log.info("Downloading datasets...")
        preds_raw = json.loads(fetch_data("https://raw.githubusercontent.com/sstklen/trump-code/main/data/predictions_log.json"))
        report_raw = json.loads(fetch_data("https://raw.githubusercontent.com/sstklen/trump-code/main/data/daily_report.json"))
        
        preds = preds_raw if isinstance(preds_raw, list) else [{**v, "date": k} for k, v in preds_raw.items()]

        spy_json = fetch_data("https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=2y")
        spy_res = json.loads(spy_json)["chart"]["result"][0]
        spy_map = {datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"): p 
                   for t, p in zip(spy_res["timestamp"], spy_res["indicators"]["quote"][0]["close"]) if p}
        sorted_dates = sorted(spy_map.keys())

        # 2. 量化回测引擎 (反向信号执行)
        equity_curve = []
        rets, model_map = [], {}
        current_eq = 100.0
        peak = 100.0
        mdd = 0

        for p in sorted(preds, key=lambda x: str(x.get("date", ""))[:10]):
            d = str(p.get("date", ""))[:10]
            # 找到离信号最近的交易日
            entry_date = next((dt for dt in sorted_dates if dt >= d), None)
            
            if entry_date:
                idx = sorted_dates.index(entry_date)
                hold = int(p.get("hold_days", 1))
                if idx + hold < len(sorted_dates):
                    p_in, p_out = spy_map[sorted_dates[idx]], spy_map[sorted_dates[idx + hold]]
                    raw_move = (p_out - p_in) / p_in
                    
                    # 关键逻辑：反向执行 (Inverse Alpha)
                    sig = str(p.get("direction", p.get("signal", "BULLISH"))).upper()
                    actual_ret = -raw_move if "BULL" in sig else raw_move
                    actual_ret -= 0.0001 # 扣除预估交易滑点
                    
                    rets.append(actual_ret)
                    current_eq *= (1 + actual_ret)
                    equity_curve.append({"t": entry_date, "y": round(current_eq, 2)})
                    
                    # 风险指标计算
                    if current_eq > peak: peak = current_eq
                    mdd = max(mdd, (peak - current_eq) / peak)

                    m_id = p.get("model", p.get("model_id", "Default_Alpha"))
                    m = model_map.setdefault(m_id, {"win":0, "n":0, "rets":[]})
                    m["n"] += 1
                    if actual_ret > 0: m["win"] += 1
                    m["rets"].append(actual_ret)

        # 3. 统计汇总
        total_trades = len(rets)
        cum_ret = (current_eq / 100.0) - 1
        sharpe = (mean(rets) / stdev(rets) * math.sqrt(252)) if len(rets) > 1 else 0
        profit_factor = sum(r for r in rets if r > 0) / abs(sum(r for r in rets if r < 0)) if any(r < 0 for r in rets) else 1.0

        # 4. 模型表格渲染
        model_rows = "".join([
            f"<tr><td>{k}</td><td>{v['n']}</td><td style='color:{'#00e5a0' if mean(v['rets'])>0 else '#ff4d6a'}'>{v['win']/v['n']:.1%}</td><td>{mean(v['rets']):+.3%}</td></tr>" 
            for k, v in sorted(model_map.items(), key=lambda x: mean(x[1]['rets']), reverse=True)
        ])

        # 5. UI 渲染 (专业深色终端风格)
        update_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        summary_zh = report_raw.get('summary', {}).get('zh', '市场情绪分析同步中...')

        html = f"""
        <!DOCTYPE html><html><head><meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {{ background:#05080a; color:#a0b0c0; font-family:sans-serif; margin:0; padding:20px; }}
            .header {{ display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1a2a3a; padding-bottom:15px; margin-bottom:20px; }}
            .kpi-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:15px; margin-bottom:20px; }}
            .kpi-card {{ background:#0f171f; padding:20px; border:1px solid #1a2a3a; border-radius:4px; }}
            .val {{ font-size:32px; color:#fff; font-family:monospace; margin-top:5px; font-weight:bold; }}
            .lab {{ font-size:10px; color:#5a6a7a; text-transform:uppercase; letter-spacing:1px; }}
            .chart-box {{ background:#0f171f; padding:20px; border:1px solid #1a2a3a; height:350px; margin-bottom:20px; }}
            .main-layout {{ display:grid; grid-template-columns: 2fr 1.2fr; gap:20px; }}
            table {{ width:100%; border-collapse:collapse; font-size:12px; }}
            th, td {{ text-align:left; padding:12px; border-bottom:1px solid #1a2a3a; }}
            th {{ color:#5a6a7a; font-size:10px; }}
            .report {{ background:#111a24; padding:20px; border-left:4px solid #3d9eff; line-height:1.7; font-size:14px; color:#d0d0d0; }}
            .badge {{ background:#3d9eff; color:#fff; padding:2px 6px; border-radius:3px; font-size:10px; font-weight:bold; }}
        </style></head><body>
        <div class="header">
            <div style="font-size:22px; font-weight:bold; color:#fff;">TRUMP/CODE <span style="color:#3d9eff;">ALPHA TERMINAL</span></div>
            <div style="font-size:11px;">UTC SYNC: {update_time} | <span style="color:#00e5a0;">● SYSTEM ACTIVE</span></div>
        </div>
        <div class="kpi-grid">
            <div class="kpi-card"><div class="lab">Cumulative Return</div><div class="val" style="color:#00e5a0;">{cum_ret:+.2%}</div></div>
            <div class="kpi-card"><div class="lab">Sharpe Ratio</div><div class="val" style="color:#3d9eff;">{sharpe:.2f}</div></div>
            <div class="kpi-card"><div class="lab">Max Drawdown</div><div class="val" style="color:#ff4d6a;">{mdd:.1%}</div></div>
            <div class="kpi-card"><div class="lab">Profit Factor</div><div class="val">{profit_factor:.2f}</div></div>
        </div>
        <div class="chart-box"><canvas id="mainChart"></canvas></div>
        <div class="main-layout">
            <div class="kpi-card">
                <div class="lab" style="margin-bottom:15px;">Model Attribution (Realized Alpha)</div>
                <table><tr><th>Model ID</th><th>Trades</th><th>Win%</th><th>Avg Ret</th></tr>{model_rows}</table>
            </div>
            <div>
                <div class="lab" style="margin-bottom:10px;">Market Context</div>
                <div class="report"><span class="badge">AI SUMMARY</span><br><br>{summary_zh}</div>
            </div>
        </div>
        <script>
            new Chart(document.getElementById('mainChart'), {{
                type: 'line',
                data: {{
                    labels: {json.dumps([d['t'] for d in equity_curve])},
                    datasets: [{{
                        label: 'Equity Curve',
                        data: {json.dumps([d['y'] for d in equity_curve])},
                        borderColor: '#00e5a0',
                        backgroundColor: 'rgba(0,229,160,0.05)',
                        fill: true,
                        tension: 0.1,
                        pointRadius: 0,
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        x: {{ grid: {{ color: '#1a2a3a' }}, ticks: {{ color: '#5a6a7a', maxTicksLimit: 10 }} }},
                        y: {{ grid: {{ color: '#1a2a3a' }}, ticks: {{ color: '#5a6a7a' }} }}
                    }},
                    plugins: {{ legend: {{ display: false }} }}
                }}
            }});
        </script>
        </body></html>
        """
        Path("trump_dashboard.html").write_text(html, encoding="utf-8")
        if Path("docs").exists(): (Path("docs") / "index.html").write_text(html, encoding="utf-8")
        log.info("Terminal v4.0 Full Deployment ✅")
    except Exception as e:
        log.error(f"Critical Failure: {e}")

if __name__ == "__main__":
    main()
