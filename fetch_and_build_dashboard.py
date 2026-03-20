import json, math, sys, logging, ssl, urllib.request, os
from pathlib import Path
from datetime import datetime, timezone
from statistics import mean, stdev

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# 证书脱敏
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def fetch_data(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as r:
        return r.read().decode('utf-8')

def main():
    try:
        # 1. 获取预测数据
        log.info("Step 1: Fetching predictions...")
        preds_json = fetch_data("https://raw.githubusercontent.com/sstklen/trump-code/main/data/predictions_log.json")
        preds_raw = json.loads(preds_json)
        preds = preds_raw if isinstance(preds_raw, list) else [{**v, "date": k} for k, v in preds_raw.items()]

        # 2. 获取 SPY 价格
        log.info("Step 2: Fetching SPY prices...")
        spy_json = fetch_data("https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=2y")
        spy_res = json.loads(spy_json)["chart"]["result"][0]
        ts = spy_res["timestamp"]
        prices = spy_res["indicators"]["quote"][0]["close"]
        # 建立日期索引
        spy_data = {datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"): p for t, p in zip(ts, prices) if p}
        sorted_dates = sorted(spy_data.keys())
        log.info(f"Loaded {len(sorted_dates)} days of SPY data.")

        # 3. 计算收益
        equity = [100.0]
        returns = []
        matched_count = 0
        
        for p in sorted(preds, key=lambda x: x.get("date", "")[:10]):
            d = p.get("date", "")[:10]
            # 寻找当天或之后的第一个交易日
            match_date = next((dt for dt in sorted_dates if dt >= d), None)
            
            if match_date:
                idx = sorted_dates.index(match_date)
                hold = int(p.get("hold_days", 1))
                if idx + hold < len(sorted_dates):
                    p_start = spy_data[sorted_dates[idx]]
                    p_end = spy_data[sorted_dates[idx + hold]]
                    
                    change = (p_end - p_start) / p_start
                    signal = p.get("direction", p.get("signal", "BULLISH")).upper()
                    actual_ret = change if "BULL" in signal else -change
                    
                    returns.append(actual_ret)
                    equity.append(equity[-1] * (1 + actual_ret))
                    matched_count += 1

        # 4. 指标汇总
        cum_ret = (equity[-1] / 100.0) - 1 if equity else 0
        vol = stdev(returns) if len(returns) > 1 else 0
        sharpe = (mean(returns) / vol * math.sqrt(252)) if vol > 0 else 0
        
        log.info(f"Summary: Matched {matched_count} predictions. CumRet: {cum_ret:.2%}")

        # 5. 生成 HTML (同时存放在根目录和 docs/ 目录，双重保险)
        update_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        html_content = f"""
        <!DOCTYPE html><html><head><meta charset="UTF-8"><title>FIXED DATA</title>
        <style>
            body {{ background:#080c10; color:#00e5a0; font-family:monospace; padding:50px; line-height:1.5; }}
            .box {{ border: 2px solid #3d9eff; padding: 20px; display: inline-block; }}
            .big {{ font-size: 48px; color: #fff; }}
        </style></head><body>
            <div class="box">
                <h2>TRUMP CODE DEBUG BOARD</h2>
                <p>LAST UPDATE: {update_time} UTC</p>
                <hr>
                <div>MATCHED TRADES: {matched_count}</div>
                <div>CUMULATIVE RETURN: <span class="big">{cum_ret:+.2%}</span></div>
                <div>ANNUAL SHARPE: <span class="big">{sharpe:.2f}</span></div>
            </div>
        </body></html>
        """
        
        # 写入根目录
        Path("trump_dashboard.html").write_text(html_content, encoding="utf-8")
        # 写入 docs 目录 (因为你的截图里有一个 docs 文件夹，Pages 极有可能在那)
        docs_dir = Path("docs")
        if docs_dir.exists():
            (docs_dir / "index.html").write_text(html_content, encoding="utf-8")
            (docs_dir / "trump_dashboard.html").write_text(html_content, encoding="utf-8")

    except Exception as e:
        log.error(f"FATAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
