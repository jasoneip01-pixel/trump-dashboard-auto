import os, yfinance as yf, pandas as pd, numpy as np, requests
from datetime import datetime, timedelta

# --- [1. 核心模型配置库] ---
MODELS = [
    {"id": "A3", "tk": "IWM", "win": 0.72, "odds": 1.5, "tp_target": 0.05, "stop_loss": -0.04, "tag": "SmallCap"},
    {"id": "D3", "tk": "BITO", "win": 0.70, "odds": 2.2, "tp_target": 0.12, "stop_loss": -0.07, "tag": "Crypto"},
    {"id": "D2", "tk": "FXI", "win": 0.70, "odds": 1.8, "tp_target": 0.08, "stop_loss": -0.05, "tag": "China"},
    {"id": "B3", "tk": "QQQ", "win": 0.67, "odds": 2.5, "tp_target": 0.06, "stop_loss": -0.03, "tag": "BigTech"}
]

# --- [2. 决策辅助函数] ---
def translate_intel(text):
    dic = {"TARIFF": "关税", "TAX": "减税", "INFLATION": "通胀", "CRYPTO": "加密", "TRADE": "贸易", "FED": "联储"}
    translated = text.upper()
    for k, v in dic.items(): translated = translated.replace(k, f"【{v}】")
    return translated[:75] + "..." if len(translated) > 75 else translated

def calculate_kelly(p, b):
    f = (b * p - (1 - p)) / b
    return max(0, f * 0.5) # 半凯利风控

def get_engine_data():
    api_key = os.getenv("ALPHAVANTAGE_API_KEY", "DEMO")
    all_tk = ["SPY", "IWM", "FXI", "BITO", "QQQ", "VIX", "UUP"]
    
    try:
        df = yf.download(all_tk, period="6mo").ffill()['Close']
        rets = df.pct_change()
        
        # A. 流动性黑洞监测
        usd_move = df['UUP'].pct_change(5).iloc[-1]
        vix_val = df['VIX'].iloc[-1]
        env_mode = "BLACK_HOLE" if usd_move > 0.015 and vix_val > 25 else "NORMAL"
        
        # B. 情报获取与翻译
        news_res = requests.get(f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&limit=15&apikey={api_key}').json()
        raw_news = news_res.get("feed", [{}])[0].get("title", "Market Steady")
        news_cloud = " ".join([n['title'].upper() for n in news_res.get("feed", [])])

        # C. 核心决策矩阵生成
        decisions = []
        for m in MODELS:
            # 1. 信号共振检查
            signal_hit = 1 if (m['tag'].upper() in news_cloud or m['tk'][:3] in news_cloud) else 0
            
            # 2. 仓位与止盈计算
            recent_gain = (df[m['tk']].iloc[-1] / df[m['tk']].iloc[-10]) - 1 # 10日表现
            kelly_pos = calculate_kelly(m['win'], m['odds']) if signal_hit else 0
            tp_progress = min(100, max(0, (recent_gain / m['tp_target']) * 100)) if recent_gain > 0 else 0
            
            # 3. 回溯与安全边际
            week_high = df[m['tk']].tail(5).max()
            dist_to_stop = ((df[m['tk']].iloc[-1] / week_high) - 1) - m['stop_loss']
            
            decisions.append({
                "id": m['id'], "tk": m['tk'], 
                "pos": f"{kelly_pos*100:.1f}%",
                "gain": f"{recent_gain*100:+.1f}%",
                "tp_prog": tp_progress,
                "safety": "SAFE" if dist_to_stop > 0.02 else "DANGER",
                "action": "LONG" if (signal_hit and env_mode=="NORMAL") else "WAIT"
            })

        return {
            "ret": f"{(df['SPY'].iloc[-1]/df['SPY'].iloc[-20]-1)*100:+.2f}%",
            "vix": f"{vix_val:.2f}", "env": env_mode,
            "news_cn": translate_intel(raw_news), "news_en": raw_news,
            "decisions": decisions, "ts": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e: return {"error": str(e)}

def render_ui(d):
    html = f"""
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            :root {{ --neon: #00FF66; --bg: #000; --red: #FF3333; --blue: #00CCFF; --amber: #FFB800; }}
            body {{ background: var(--bg); color: #fff; font-family: 'Inter', sans-serif; padding: 12px; margin: 0; }}
            .card {{ background: #080808; border: 1px solid #1a1a1a; padding: 16px; margin-bottom: 12px; border-radius: 8px; }}
            .env-tag {{ padding: 2px 8px; border-radius: 20px; font-size: 10px; font-weight: bold; background: { 'var(--red)' if d['env']=='BLACK_HOLE' else 'var(--blue)' }; color: #000; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
            .prog-bg {{ background: #222; height: 4px; border-radius: 2px; margin-top: 5px; }}
            .prog-fill {{ height: 100%; background: var(--neon); transition: width 0.5s; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }}
            td {{ padding: 12px 5px; border-bottom: 1px solid #111; }}
            .action-tag {{ padding: 2px 6px; font-size: 10px; font-weight: bold; border-radius: 3px; }}
            .LONG {{ background: var(--neon); color: #000; }}
            .WAIT {{ background: #222; color: #666; }}
        </style>
    </head>
    <body>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; border-bottom: 1px solid #333; padding-bottom:10px;">
            <b style="color:var(--neon);">TRUMP_CODE CORE V24.0</b>
            <span class="env-tag">{d['env']} MODE</span>
        </div>

        <div class="card">
            <div style="font-size:10px; color:#444; margin-bottom:8px;">AI 智能情报翻译</div>
            <div style="font-size:13px; color:#fff; border-left: 3px solid var(--blue); padding-left: 10px;">{d['news_cn']}</div>
            <div style="font-size:9px; color:#333; margin-top:5px;">{d['news_en']}</div>
        </div>

        <div class="grid">
            <div class="card"><div style="font-size:10px; color:#444;">20D 市场基准收益</div><div style="font-size:24px; font-weight:bold; color:var(--neon);">{d['ret']}</div></div>
            <div class="card"><div style="font-size:10px; color:#444;">VIX 风险水位</div><div style="font-size:24px; font-weight:bold;">{d['vix']}</div></div>
        </div>

        <div class="card">
            <div style="font-size:10px; color:var(--amber); margin-bottom:10px;">● 综合执行矩阵 (Execution Matrix)</div>
            <table>
                <thead><tr style="color:#444;"><td>标的</td><td>指令</td><td>凯利建议</td><td>止盈进度</td><td>安全</td></tr></thead>
                <tbody>
                    {"".join([f'''
                    <tr>
                        <td><b>{o['tk']}</b><br><small style="color:#444;">{o['gain']}</small></td>
                        <td><span class="action-tag {o['action']}">{o['action']}</span></td>
                        <td style="color:var(--blue);">{o['pos']}</td>
                        <td><div class="prog-bg"><div class="prog-fill" style="width:{o['tp_prog']}%;"></div></div></td>
                        <td style="color:{'var(--neon)' if o['safety']=='SAFE' else 'var(--red)'};">{o['safety']}</td>
                    </tr>
                    ''' for o in d['decisions']])}
                </tbody>
            </table>
        </div>

        <div style="text-align:center; font-size:9px; color:#222; margin-top:15px;">
            INTELLIGENCE v24.0 | RE-INVESTMENT ACTIVE | {d['ts']} UTC
        </div>
    </body>
    </html>
    """
    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w', encoding='utf-8') as f: f.write(html)

if __name__ == "__main__":
    data = get_engine_data()
    if "error" not in data: render_ui(data)
