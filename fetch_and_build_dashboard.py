import json, math, sys, logging, ssl, urllib.request, os
from pathlib import Path
from datetime import datetime, timezone
from statistics import mean, stdev

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# 离线环境/Actions 证书配置
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def fetch_data(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as r:
        return r.read().decode('utf-8')

def main():
    try:
        # 1. 下载最新预测
        log.info("正在获取预测日志...")
        preds_json = fetch_data("https://raw.githubusercontent.com/sstklen/trump-code/main/data/predictions_log.json")
        preds_raw = json.loads(preds_json)
        preds = preds_raw if isinstance(preds_raw, list) else [{**v, "date": k} for k, v in preds_raw.items()]

        # 2. 获取 SPY 市场数据
        log.info("正在获取 SPY 历史价格...")
        spy_json = fetch_data("https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=2y")
        spy_res = json.loads(spy_json)["chart"]["result"][0]
        ts, prices = spy_res["timestamp"], spy_res["indicators"]["quote"][0]["close"]
        spy_data = {datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"): p for t, p in zip(ts, prices) if p}
        sorted_dates = sorted(spy_data.keys())

        # 3. 回测逻辑（核心修复：自动处理非交易日）
        equity = [100.0]
        returns = []
        
        for p in sorted(preds, key=lambda x: x.get("date", "")[:10]):
            d = p.get("date", "")[:10]
            # 找到大于或等于预测日期的第一个交易日
            match_date = next((dt for dt in sorted_dates if dt >= d), None)
            if not match_date: continue
            
            idx = sorted_dates.index(match_date)
            hold = int(p.get("hold_days", 1))
            
            if idx + hold < len(sorted_dates):
                p_start = spy_data[sorted_dates[idx]]
                p_end = spy_data[sorted_dates[idx + hold]]
                
                raw_diff = (p_end - p_start) / p_start
                signal = p.get("direction", "BULLISH").upper()
                actual_ret = raw_diff if "BULL" in signal else -raw_diff
                
                returns.append(actual_ret)
                equity.append(equity[-1] * (1 + actual_ret))

        # 4. 指标计算
        cum_ret = (equity[-1] / 100.0) - 1
        vol = stdev(returns) if len(returns) > 1 else 0
        sharpe = (mean(returns) / vol * math.sqrt(252)) if vol > 0 else 0
        
        # 5. 生成精简看板（用于验证更新）
        update_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        html = f"""
        <!DOCTYPE html><html><head><meta charset="UTF-8">
        <style>
            body {{ background:#080c10; color:#00e5a0; font-family:sans-serif; text-align:center; padding-top:100px; }}
            .card {{ background:#0d1318; display:inline-block; padding:40px; border:1px solid #1e2d3d; border-radius:10px; }}
            .val {{ font-size:48px; font-weight:bold; margin:10px 0; color:#3d9eff; }}
        </style></head><body>
            <div class="card">
                <h2 style="color:#8aa4b8;">TRUMP CODE 实时回测</h2>
                <p>同步时间: {update_time} UTC</p>
                <hr style="border-color:#1e2d3d">
                <div>模拟累计收益</div><div class="val">{cum_ret:+.2%}</div>
                <div>Sharpe 年化</div><div class="val">{sharpe:.2f}</div>
                <p style="color:#4a6178;">基于 {len(returns)} 次有效信号匹配</p>
            </div>
        </body></html>
        """
        Path("trump_dashboard.html").write_text(html, encoding="utf-8")
        log.info(f"✅ 看板构建成功！收益率: {cum_ret:.2%}")

    except Exception as e:
        log.error(f"❌ 运行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
