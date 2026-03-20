import os, yfinance as yf, pandas as pd, numpy as np, requests
from datetime import datetime

# --- [自驾引擎核心配置] ---
# 逻辑：如果新闻中出现 KEY，则执行 ACTION
LOGIC_ENGINE = {
    "TARIFF": {"ticker": "YANG", "action": "BUY", "desc": "关税风险，做空中国资产"},
    "TAX": {"ticker": "IWM", "action": "BUY", "desc": "减税预期，做多美国小盘股"},
    "CRYPTO": {"ticker": "BTC-USD", "action": "BUY", "desc": "政策放宽，做多比特币"},
    "INFLATION": {"ticker": "GLD", "action": "BUY", "desc": "通胀预期，买入黄金对冲"}
}

def run_engine():
    api_key = os.getenv("ALPHAVANTAGE_API_KEY", "DEMO")
    # 监控池
    watch_list = ["SPY", "IWM", "FXI", "BTC-USD", "YANG", "GLD"]
    
    try:
        # 1. 抓取市场数据
        data = yf.download(watch_list, period="1mo", interval="1d")['Close'].ffill()
        returns = data.pct_change().dropna()

        # 2. 抓取实时新闻 (AlphaVantage 情绪流)
        news_url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&limit=15&apikey={api_key}"
        news_data = requests.get(news_url).json().get("feed", [])
        
        # 3. 情绪分析与信号触发
        active_signals = []
        headline_pool = " ".join([n['title'].upper() for n in news_data])
        
        for key, config in LOGIC_ENGINE.items():
            if key in headline_pool:
                active_signals.append(config)
        
        # 4. 自动计算模拟收益 (此处为自驾逻辑：根据信号调仓)
        if active_signals:
            # 简单等权自驾策略
            strat_rets = sum([returns[s['ticker']] for s in active_signals]) / len(active_signals)
        else:
            # 无信号时默认持仓大盘
            strat_rets = returns['SPY']

        cum_ret = (1 + strat_rets).cumprod()
        
        return {
            "perf": f"{(cum_ret.iloc[-1]-1)*100:+.2f}%",
            "sharpe": f"{(strat_rets.mean()*252)/(strat_rets.std()*np.sqrt(252)):.2f}",
            "mdd": f"{((cum_ret / cum_ret.cummax()) - 1).min()*100:.2f}%",
            "signals": active_signals if active_signals else [{"ticker":"CASH","action":"HOLD","desc":"暂无高置信度机会"}],
            "update": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
    except Exception as e:
        print(f"Engine Error: {e}")
        return None

def generate_mobile_ui(d):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            :root {{ --neon: #00FF66; --bg: #000; --amber: #FFB800; }}
            body {{ background: var(--bg); color: var(--neon); font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 15px; margin: 0; }}
            .card {{ background: #0A0A0A; border: 1px solid #1A1A1A; padding: 15px; border-radius: 8px; margin-bottom: 12px; }}
            .header {{ font-size: 12px; color: #444; margin-bottom: 20px; display: flex; justify-content: space-between; }}
            .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
            .val {{ font-size: 24px; font-weight: 800; margin-top: 5px; }}
            .label {{ font-size: 10px; color: #666; text-transform: uppercase; }}
            .signal-item {{ border-left: 3px solid var(--amber); padding-left: 12px; margin: 15px 0; }}
            .action-btn {{ background: var(--amber); color: black; padding: 2px 6px; font-size: 10px; font-weight: bold; border-radius: 3px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <b>AUTONOMOUS ENGINE V11.0</b>
            <span>{d['update']}</span>
        </div>
        <div class="stat-grid">
            <div class="card"><div class="label">自驾收益</div><div class="val">{d['perf']}</div></div>
            <div class="card"><div class="label">夏普比率</div><div class="val" style="color:#fff">{d['sharpe']}</div></div>
        </div>
        <div class="card">
            <div class="label" style="color:var(--amber)">当前执行指令 (Auto-Signals)</div>
            {"".join([f"<div class='signal-item'><span class='action-btn'>{s['action']}</span> <b>{s['ticker']}</b><br><small style='color:#888'>{s['desc']}</small></div>" for s in d['signals']])}
        </div>
        <div class="card" style="border-color: #333;">
            <div class="label">风险监控 (MDD)</div>
            <div class="val" style="color:#FF3333; font-size:18px;">{d['mdd']}</div>
            <div style="font-size:10px; color:#333; margin-top:10px;">适配: iPhone 17 / Huawei Mate / Android</div>
        </div>
    </body>
    </html>
    """
    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == "__main__":
    result = run_engine()
    if result: generate_mobile_ui(result)
