import os, yfinance as yf, pandas as pd, numpy as np, requests
from datetime import datetime

# --- [自驾引擎配置] ---
MODELS = [
    {"id": "A3", "name": "relief_rocket", "n": 11, "win": 0.727, "asset": "IWM"},
    {"id": "D3", "name": "volume_spike", "n": 47, "win": 0.702, "asset": "BTC-USD"},
    {"id": "D2", "name": "sig_change", "n": 88, "win": 0.700, "asset": "FXI"},
    {"id": "B3", "name": "action_pre", "n": 33, "win": 0.667, "asset": "TSLA"}
]

# 关键词驱动的自动调仓逻辑
TRIGGER_MAP = {
    "TARIFF": {"ticker": "YANG", "side": "LONG", "reason": "关税升级-做多反向中概"},
    "TAX": {"ticker": "IWM", "side": "LONG", "reason": "减税政策-做多小盘股"},
    "CRYPTO": {"ticker": "BITO", "side": "LONG", "reason": "监管放宽-做多加密资产"},
    "CHINA": {"ticker": "FXI", "side": "SHORT", "reason": "对华限制-做空A50/H股"}
}

def get_engine_data():
    api_key = os.getenv("ALPHAVANTAGE_API_KEY", "DEMO")
    # 1. 抓取多资产行情
    assets = ["SPY", "IWM", "FXI", "BTC-USD", "YANG"]
    df = yf.download(assets, period="6mo", interval="1d")['Close'].ffill()
    rets = df.pct_change().dropna()

    # 2. 识别实时机会 (自驾引擎核心)
    news_res = requests.get(f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&limit=10&apikey={api_key}').json()
    feeds = news_res.get("feed", [])
    
    active_signals = []
    combined_text = " ".join([f['title'] for f in feeds]).upper()
    
    for key, val in TRIGGER_MAP.items():
        if key in combined_text:
            active_signals.append(val)
    
    # 3. 模拟自动调仓收益 (基于识别到的信号分配权重)
    # 如果没信号，默认保守持仓 IWM/SPY
    if not active_signals:
        strategy_ret = rets['SPY'] * 0.5 + rets['IWM'] * 0.5
    else:
        # 简单凯利：每个识别出的机会分配 25% 权重
        strategy_ret = sum([rets[s['ticker']] * (1 if s['side']=='LONG' else -1) for s in active_signals[:4]]) / 4

    cum_ret = (1 + strategy_ret).cumprod()
    
    return {
        "cum_ret": f"{(cum_ret.iloc[-1]-1)*100:+.2f}%",
        "sharpe": f"{(strategy_ret.mean()*252)/(strategy_ret.std()*np.sqrt(252)):.2f}",
        "mdd": f"{((cum_ret / cum_ret.cummax()) - 1).min()*100:.2f}%",
        "signals": active_signals if active_signals else [{"ticker": "CASH", "side": "NEUTRAL", "reason": "等待波动率回归"}],
        "news": feeds[0]['title'] if feeds else "No news link",
        "update": datetime.utcnow().strftime('%H:%M:%S')
    }

def build_ui(d):
    html = f"""
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>TRUMP_CODE MOBILE</title>
        <style>
            :root {{ --neon: #00FF66; --bg: #000; --card: #0A0A0A; --amber: #FFB800; }}
            body {{ background: var(--bg); color: var(--neon); font-family: -apple-system, sans-serif; margin: 0; padding: 10px; }}
            /* 响应式栅格：手机端1列，电脑端4列 */
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 8px; }}
            .card {{ background: var(--card); border: 1px solid #1A1A1A; padding: 12px; border-radius: 4px; }}
            .label {{ font-size: 10px; color: #666; text-transform: uppercase; }}
            .val {{ font-size: 20px; font-weight: 800; margin-top: 4px; }}
            .signal-row {{ border-left: 3px solid var(--amber); padding-left: 10px; margin: 10px 0; font-size: 13px; }}
            table {{ width: 100%; font-size: 11px; margin-top: 15px; border-collapse: collapse; }}
            th {{ text-align: left; color: #444; border-bottom: 1px solid #111; padding: 5px; }}
            td {{ padding: 8px 5px; border-bottom: 1px solid #050505; }}
            .mobile-hide {{ @media (max-width: 600px) {{ display: none; }} }}
        </style>
    </head>
    <body>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
            <b style="font-size:16px;">TERMINAL V10.0</b>
            <span style="font-size:10px; color:#444;">{d['update']} UTC</span>
        </div>

        <div class="grid">
            <div class="card"><div class="label">自驾收益</div><div class="val">{d['cum_ret']}</div></div>
            <div class="card"><div class="label">夏普 (Sharpe)</div><div class="val" style="color:white">{d['sharpe']}</div></div>
            <div class="card"><div class="label">风控 MDD</div><div class="val" style="color:#FF3333">{d['mdd']}</div></div>
            <div class="card mobile-hide"><div class="label">状态</div><div class="val">AUTO-PILOT</div></div>
        </div>

        <div class="card" style="margin-top:10px;">
            <div class="label" style="color:var(--amber)">● 引擎识别机会点 (Actionable Alpha)</div>
            {"".join([f"<div class='signal-row'><b>{s['ticker']} {s['side']}</b><br><span style='color:#888'>{s['reason']}</span></div>" for s in d['signals']])}
        </div>

        <div class="card" style="margin-top:10px;">
            <div class="label">核心模型胜率 (Model Win-Rate)</div>
            <table>
                <thead><tr><th>ID</th><th>胜率</th><th>映射资产</th><th class="mobile-hide">样本</th></tr></thead>
                <tbody>
                    {"".join([f"<tr><td>{m['id']}</td><td style='color:var(--neon)'>{m['win']*100}%</td><td>{m['asset']}</td><td class='mobile-hide'>{m['n']}</td></tr>" for m in MODELS])}
                </tbody>
            </table>
        </div>

        <div style="font-size:10px; color:#333; margin-top:15px; text-align:center;">
            适配 iPhone 17 / Huawei Mate 系列 / Android 响应式终端
        </div>
    </body>
    </html>
    """
    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == "__main__":
    data = get_engine_data()
    build_ui(data)
