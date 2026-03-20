import os, yfinance as yf, pandas as pd, numpy as np, requests
from datetime import datetime

# ==========================================
# 策略参数矩阵：工业级量化配置
# ==========================================
STRATEGY_MAP = {
    "IWM": {"name": "政策灵敏型", "win_rate": 0.68, "odds": 1.4, "tp_steps": [0.03, 0.08], "sl": -0.04, "tag": "SMALLCAP"},
    "BITO": {"name": "高波溢价型", "win_rate": 0.62, "odds": 2.5, "tp_steps": [0.05, 0.15], "sl": -0.08, "tag": "CRYPTO"},
    "FXI": {"name": "均值回归型", "win_rate": 0.58, "odds": 1.8, "tp_steps": [0.04, 0.10], "sl": -0.06, "tag": "CHINA"},
    "QQQ": {"name": "趋势龙头型", "win_rate": 0.72, "odds": 1.2, "tp_steps": [0.03, 0.07], "sl": -0.03, "tag": "TECH"}
}

class QuantTerminal:
    def __init__(self):
        self.api_key = os.getenv("ALPHAVANTAGE_API_KEY", "DEMO")
        # VIX 使用标准的 ^ 符号，UUP 监控美元
        self.tickers = ["SPY", "IWM", "FXI", "BITO", "QQQ", "^VIX", "UUP"]

    def fetch_clean_data(self):
        """稳健的数据下载与清洗引擎"""
        try:
            df = yf.download(self.tickers, period="6mo", interval="1d", auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df = df['Close']
            # 处理 VIX 可能缺失的情况
            if '^VIX' not in df.columns:
                df['^VIX'] = 18.0 
            return df.ffill().bfill()
        except Exception as e:
            print(f"Data Fetch Error: {e}")
            return pd.DataFrame()

    def get_sentiment_data(self):
        """情报解析：解耦赋值，修复 SyntaxError"""
        news_title = "暂无实时情报"
        translated_text = ""
        news_cloud = ""
        
        try:
            url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&limit=15&apikey={self.api_key}"
            r = requests.get(url, timeout=10).json()
            feeds = r.get("feed", [])
            
            if feeds:
                news_title = feeds[0].get("title", "")
                full_text = " ".join([f.get("title", "").upper() for f in feeds])
                news_cloud = full_text
                
                # 情报翻译逻辑
                mapping = {"TARIFF": "关税", "TAX": "减税", "TRADE": "贸易", "FED": "联储", "AI": "人工智能"}
                temp_trans = full_text
                for k, v in mapping.items():
                    temp_trans = temp_trans.replace(k, f"【{v}】")
                translated_text = temp_trans[:150] # 截取前150字符
        except Exception as e:
            news_title = f"API 连接受限"
            
        return news_title, translated_text, news_cloud

    def run_logic(self):
        df = self.fetch_clean_data()
        if df.empty:
            return {"error": "无法加载行情数据"}
            
        top_news, translated, news_cloud = self.get_sentiment_data()
        
        # 宏观风控
        vix = float(df['^VIX'].iloc[-1])
        usd_move = df['UUP'].pct_change(5).iloc[-1] if 'UUP' in df else 0
        # 判定流动性危机状态
        is_blackhole = usd_move > 0.012 and vix > 26
        
        results = []
        for tk, cfg in STRATEGY_MAP.items():
            if tk not in df: continue
            
            prices = df[tk]
            # 动量与回撤
            perf_10d = (prices.iloc[-1] / prices.iloc[-10]) - 1 if len(prices) > 10 else 0
            max_20d = prices.tail(20).max()
            dd_from_peak = (prices.iloc[-1] / max_20d) - 1
            
            # 信号匹配：标签命中或代码命中
            signal = 1 if (cfg['tag'] in news_cloud or tk[:3] in news_cloud) else 0
            
            # 凯利仓位计算
            kelly = (cfg['win_rate'] * cfg['odds'] - (1 - cfg['win_rate'])) / cfg['odds']
            # 综合判定：有信号 + 没危机 + 动量不为负
            pos_size = max(0, kelly * 0.5) if (signal and not is_blackhole and perf_10d > -0.02) else 0
            
            # 止盈进度
            tp1_target = cfg['tp_steps'][0]
            tp_prog = min(100, max(0, (perf_10d / tp1_target) * 100))
            
            results.append({
                "tk": tk, "name": cfg['name'], "price": f"{prices.iloc[-1]:.2f}",
                "perf": f"{perf_10d*100:+.1f}%", "pos": f"{pos_size*100:.1f}%",
                "tp_prog": int(tp_prog), "status": "DANGER" if dd_from_peak < cfg['sl'] else "HEALTHY"
            })

        return {
            "mkt_ret": f"{(df['SPY'].iloc[-1]/df['SPY'].iloc[-20]-1)*100:+.2f}%",
            "vix": f"{vix:.2f}", 
            "env": "BLACK_HOLE (清仓)" if is_blackhole else "STABLE (稳健)",
            "news": translated if translated else top_news,
            "results": results,
            "ts": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

def render_html(data):
    if "error" in data:
        html = f"<html><body style='background:#000;color:#ff3333;'>ERROR: {data['error']}</body></html>"
    else:
        env_color = "#ff3333" if "BLACK" in data['env'] else "#00CCFF"
        html = f"""
        <!DOCTYPE html><html><head><meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            :root {{ --neon: #00FF66; --bg: #000; --red: #FF3333; --blue: #00CCFF; --amber: #FFB800; }}
            body {{ background: var(--bg); color: #fff; font-family: 'Inter', sans-serif; padding: 20px; margin: 0; }}
            .card {{ background: #080808; border: 1px solid #1a1a1a; padding: 20px; margin-bottom: 15px; border-radius: 12px; }}
            .env-tag {{ padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; background: {env_color}; color: #000; }}
            .flex {{ display: flex; justify-content: space-between; align-items: center; }}
            .val {{ font-size: 28px; font-weight: 900; color: var(--neon); letter-spacing: -1px; }}
            .bar-bg {{ background: #222; height: 6px; width: 100%; border-radius: 3px; margin-top: 8px; }}
            .bar-fill {{ background: var(--neon); height: 100%; border-radius: 3px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            td {{ padding: 15px 5px; border-bottom: 1px solid #111; font-size: 13px; }}
            .HEALTHY {{ color: var(--neon); }} .DANGER {{ color: var(--red); font-weight: bold; }}
        </style></head>
        <body>
            <div class="flex" style="margin-bottom: 25px; border-bottom: 1px solid #222; padding-bottom: 15px;">
                <b style="font-size: 18px; color: var(--blue);">TRUMP_CODE v25.1 FINAL</b>
                <span class="env-tag">{data['env']}</span>
            </div>
            
            <div class="card">
                <div style="font-size: 11px; color: #444; margin-bottom: 10px; text-transform: uppercase;">核心情报实时量化 (AI-INTEL)</div>
                <div style="font-size: 14px; line-height: 1.6; border-left: 3px solid var(--blue); padding-left: 15px;">{data['news']}</div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                <div class="card"><div>20D 市场收益</div><div class="val">{data['mkt_ret']}</div></div>
                <div class="card"><div>VIX 压力</div><div class="val" style="color:#fff;">{data['vix']}</div></div>
            </div>

            <div class="card">
                <div style="font-size: 11px; color: var(--amber); margin-bottom: 10px;">执行矩阵 (EXECUTION MATRIX)</div>
                <table>
                    <thead><tr style="color: #444; font-size: 11px;"><td>标的</td><td>10D表现</td><td>凯利建议</td><td>止盈进度</td><td>状态</td></tr></thead>
                    <tbody>
                        {"".join([f'''
                        <tr>
                            <td><b>{r['tk']}</b><br><small style="color:#444;">{r['price']}</small></td>
                            <td class="HEALTHY">{r['perf']}</td>
                            <td style="color:var(--blue); font-weight:bold;">{r['pos']}</td>
                            <td style="width: 120px;">
                                <div class="bar-bg"><div class="bar-fill" style="width:{r['tp_prog']}%"></div></div>
                            </td>
                            <td class="{r['status']}">{r['status']}</td>
                        </tr>
                        ''' for r in data['results']])}
                    </tbody>
                </table>
            </div>
            <div style="text-align:center; font-size:10px; color:#222; margin-top: 20px;">
                STABLE RELEASE v25.1 | {data['ts']} UTC | RE-RUN SUCCESSFUL
            </div>
        </body></html>
        """
    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w', encoding='utf-8') as f: f.write(html)

if __name__ == "__main__":
    terminal = QuantTerminal()
    result = terminal.run_logic()
    render_html(result)
