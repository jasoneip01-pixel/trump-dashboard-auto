import json, math, random, time, sys, logging, ssl, urllib.request, warnings, os
from pathlib import Path
from datetime import datetime, timezone
from statistics import mean, stdev
import bisect

# 配置增强日志，方便在 GitHub Actions 页面查看
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# 确保路径存在
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
RESULTS_DIR = Path("paper_results")
RESULTS_DIR.mkdir(exist_ok=True)

# 数据源
RAW = "https://raw.githubusercontent.com/sstklen/trump-code/main"
FILES = {
    "predictions_log.json": f"{RAW}/data/predictions_log.json",
    "daily_report.json": f"{RAW}/data/daily_report.json"
}
TICKERS = {"market_SP500.json": "SPY"}

def get_ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c

def fetch_url(url):
    """极致兼容的下载函数"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    for i in range(3): # 增加重试机制
        try:
            with urllib.request.urlopen(req, context=get_ctx(), timeout=15) as r:
                return r.read().decode('utf-8')
        except Exception as e:
            log.warning(f"重试 {i+1}/3: {url} 失败: {e}")
            time.sleep(2)
    return None

def fetch_all():
    log.info("开始同步外部数据...")
    # 1. GitHub 数据
    for fname, url in FILES.items():
        content = fetch_url(url)
        if content:
            (DATA_DIR / fname).write_text(content, encoding="utf-8")
            log.info(f"成功同步: {fname}")
            
    # 2. Yahoo Finance 数据
    for fname, ticker in TICKERS.items():
        y_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2y"
        content = fetch_url(y_url)
        if content:
            raw = json.loads(content)
            res = raw["chart"]["result"][0]
            ts, close = res["timestamp"], res["indicators"]["quote"][0]["close"]
            out = {datetime.fromtimestamp(t).strftime("%Y-%m-%d"): {"close": round(float(c), 4)} 
                   for t, c in zip(ts, close) if c is not None}
            (DATA_DIR / fname).write_text(json.dumps(out, indent=2))
            log.info(f"成功同步市场数据: {ticker}")

def backtest():
    log.info("开始回测计算...")
    plog_path = DATA_DIR / "predictions_log.json"
    spy_path = DATA_DIR / "market_SP500.json"
    
    if not (plog_path.exists() and spy_path.exists()):
        log.error("缺失关键数据文件，无法回测")
        return None

    preds = json.loads(plog_path.read_text(encoding="utf-8"))
    if not isinstance(preds, list): # 兼容字典格式
        preds = [{**v, "date": k} for k, v in preds.items() if isinstance(v, dict)]
    
    spy = json.loads(spy_path.read_text())
    sorted_dates = sorted(spy.keys())
    
    rets, equity = [], [100.0]
    correct, total = 0, 0
    
    for p in sorted(preds, key=lambda x: x.get("date", "")[:10]):
        d_str = p.get("date", "")[:10]
        if not d_str: continue
        
        idx = bisect.bisect_left(sorted_dates, d_str)
        hold = int(p.get("hold_days", 1))
        
        if idx + hold < len(sorted_dates):
            p1 = spy[sorted_dates[idx]]["close"]
            p2 = spy[sorted_dates[idx+hold]]["close"]
            ret = (p2 - p1) / p1
            
            signal = p.get("direction", p.get("signal", "BULLISH"))
            actual_ret = ret if signal == "BULLISH" else -ret
            
            total += 1
            if actual_ret > 0: correct += 1
            rets.append(actual_ret)
            equity.append(equity[-1] * (1 + actual_ret))

    if total == 0: return None
    
    wr = correct / total
    avg = mean(rets)
    std = stdev(rets) if len(rets) > 1 else 0.001
    sharpe = (avg / std * math.sqrt(252)) if std > 0 else 0
    
    return {
        "win_rate": f"{wr:.1%}",
        "cumulative": f"{(equity[-1]/equity[0]-1):+.2%}",
        "sharpe": round(sharpe, 2),
        "equity_curve": [round(v, 2) for v in equity],
        "total": total,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

def build_html(stats):
    # 极简看板 HTML
    html = f"""
    <html><body style="background:#080c10;color:#c8daea;font-family:sans-serif;padding:40px;">
    <h1>Trump Code Real-Data Monitor</h1>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin:20px 0;">
        <div style="background:#0d1318;padding:20px;border-radius:8px;border:1px solid #1e2d3d;">
            <div style="color:#8aa4b8;font-size:12px;">胜率</div><div style="font-size:24px;color:#00e5a0;">{stats['win_rate']}</div>
        </div>
        <div style="background:#0d1318;padding:20px;border-radius:8px;border:1px solid #1e2d3d;">
            <div style="color:#8aa4b8;font-size:12px;">累计收益</div><div style="font-size:24px;color:#00e5a0;">{stats['cumulative']}</div>
        </div>
        <div style="background:#0d1318;padding:20px;border-radius:8px;border:1px solid #1e2d3d;">
            <div style="color:#8aa4b8;font-size:12px;">夏普比率</div><div style="font-size:24px;color:#3d9eff;">{stats['sharpe']}</div>
        </div>
        <div style="background:#0d1318;padding:20px;border-radius:8px;border:1px solid #1e2d3d;">
            <div style="color:#8aa4b8;font-size:12px;">信号总数</div><div style="font-size:24px;">{stats['total']}</div>
        </div>
    </div>
    <p style="color:#4a6178;font-size:11px;">最后更新: {stats['updated_at']} UTC</p>
    </body></html>
    """
    Path("trump_dashboard.html").write_text(html, encoding="utf-8")

if __name__ == "__main__":
    try:
        fetch_all()
        results = backtest()
        if results:
            build_html(results)
            log.info("🎉 所有任务完成，看板已生成")
        else:
            log.warning("没有匹配到有效的回测信号")
    except Exception as e:
        log.error(f"脚本运行崩溃: {e}")
        sys.exit(1) # 显式告知 GitHub Actions 运行失败
