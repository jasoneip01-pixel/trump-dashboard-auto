import json, math, random, time, sys, logging, ssl, urllib.request, warnings, os
from pathlib import Path
from datetime import datetime, timezone, timedelta
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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            return r.read().decode('utf-8')
    except Exception as e:
        log.error(f"下载失败: {url} -> {e}")
        return None

def main():
    log.info("🚀 启动深度数据对齐流程...")
    
    # 同步 GitHub 数据
    for fname, url in FILES.items():
        content = fetch_json(url)
        if content: (DATA_DIR / fname).write_text(content, encoding="utf-8")

    # 同步市场数据 (SPY)
    spy_url = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=2y"
    spy_content = fetch_json(spy_url)
    if not spy_content: return
    
    res = json.loads(spy_content)["chart"]["result"][0]
    ts, close = res["timestamp"], res["indicators"]["quote"][0]["close"]
    # 修正时区问题：统一处理为 UTC 日期
    spy_dict = {}
    for t, c in zip(ts, close):
        if c is not None:
            d = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
            spy_dict[d] = round(float(c), 4)
    
    sorted_dates = sorted(spy_dict.keys())
    log.info(f"市场数据加载完毕: {len(sorted_dates)} 天记录 (最新: {sorted_dates[-1]})")

    # 处理预测数据
    preds_raw = json.loads((DATA_DIR / "predictions_log.json").read_text(encoding="utf-8"))
    preds = preds_raw if isinstance(preds_raw, list) else [{**v, "date": k} for k, v in preds_raw.items()]
    
    equity = [100.0]; rets = []; model_stats = {}
    correct = total = match_fail = 0

    for p in sorted(preds, key=lambda x: x.get("date", "")[:10]):
        d_str = p.get("date", "")[:10]
        if not d_str: continue
        
        # 核心逻辑：如果在周末，寻找后序第一个交易日
        idx = bisect.bisect_left(sorted_dates, d_str)
        hold = int(p.get("hold_days", 1))
        
        if idx + hold < len(sorted_dates):
            p1 = spy_dict[sorted_dates[idx]]
            p2 = spy_dict[sorted_dates[idx + hold]]
            raw_ret = (p2 - p1) / p1
            
            sig = p.get("direction", p.get("signal", "BULLISH"))
            actual_ret = raw_ret if "BULL" in sig.upper() else -raw_ret
            
            total += 1
            if actual_ret > 0: correct += 1
            rets.append(actual_ret)
            equity.append(equity[-1] * (1 + actual_ret))
            
            # 模型分组
            m_id = p.get("model", "Unknown")
            m_data = model_stats.setdefault(m_id, {"c":0, "n":0, "r":[]})
            m_data["n"] += 1
            if actual_ret > 0: m_data["c"] += 1
            m_data["r"].append(actual_ret)
        else:
            match_fail += 1

    log.info(f"计算完成: 成功匹配 {total} 条, 失败 {match_fail} 条 (因日期太新或超出范围)")

    # 指标计算
    if total > 0:
        wr = correct / total
        cum_ret = (equity[-1] / equity[0]) - 1
        avg_ret = mean(rets)
        std_ret = stdev(rets) if len(rets) > 1 else 0.0001
        sharpe = (avg_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0
        z_score = (wr - 0.5) / math.sqrt(0.25 / total)
    else:
        wr = cum_ret = sharpe = z_score = 0

    # 生成 HTML (复刻原版深色 UI)
    model_rows = ""
    for mid, d in sorted(model_stats.items(), key=lambda x: x[1]['c']/x[1]['n'] if x[1]['n']>0 else 0, reverse=True):
        m_wr = d["c"]/d["n"]
        m_ret = mean(d["r"])
        color = "#00e5a0" if m_wr >= 0.55 else "#ff4d6a"
        model_rows += f"<tr><td>{mid}</td><td>{d['n']}</td><td style='color:{color}'>{m_wr:.1%}</td><td style='text-align:right;color:{color}'>{m_ret:+.3%}</td></tr>"

    # 读取日报
    dr = json.loads((DATA_DIR/"daily_report.json").read_text(encoding="utf-8")) if (DATA_DIR/"daily_report.json").exists() else {}
    
    html_template = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8"><style>
        body {{ background:#080c10; color:#c8daea; font-family:sans-serif; padding:20px; }}
        .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:#1e2d3d; margin-bottom:20px; }}
        .kpi {{ background:#0d1318; padding:20px; }}
        .val {{ font-size:32px; font-weight:bold; font-family:monospace; margin-top:5px; color:#00e5a0; }}
        table {{ width:100%; border-collapse:collapse; background:#0d1318; }}
        td, th {{ padding:12px; border-bottom:1px solid #1e2d3d; text-align:left; }}
    </style></head><body>
    <div style="margin-bottom:20px; font-weight:bold; color:#00e5a0;">TRUMP CODE MONITOR (REAL DATA)</div>
    <div class="grid">
        <div class="kpi">胜率<div class="val">{wr:.1%}</div></div>
        <div class="kpi">Z-SCORE<div class="val">{z_score:+.2f}</div></div>
        <div class="kpi">模拟累计收益<div class="val" style="color:{"#00e5a0" if cum_ret>=0 else "#ff4d6a"}">{cum_ret:+.2%}</div></div>
        <div class="kpi">SHARPE 年化<div class="val" style="color:#3d9eff;">{sharpe:.2f}</div></div>
    </div>
    <div style="display:grid; grid-template-columns: 2fr 1fr; gap:20px;">
        <table><tr><th>模型</th><th>次数</th><th>胜率</th><th style="text-align:right">回报</th></tr>{model_rows}</table>
        <div style="background:#111820; padding:20px; border:1px solid #1e2d3d;">
            <b>今日摘要:</b><br><br>{dr.get('summary', {}).get('zh', '同步中...')}
        </div>
    </div>
    </body></html>
    """
    (BASE_DIR / "trump_dashboard.html").write_text(html_template, encoding="utf-8")
    log.info("🎉 修复版看板已生成！")

if __name__ == "__main__":
    main()
