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
        # 1. 获取数据
        log.info("Fetching raw data...")
        preds_json = fetch_data("https://raw.githubusercontent.com/sstklen/trump-code/main/data/predictions_log.json")
        report_json = fetch_data("https://raw.githubusercontent.com/sstklen/trump-code/main/data/daily_report.json")
        
        preds_raw = json.loads(preds_json)
        report = json.loads(report_json)
        
        # 兼容处理：将字典或列表统一转为列表，并处理可能的字段名
        preds = []
        if isinstance(preds_raw, dict):
            for k, v in preds_raw.items():
                v['date'] = v.get('date', k)
                preds.append(v)
        else:
            preds = preds_raw

        spy_json = fetch_data("https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=2y")
        spy_res = json.loads(spy_json)["chart"]["result"][0]
        spy_data = {datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"): p 
                    for t, p in zip(spy_res["timestamp"], spy_res["indicators"]["quote"][0]["close"]) if p}
        sorted_dates = sorted(spy_data.keys())

        # 2. 回测计算
        equity = [100.0]
        rets, model_map = [], {}
        win, total = 0, 0

        for p in sorted(preds, key=lambda x: str(x.get("date", ""))[:10]):
            d = str(p.get("date", ""))[:10]
            match_date = next((dt for dt in sorted_dates if dt >= d), None)
            
            if match_date:
                idx = sorted_dates.index(match_date)
                hold = int(p.get("hold_days", 1))
                if idx + hold < len(sorted_dates):
                    p1, p2 = spy_data[sorted_dates[idx]], spy_data[sorted_dates[idx + hold]]
                    raw_diff = (p2 - p1) / p1
                    
                    # 关键修复：多字段兼容匹配信号和模型ID
                    sig = str(p.get("direction", p.get("signal", "BULLISH"))).upper()
                    m_id = p.get("model", p.get("model_id", p.get("type", "Unknown")))
                    
                    actual_ret = raw_diff if "BULL" in sig else -raw_diff
                    
                    total += 1
                    if actual_ret > 0: win += 1
                    rets.append(actual_ret)
                    equity.append(equity[-1] * (1 + actual_ret))
                    
                    m = model_map.setdefault(m_id, {"win":0, "n":0, "rets":[]})
                    m["n"] += 1
                    if actual_ret > 0: m["win"] += 1
                    m["rets"].append(actual_ret)

        # 3. 指标统计
        wr = win / total if total > 0 else 0
        cum_ret = (equity[-1] / 100.0) - 1
        sharpe = (mean(rets) / stdev(rets) * math.sqrt(252)) if len(rets) > 1 else 0
        z_score = (wr - 0.5) / math.sqrt(0.25 / total) if total > 0 else 0

        # 4. 渲染模型行
        model_rows = ""
        for mid, d in sorted(model_map.items(), key=lambda x: x[1]['win']/x[1]['n'], reverse=True):
            m_wr = d["win"]/d["n"]
            m_ret = mean(d["rets"])
            color = "#00e5a0" if m_wr >= 0.55 else "#ff4d6a"
            model_rows += f"""
            <tr>
                <td style="color:#8aa4b8; font-family:monospace;">{mid}</td>
                <td>{d['n']}</td>
                <td style="color:{color}; font-weight:bold;">{m_wr:.1%}</td>
                <td style="text-align:right; color:{color};">{m_ret:+.3%}</td>
            </tr>"""

        # 5. 完整深色专业 UI 模板
        update_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        summary_zh = report.get("summary", {}).get("zh", "暂无今日摘要")
        
        html = f"""
        <!DOCTYPE html><html><head><meta charset="UTF-8"><title>Trump Code Monitor</title>
        <style>
            body {{ background:#080c10; color:#c8daea; font-family:sans-serif; margin:0; padding:20px; font-size:13px; }}
            .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:#1e2d3d; border:1px solid #1e2d3d; margin-bottom:20px; }}
            .kpi {{ background:#0d1318; padding:20px; }}
            .val {{ font-size:32px; font-weight:bold; font-family:monospace; margin-top:5px; color:#00e5a0; }}
            .lab {{ color:#8aa4b8; font-size:11px; text-transform:uppercase; }}
            table {{ width:100%; border-collapse:collapse; background:#0d1318; }}
            td, th {{ padding:12px; border-bottom:1px solid #1e2d3d; text-align:left; }}
            th {{ color:#4a6178; font-size:10px; text-transform:uppercase; }}
            .report {{ background:#111820; padding:20px; border:1px solid #1e2d3d; border-radius:4px; margin-top:20px; line-height:1.6; }}
        </style></head><body>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <div style="color:#00e5a0; font-weight:bold; font-size:16px;">TRUMP/CODE PROFESSIONAL MONITOR</div>
            <div style="color:#4a6178; font-size:11px;">UTC: {update_time} | TOTAL_TRADES: {total}</div>
        </div>
        <div class="grid">
            <div class="kpi"><div class="lab">真实胜率</div><div class="val">{wr:.1%}</div></div>
            <div class="kpi"><div class="lab">显著性 Z-SCORE</div><div class="val" style="color:{"#00e5a0" if z_score>2 else "#ff4d6a"}">{z_score:+.2f}</div></div>
            <div class="kpi"><div class="lab">模拟累计收益</div><div class="val" style="color:{"#00e5a0" if cum_ret>0 else "#ff4d6a"};">{cum_ret:+.2%}</div></div>
            <div class="kpi"><div class="lab">SHARPE 年化</div><div class="val" style="color:#3d9eff;">{sharpe:.2f}</div></div>
        </div>
        <div style="display:grid; grid-template-columns: 2fr 1fr; gap:20px;">
            <div>
                <div class="lab" style="margin-bottom:10px;">模型排行 (基于真实数据回测)</div>
                <table><tr><th>模型 ID</th><th>样本</th><th>胜率</th><th style="text-align:right">平均回报</th></tr>{model_rows}</table>
            </div>
            <div>
                <div class="lab" style="margin-bottom:10px;">今日深度摘要</div>
                <div class="report">
                    <b style="color:#3d9eff;">中文研判:</b><br>{summary_zh}
                </div>
            </div>
        </div>
        </body></html>
        """
        Path("trump_dashboard.html").write_text(html, encoding="utf-8")
        if Path("docs").exists(): (Path("docs") / "index.html").write_text(html, encoding="utf-8")
        log.info("Dashboard updated successfully with full UI.")
    except Exception as e:
        log.error(f"Error: {e}")

if __name__ == "__main__":
    main()
