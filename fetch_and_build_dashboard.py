import json, math, sys, logging, ssl, urllib.request, os
from pathlib import Path
from datetime import datetime, timezone
from statistics import mean, stdev

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def fetch_data(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as r:
        return r.read().decode('utf-8')

def main():
    try:
        # 1. 抓取数据
        preds_json = fetch_data("https://raw.githubusercontent.com/sstklen/trump-code/main/data/predictions_log.json")
        preds_raw = json.loads(preds_json)
        preds = preds_raw if isinstance(preds_raw, list) else [{**v, "date": k} for k, v in preds_raw.items()]

        spy_json = fetch_data("https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=2y")
        spy_res = json.loads(spy_json)["chart"]["result"][0]
        spy_data = {datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"): p 
                    for t, p in zip(spy_res["timestamp"], spy_res["indicators"]["quote"][0]["close"]) if p}
        sorted_dates = sorted(spy_data.keys())

        # 2. 深度回测计算
        equity = [100.0]
        rets, model_map = [], {}
        win, total = 0, 0

        for p in sorted(preds, key=lambda x: x.get("date", "")[:10]):
            d = p.get("date", "")[:10]
            match_date = next((dt for dt in sorted_dates if dt >= d), None)
            
            if match_date:
                idx = sorted_dates.index(match_date)
                hold = int(p.get("hold_days", 1))
                if idx + hold < len(sorted_dates):
                    p1, p2 = spy_data[sorted_dates[idx]], spy_data[sorted_dates[idx+hold]]
                    raw_diff = (p2 - p1) / p1
                    
                    # 信号解析
                    sig = p.get("direction", p.get("signal", "BULLISH")).upper()
                    actual_ret = raw_diff if "BULL" in sig else -raw_diff
                    
                    total += 1
                    if actual_ret > 0: win += 1
                    rets.append(actual_ret)
                    equity.append(equity[-1] * (1 + actual_ret))
                    
                    # 模型排行统计
                    m_id = p.get("model", "Unknown")
                    m = model_map.setdefault(m_id, {"win":0, "n":0, "rets":[]})
                    m["n"] += 1
                    if actual_ret > 0: m["win"] += 1
                    m["rets"].append(actual_ret)

        # 3. 指标计算
        wr = win / total if total > 0 else 0
        cum_ret = (equity[-1] / 100.0) - 1
        sharpe = (mean(rets) / stdev(rets) * math.sqrt(252)) if len(rets) > 1 else 0
        z_score = (wr - 0.5) / math.sqrt(0.25 / total) if total > 0 else 0

        # 4. 生成专业级深色 UI
        model_rows = ""
        for mid, d in sorted(model_map.items(), key=lambda x: x[1]['win']/x[1]['n'], reverse=True):
            m_wr = d["win"]/d["n"]
            m_ret = mean(d["rets"])
            color = "#00e5a0" if m_wr >= 0.5 else "#ff4d6a"
            model_rows += f"""
            <tr>
                <td style="color:#8aa4b8;">{mid}</td>
                <td>{d['n']}</td>
                <td style="color:{color}; font-weight:bold;">{m_wr:.1%}</td>
                <td style="text-align:right; color:{color};">{m_ret:+.3%}</td>
            </tr>"""

        update_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        html = f"""
        <!DOCTYPE html><html><head><meta charset="UTF-8">
        <style>
            body {{ background:#080c10; color:#c8daea; font-family:sans-serif; margin:0; padding:20px; font-size:13px; }}
            .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:#1e2d3d; border:1px solid #1e2d3d; margin-bottom:20px; }}
            .kpi {{ background:#0d1318; padding:20px; }}
            .val {{ font-size:32px; font-weight:bold; font-family:monospace; margin-top:5px; color:#00e5a0; }}
            .lab {{ color:#8aa4b8; font-size:11px; text-transform:uppercase; }}
            table {{ width:100%; border-collapse:collapse; background:#0d1318; }}
            td, th {{ padding:12px; border-bottom:1px solid #1e2d3d; text-align:left; }}
            th {{ color:#4a6178; font-size:10px; }}
        </style></head><body>
        <div style="display:flex; justify-content:space-between; margin-bottom:20px;">
            <span style="color:#00e5a0; font-weight:bold;">TRUMP/CODE PROFESSIONAL MONITOR</span>
            <span style="color:#4a6178;">LAST SYNC: {update_time} UTC</span>
        </div>
        <div class="grid">
            <div class="kpi"><div class="lab">真实胜率</div><div class="val">{wr:.1%}</div></div>
            <div class="kpi"><div class="lab">显著性 Z-SCORE</div><div class="val">{z_score:+.2f}</div></div>
            <div class="kpi"><div class="lab">模拟累计收益</div><div class="val" style="color:{"#00e5a0" if cum_ret>0 else "#ff4d6a"};">{cum_ret:+.2%}</div></div>
            <div class="kpi"><div class="lab">SHARPE 年化</div><div class="val" style="color:#3d9eff;">{sharpe:.2f}</div></div>
        </div>
        <table>
            <tr><th>模型 ID</th><th>样本数</th><th>胜率</th><th style="text-align:right">平均单笔回报</th></tr>
            {model_rows}
        </table>
        </body></html>
        """
        
        # 写入两个位置确保 Pages 绝对更新
        Path("trump_dashboard.html").write_text(html, encoding="utf-8")
        if Path("docs").exists():
            (Path("docs") / "index.html").write_text(html, encoding="utf-8")

    except Exception as e:
        log.error(f"Error: {e}")

if __name__ == "__main__":
    main()
