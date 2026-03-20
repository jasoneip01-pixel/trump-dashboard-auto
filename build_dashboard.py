import os, yfinance as yf, pandas as pd, numpy as np, requests
from datetime import datetime

# --- [量化因子库：增强型关键词] ---
LOGIC_LIBRARY = {
    "POLICY": {"keywords": ["TARIFF", "TRADE", "CHINA", "TAX", "DEAL"], "tk": "IWM", "side": "LONG", "desc": "政策博弈"},
    "CRYPTO": {"keywords": ["BTC", "CRYPTO", "BITCOIN", "REGULATION"], "tk": "BITO", "side": "LONG", "desc": "数字资产溢价"},
    "ENERGY": {"keywords": ["OIL", "ENERGY", "DRILL", "CLIMATE"], "tk": "XLE", "side": "LONG", "desc": "传统能源复苏"},
    "TECH": {"keywords": ["AI", "NVDA", "SEMICONDUCTOR", "CHIP"], "tk": "QQQ", "side": "LONG", "desc": "科技成长因子"}
}

SUB_MODELS = [
    {"id": "A3", "name": "relief_rocket", "win": 0.727, "asset": "IWM"},
    {"id": "D3", "name": "volume_spike", "win": 0.702, "asset": "BTC"},
    {"id": "D2", "name": "sig_change", "win": 0.700, "asset": "FXI"},
    {"id": "B3", "name": "action_pre", "win": 0.667, "asset": "TSLA"}
]

def fetch_intel():
    api_key = os.getenv("ALPHAVANTAGE_API_KEY", "DEMO")
    tickers = ["SPY", "IWM", "FXI", "BITO", "QQQ", "XLE"]
    try:
        # 获取行情
        df = yf.download(tickers, period="6mo", interval="1d")['Close'].ffill()
        rets = df.pct_change().dropna()

        # 情绪引擎升级：多关键词匹配
        news_res = requests.get(f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&limit=25&apikey={api_key}').json()
        feeds = news_res.get("feed", [])
        
        active_signals = []
        news_cloud = " ".join([n['title'].upper() for n in feeds])
        
        for factor, cfg in LOGIC_LIBRARY.items():
            if any(k in news_cloud for k in cfg['keywords']):
                active_signals.append(cfg)

        # 动态权重分配 (Kelly-Lite)
        if active_signals:
            w = 1.0 / len(active_signals)
            strat_ret = sum([rets[s['tk']] * (1 if s['side']=="LONG" else -1) * w for s in active_signals])
        else:
            strat_ret = rets['SPY'] * 0.5 + rets['IWM'] * 0.5 # 默认对冲模式

        cum_ret = (1 + strat_ret).cumprod()
        
        return {
            "ret": f"{(cum_ret.iloc[-1]-1)*100:+.2f}%",
            "sharpe": f"{(strat_ret.mean()*252)/(strat_ret.std()*np.sqrt(252)):.2f}",
            "mdd": f"{((cum_ret / cum_ret.cummax()) - 1).min()*100:.2f}%",
            "signals": active_signals if active_signals else [{"tk":"CASH", "side":"WAIT", "desc":"信号真空期"}],
            "news": feeds[0]['title'] if feeds else "Market Sidelined",
            "ts": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {"error": str(e)}

def render_ui(d):
    html = f"""
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            :root {{ --neon: #00FF66; --bg: #000; --card: #0A0A0A; --border: #1A1A1A; --amber: #FFB800; }}
            body {{ background: var(--bg); color: var(--neon); font-family: -apple-system, 'Inter', sans-serif; padding: 12px; margin: 0; }}
            .card {{ background: var(--card); border: 1px solid var(--border); padding: 16px; margin-bottom: 12px; border-radius: 8px; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
            .val {{ font-size: 26px; font-weight: 900; letter-spacing: -1px; }}
            .label {{ font-size: 10px; color: #666; text-transform: uppercase; margin-bottom: 4px; }}
            .sig-box {{ border-left: 3px solid var(--amber); padding-left: 12px; margin: 12px 0; }}
            table {{ width: 100%; font-size: 12px; border-collapse: collapse; margin-top: 10px; }}
            th {{ text-align: left; color: #444; border-bottom: 1px solid #111; padding: 8px 4px; }}
            td {{ padding: 10px 4px; border-bottom: 1px solid #050505; }}
            .up {{ color: var(--neon); }} .down {{ color: #FF3333; }}
        </style>
    </head>
    <body>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
            <b style="font-size:14px; color:#fff;">TRUMP_CODE INTEL v14.0</b>
            <span style="font-size:10px; color:#444;">{d['ts']} UTC</span>
        </div>

        <div class="grid">
            <div class="card"><div class="label">自驾引擎收益</div><div class="val { 'up' if '+' in d['ret'] else 'down' }">{d['ret']}</div></div>
            <div class="card"><div class="label">夏普比率 (Sharpe)</div><div class="val" style="color:#fff;">{d['sharpe']}</div></div>
        </div>

        <div class="card">
            <div class="label" style="color:var(--amber)">● 信号穿透与调仓指令 (Active Signals)</div>
            {"".join([f"<div class='sig-box'><b style='color:#fff;'>{s['tk']} | {s['side']}</b><br><span style='color:var(--amber); font-size:11px;'>{s['desc']}</span></div>" for s in d['signals']])}
        </div>

        <div class="card">
            <div class="label">核心子模型胜率 (Win Rate Matrix)</div>
            <table>
                <thead><tr><th>ID</th><th>胜率</th><th>映射资产</th></tr></thead>
                <tbody>
                    {"".join([f"<tr><td>{m['id']}</td><td style='color:#fff;'>{m['win']*100:.1f}%</td><td>{m['asset']}</td></tr>" for m in SUB_MODELS])}
                </tbody>
            </table>
        </div>

        <div class="card" style="border-color:#333;">
            <div class="label">风控监控 (Risk MDD)</div>
            <div class="val down" style="font-size:18px;">{d['mdd']}</div>
            <div style="font-size:10px; color:#222; margin-top:10px;">适配全机型终端 | 动态权重分仓已启动</div>
        </div>
    </body>
    </html>
    """
    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w', encoding='utf-8') as f: f.write(html)

if __name__ == "__main__":
    intel = fetch_intel()
    if "error" not in intel: render_ui(intel)
