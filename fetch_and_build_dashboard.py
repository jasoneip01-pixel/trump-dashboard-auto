import json, math, random, time, sys, logging, ssl, urllib.request, warnings, os
from pathlib import Path
from datetime import datetime, timezone
from statistics import mean, stdev
import bisect

# 1. 基础配置
logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)

RAW = "https://raw.githubusercontent.com/sstklen/trump-code/main"
FILES = {
    "predictions_log.json": f"{RAW}/data/predictions_log.json",
    "daily_report.json": f"{RAW}/data/daily_report.json"
}

def fetch_json(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            return r.read().decode('utf-8')
    except Exception as e:
        log.error(f"下载失败: {url} -> {e}")
        return None

def wilson_score(c, n, z=1.96):
    if n == 0: return 0, 1
    p = c / n
    d = 1 + z**2/n
    center = (p + z**2/(2*n))/d
    msg = z * math.sqrt(p*(1-p)/n + z**2/(4*n**2))/d
    return max(0, center - msg), min(1, center + msg)

def main():
    log.info("🚀 开始同步数据...")
    # 下载核心 JSON
    for fname, url in FILES.items():
        content = fetch_json(url)
        if content: (DATA_DIR / fname).write_text(content, encoding="utf-8")

    # 抓取 SPY 价格数据 (2年范围确保覆盖所有回测点)
    spy_url = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=2y"
    spy_content = fetch_json(spy_url)
    if not spy_content: 
        log.error("无法获取市场数据，退出")
        return
    
    spy_raw = json.loads(spy_content)
    res = spy_raw["chart"]["result"][0]
    ts, close = res["timestamp"], res["indicators"]["quote"][0]["close"]
    spy_dict = {datetime.fromtimestamp(t).strftime("%Y-%m-%d"): round(float(c), 4) 
                for t, c in zip(ts, close) if c is not None}
    sorted_dates = sorted(spy_dict.keys())

    # --- 回测计算逻辑 ---
    preds_raw = json.loads((DATA_DIR / "predictions_log.json").read_text(encoding="utf-8"))
    preds = preds_raw if isinstance(preds_raw, list) else [{**v, "date": k} for k, v in preds_raw.items()]
    
    equity = [100.0]
    rets, results_by_model = [], {}
    correct, total = 0, 0

    # 按时间排序预测记录
    for p in sorted(preds, key=lambda x: x.get("date", "")[:10]):
        d_str = p.get("date", "")[:10]
        if not d_str: continue
        
        # 核心修复：寻找最近的交易日
        idx = bisect.bisect_left(sorted_dates, d_str)
        hold = int(p.get("hold_days", 1))
        
        if idx + hold < len(sorted_dates):
            p1 = spy_dict[sorted_dates[idx]]
            p2 = spy_dict[sorted_dates[idx + hold]]
            raw_ret = (p2 - p1) / p1
            
            sig = p.get("direction", p.get("signal", "BULLISH"))
            actual_ret = raw_ret if sig == "BULLISH" else -raw_ret
            
            total += 1
            is_ok = actual_ret > 0
            if is_ok: correct += 1
            
            rets.append(actual_ret)
            equity.append(equity[-1] * (1 + actual_ret))
            
            # 模型分组统计
            m_id = p.get("model", "Unknown")
            m_data = results_by_model.setdefault(m_id, {"c":0, "n":0, "rets":[]})
            m_data["n"] += 1
            if is_ok: m_data["c"] += 1
            m_data["rets"].append(actual_ret)

    if total == 0:
        log.warning("未匹配到任何有效交易日，请检查日期格式")
        return

    # 指标汇总
    wr = correct / total
    cum_ret = (equity[-1] / equity[0]) - 1
    avg_ret = mean(rets)
    std_ret = stdev(rets) if len(rets) > 1 else 0.0001
    sharpe = (avg_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0
    z_score = (wr - 0.5) / math.sqrt(0.25 / total)

    # --- UI 渲染数据准备 ---
    model_rows = ""
    for mid, d in sorted(results_by_model.items(), key=lambda x: x[1]['c']/x[1]['n'], reverse=True):
        m_wr = d["c"]/d["n"]
        lo, hi = wilson_score(d["c"], d["n"])
        m_ret = mean(d["rets"])
        color = "#00e5a0" if m_wr >= 0.55 else "#ff4d6a"
        model_rows += f"""
        <tr>
            <td style="color:#8aa4b8; font-family:monospace;">{mid}</td>
            <td>{d['n']}</td>
            <td style="color:{color}; font-weight:bold;">{m_wr:.1%}</td>
            <td style="font-size:11px; color:#4a6178;">{lo:.0%}–{hi:.0%}</td>
            <td style="text-align:right; color:{color};">{m_ret:+.3%}</td>
        </tr>"""

    # 读取日报摘要
    dr_path = DATA_DIR / "daily_report.json"
    dr = json.loads(dr_path.read_text(encoding="utf-8")) if dr_path.exists() else {}
    summary_zh = dr.get("summary", {}).get("zh", "数据同步中...")
    summary_en = dr.get("summary", {}).get("en", "Syncing...")

    # --- 最终 HTML 模板 ---
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8"><title>Trump Code Monitor</title>
    <style>
        body {{ background:#080c10; color:#c8daea; font-family:sans-serif; margin:0; padding:20px; font-size:13px; }}
        .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:#1e2d3d; border:1px solid #1e2d3d; margin-bottom:20px; }}
        .kpi {{ background:#0d1318; padding:20px; }}
        .val {{ font-size:32px; font-weight:bold; font-family:monospace; margin-top:5px; }}
        .lab {{ color:#8aa4b8; font-size:11px; text-transform:uppercase; }}
        table {{ width:100%; border-collapse:collapse; background:#0d1318; }}
        th {{ text-align:left; color:#4a6178; font-size:10px; padding:10px 5px; border-bottom:1px solid #1e2d3d; }}
        td {{ padding:10px 5px; border-bottom:1px solid #1e2d3d; }}
        .daily {{ background:#111820; padding:20px; border:1px solid #1e2d3d; border-radius:4px; line-height:1.6; }}
    </style>
    </head><body>
    <div style="display:flex; justify-content:space-between; margin-bottom:20px;">
        <span style="color:#00e5a0; font-weight:bold; font-family:monospace;">TRUMP/CODE REAL_DATA_BACKTEST</span>
        <span style="color:#4a6178; font-size:11px;">UPDATED: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")} UTC</span>
    </div>
    <div class="grid">
        <div class="kpi"><div class="lab">真实胜率</div><div class="val" style="color:#00e5a0;">{wr:.1%}</div></div>
        <div class="kpi"><div class="lab">显著性 Z-SCORE</div><div class="val" style="color:#00e5a0;">{z_score:+.2f}</div></div>
        <div class="kpi"><div class="lab">模拟累计收益</div><div class="val" style="color:{"#00e5a0" if cum_ret>0 else "#ff4d6a"};">{cum_ret:+.2%}</div></div>
        <div class="kpi"><div class="lab">SHARPE 年化</div><div class="val" style="color:#3d9eff;">{sharpe:.2f}</div></div>
    </div>
    <div style="display:grid; grid-template-columns: 2fr 1fr; gap:20px;">
        <div>
            <div class="lab" style="margin-bottom:10px;">模型回测排行榜 (基于真实标普500数据)</div>
            <table><tr><th>模型 ID</th><th>次数</th><th>胜率</th><th>95% CI</th><th style="text-align:right">平均回报</th></tr>{model_rows}</table>
        </div>
        <div>
            <div class="lab" style="margin-bottom:10px;">今日报告摘要</div>
            <div class="daily">
                <b style="color:#3d9eff;">ZH:</b> {summary_zh}<br><br>
                <b style="color:#3d9eff;">EN:</b> {summary_en}
            </div>
        </div>
    </div>
    </body></html>
    """
    (BASE_DIR / "trump_dashboard.html").write_text(html, encoding="utf-8")
    log.info("🎉 终极看板生成成功！指标已刷新。")

if __name__ == "__main__":
    main()
