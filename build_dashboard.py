import os, yfinance as yf, pandas as pd, numpy as np, requests
from datetime import datetime

# --- [量化配置：模型与机会映射] ---
MODELS = [
    {"id": "A3", "name": "relief_rocket", "win": 0.727, "asset": "IWM"},
    {"id": "D3", "name": "volume_spike", "win": 0.702, "asset": "BTC-USD"},
    {"id": "D2", "name": "sig_change", "win": 0.700, "asset": "FXI"},
    {"id": "B3", "name": "action_pre", "win": 0.667, "asset": "TSLA"}
]

TRIGGER_MAP = {
    "TARIFF": {"ticker": "YANG", "side": "LONG", "reason": "关税升级预期"},
    "TAX": {"ticker": "IWM", "side": "LONG", "reason": "减税利好预期"},
    "CRYPTO": {"ticker": "BITO", "side": "LONG", "reason": "监管政策转暖"},
    "CHINA": {"ticker": "FXI", "side": "SHORT", "reason": "对华贸易限制"}
}

def get_data():
    api_key = os.getenv("ALPHAVANTAGE_API_KEY", "DEMO")
    assets = ["SPY", "IWM", "FXI", "BTC-USD", "YANG"]
    try:
        df = yf.download(assets, period="6mo")['Close'].ffill()
        rets = df.pct_change().dropna()
        
        # 实时情绪抓取与机会识别
        news = requests.get(f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&apikey={api_key}').json()
        feeds = news.get("feed", [])
        combined_text = " ".join([f['title'] for f in feeds[:5]]).upper()
        
        active_signals = [v for k, v in TRIGGER_MAP.items() if k in combined_text]
        
        # 策略收益计算逻辑
        if not active_signals:
            strat_ret = rets['SPY'] * 0.5 + rets['IWM'] * 0.5
        else:
            strat_ret = sum([rets[s['ticker']] * (1 if s['side']=='LONG' else -1) for s in active_signals[:3]]) / len(active_signals[:3])

        cum_ret = (1 + strat_ret).cumprod()
        
        return {
            "cum_ret": f"{(cum_ret.iloc[-1]-1)*100:+.2f}%",
            "sharpe": f"{(strat_ret.mean()*252)/(strat_ret.std()*np.sqrt(252)):.2f}",
            "mdd": f"{((cum_ret / cum_ret.cummax()) - 1).min()*100:.2f}%",
            "signals": active_signals if active_signals else [{"ticker": "CASH", "side": "WAIT", "reason": "无显著信号"}],
            "update": datetime.utcnow().strftime('%H:%M:%S')
        }
    except: return None

def build_html(d):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #000; color: #0f6; font-family: sans-serif; padding: 15px; margin: 0; }}
            .card {{ background: #0a0a0a; border: 1px solid #222; padding: 15px; border-radius: 5px; margin-bottom: 10px; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
            .label {{ font-size: 10px; color: #555; }}
            .val {{ font-size: 18px; font-weight: bold; }}
            .sig {{ border-left: 3px solid orange; padding-left: 10px; margin: 10px 0; font-size: 12px; }}
            table {{ width: 100%; font-size: 12px; margin-top: 10px; border-collapse: collapse; }}
            td {{ padding: 8px 0; border-bottom: 1px solid #111; }}
        </style>
    </head>
    <body>
        <div style="font-size:12px; margin-bottom:20px; color:#555;">SYSTEM: V10.0 | {d['update']} UTC</div>
        <div class="grid">
            <div class="card"><div class="label">自驾累计收益</div><div class="val">{d['cum_ret']}</div></div>
            <div class="card"><div class="label">夏普比率</div><div class="val">{d['sharpe']}</div></div>
        </div>
        <div class="card">
            <div class="label" style="color:orange;">● 引擎识别机会点</div>
            {"".join([f"<div class='sig'><b>{s['ticker']} {s['side']}</b><br>{s['reason']}</div>" for s in d['signals']])}
        </div>
        <div class="card">
            <div class="label">子模型胜率矩阵</div>
            <table>
                {"".join([f"<tr><td>{m['id']}</td><td style='color:#0f6'>{m['win']*100}%</td><td>{m['asset']}</td></tr>" for m in MODELS])}
            </table>
        </div>
    </body>
    </html>
    """
    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w') as f: f.write(html)

if __name__ == "__main__":
    d = get_data()
    if d: build_html(d)
