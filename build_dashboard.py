import os, yfinance as yf, pandas as pd, numpy as np, requests
from datetime import datetime

# --- [1. 核心模型胜率矩阵：你的决策底牌] ---
SUB_MODELS = [
    {"id": "A3", "name": "relief_rocket", "win": 0.727, "asset": "IWM", "risk": "低"},
    {"id": "D3", "name": "volume_spike", "win": 0.702, "asset": "BTC", "risk": "高"},
    {"id": "D2", "name": "sig_change", "win": 0.700, "asset": "FXI", "risk": "中"},
    {"id": "B3", "name": "action_pre", "win": 0.667, "asset": "TSLA", "risk": "高"},
    {"id": "C1", "name": "burst_silence", "win": 0.650, "asset": "SPY", "risk": "低"},
    {"id": "B1", "name": "triple_signal", "win": 0.647, "asset": "GLD", "risk": "中"}
]

# --- [2. 自动化自驾引擎逻辑] ---
OPPORTUNITY_MAP = {
    "TARIFF": {"tk": "YANG", "dir": "LONG", "desc": "关税升级预期 -> 做空中国资产"},
    "TAX": {"tk": "IWM", "dir": "LONG", "desc": "减税政策利好 -> 做多美国小盘股"},
    "CRYPTO": {"tk": "BITO", "dir": "LONG", "desc": "监管环境转暖 -> 加仓加密货币"},
    "CHINA": {"tk": "FXI", "dir": "SHORT", "desc": "对华限制加强 -> 减少中概暴露"}
}

def get_market_intelligence():
    api_key = os.getenv("ALPHAVANTAGE_API_KEY", "DEMO")
    tickers = ["SPY", "IWM", "FXI", "BTC-USD", "GLD", "YANG"]
    try:
        # 抓取真实市场数据
        data = yf.download(tickers, period="3mo", interval="1d")['Close'].ffill()
        rets = data.pct_change().dropna()

        # 情绪扫描
        news_api = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&limit=15&apikey={api_key}"
        res = requests.get(news_api).json().get("feed", [])
        
        signals = []
        news_text = "等待市场信号穿透..."
        if res:
            news_text = res[0]['title']
            full_content = " ".join([n['title'].upper() for n in res])
            for k, v in OPPORTUNITY_MAP.items():
                if k in full_content: signals.append(v)

        # 自驾引擎收益逻辑：信号驱动调仓
        if signals:
            active_ret = sum([rets[s['tk']] * (1 if s['dir']=="LONG" else -1) for s in signals]) / len(signals)
        else:
            active_ret = rets['SPY'] # 默认基准

        cum_ret = (1 + active_ret).cumprod()
        
        return {
            "ret": f"{(cum_ret.iloc[-1]-1)*100:+.2f}%",
            "sharpe": f"{(active_ret.mean()*252)/(active_ret.std()*np.sqrt(252)):.2f}",
            "mdd": f"{((cum_ret / cum_ret.cummax()) - 1).min()*100:.2f}%",
            "signals": signals if signals else [{"tk":"CASH", "dir":"WAIT", "desc":"震荡市，现金避险"}],
            "news": news_text,
            "update": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {"error": str(e)}

def render_terminal(d):
    html = f"""
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            :root {{ --neon: #00FF66; --bg: #050505; --amber: #FFB800; --red: #FF3333; }}
            body {{ background: var(--bg); color: var(--neon); font-family: 'Courier New', monospace; padding: 15px; margin: 0; }}
            .box {{ background: #0D0D0D; border: 1px solid #1A1A1A; padding: 12px; margin-bottom: 10px; border-radius: 4px; }}
            .header {{ border-bottom: 2px solid var(--neon); padding-bottom: 10px; display: flex; justify-content: space-between; font-weight: bold; }}
            .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; }}
            .label {{ color: #555; font-size: 10px; text-transform: uppercase; }}
            .val {{ font-size: 22px; font-weight: bold; }}
            .signal-item {{ border-left: 3px solid var(--amber); padding-left: 10px; margin: 10px 0; font-size: 13px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }}
            th {{ text-align: left; color: #444; border-bottom: 1px solid #1A1A1A; padding-bottom: 5px; }}
            td {{ padding: 8px 0; border-bottom: 1px solid #111; }}
        </style>
    </head>
    <body>
        <div class="header">
            <span>TRUMP_CODE INTELLIGENCE V13.0</span>
            <span style="font-size:10px;">{d['update']} UTC</span>
        </div>

        <div class="stat-grid">
            <div class="box"><div class="label">自驾引擎收益</div><div class="val">{d['ret']}</div></div>
            <div class="box"><div class="label">夏普比率</div><div class="val" style="color:white">{d['sharpe']}</div></div>
        </div>

        <div class="box">
            <div class="label" style="color:var(--amber)">● 机会识别与自动调仓指令</div>
            {"".join([f"<div class='signal-item'><b>{s['tk']} | {s['dir']}</b><br><span style='color:#888'>{s['desc']}</span></div>" for s in d['signals']])}
        </div>

        <div class="box">
            <div class="label">情报流摘要</div>
            <div style="font-size:12px; color:white; margin-top:5px;">{d['news']}</div>
        </div>

        <div class="box">
            <div class="label">子模型全量监控矩阵 (A3-C1)</div>
            <table>
                <thead><tr><th>ID</th><th>胜率</th><th>映射资产</th><th>风险</th></tr></thead>
                <tbody>
                    {"".join([f"<tr><td>{m['id']}_{m['name']}</td><td style='color:var(--neon)'>{m['win']*100}%</td><td>{m['asset']}</td><td>{m['risk']}</td></tr>" for m in SUB_MODELS])}
                </tbody>
            </table>
        </div>

        <div class="box" style="border-color:var(--red)">
            <div class="label" style="color:var(--red)">风控模型 (MDD CONTROL)</div>
            <div class="val" style="color:var(--red)">{d['mdd']}</div>
        </div>
    </body>
    </html>
    """
    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == "__main__":
    intelligence = get_market_intelligence()
    if "error" not in intelligence:
        render_terminal(intelligence)
    else:
        print(f"FAILED: {intelligence['error']}")
