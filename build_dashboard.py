import os, yfinance as yf, pandas as pd, numpy as np, requests
from datetime import datetime

class RealTimeQuant:
    def __init__(self):
        self.api_key = os.getenv("ALPHAVANTAGE_API_KEY", "DEMO")
        # 资产池：标的 - 核心关联分类
        self.assets = {
            "IWM": {"name": "罗素2000", "category": "TRADE", "impact": ["TARIFF", "TAX", "USA"]},
            "BITO": {"name": "比特币ETF", "category": "CRYPTO", "impact": ["BTC", "CRYPTO", "SEC"]},
            "QQQ": {"name": "纳指100", "category": "TECH", "impact": ["AI", "CHIPS", "FED"]},
            "FXI": {"name": "中国大盘ETF", "category": "GLOBAL", "impact": ["CHINA", "TRADE", "TARIFF"]}
        }
        self.tickers = list(self.assets.keys()) + ["SPY", "^VIX"]

    def get_intel_analysis(self):
        """核心：推文/情报分类与情绪定量"""
        intel_stack = []
        try:
            r = requests.get(f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&limit=20&apikey={self.api_key}").json()
            feeds = r.get("feed", [])
            for f in feeds:
                title = f.get("title", "").upper()
                score = float(f.get("overall_sentiment_score", 0))
                
                # 分类逻辑
                cat = "GENERAL"
                if any(k in title for k in ["TARIFF", "TRADE", "IMPORT"]): cat = "TRADE"
                elif any(k in title for k in ["BTC", "CRYPTO", "BITCOIN"]): cat = "CRYPTO"
                elif any(k in title for k in ["FED", "RATE", "INFLATION"]): cat = "MACRO"
                elif any(k in title for k in ["AI", "NVIDIA", "TECH"]): cat = "TECH"
                
                intel_stack.append({"title": title, "cat": cat, "score": score})
        except: pass
        return intel_stack

    def analyze_opportunities(self):
        df = yf.download(self.tickers, period="1mo", interval="1d", auto_adjust=True)
        df = df['Close'] if 'Close' in df else df
        df = df.ffill().bfill()

        intel = self.get_intel_analysis()
        vix = df['^VIX'].iloc[-1]
        
        results = []
        for tk, info in self.assets.items():
            # 1. 提取该资产相关的平均情绪
            relevant_scores = [i['score'] for i in intel if i['cat'] == info['category'] or any(k in i['title'] for k in info['impact'])]
            avg_sentiment = np.mean(relevant_scores) if relevant_scores else 0
            
            # 2. 计算量化指标
            returns = df[tk].pct_change()
            mom = returns.tail(5).sum() # 5日动量
            vol = returns.std() * np.sqrt(252) # 年化波动
            
            # 3. 机会点评分 (实打实的逻辑：情绪正向+动量向上+波动可控)
            opp_score = (avg_sentiment * 0.4) + (mom * 0.4) - (vol * 0.2)
            
            # 4. 建议行动
            action = "STRONG BUY" if opp_score > 0.05 else "HOLD" if opp_score > -0.02 else "AVOID"
            if vix > 30: action = "HEDGE/CASH" # 恐慌阈值强制修正

            results.append({
                "tk": tk, "name": info['name'], "cat": info['category'],
                "sentiment": f"{avg_sentiment:+.2f}",
                "mom": f"{mom*100:+.1f}%",
                "opp": round(opp_score * 100, 2),
                "action": action
            })
        
        return {"results": results, "vix": vix, "top_news": intel[0]['title'] if intel else "N/A"}

    def render(self, data):
        # 简化版表格，突出“机会点”和“行动”
        rows = "".join([f"""
            <tr>
                <td><b>{r['tk']}</b><br><small>{r['name']}</small></td>
                <td><span class="tag">{r['cat']}</span></td>
                <td style="color:{'#00ff66' if float(r['sentiment'])>0 else '#ff4444'}">{r['sentiment']}</td>
                <td>{r['mom']}</td>
                <td style="font-size:18px; font-weight:bold;">{r['opp']}</td>
                <td><b class="act-{r['action']}">{r['action']}</b></td>
            </tr>
        """ for r in data['results']])

        html = f"""
        <!DOCTYPE html><html><head><meta charset="UTF-8">
        <style>
            body {{ background: #000; color: #eee; font-family: sans-serif; padding: 20px; }}
            .card {{ background: #111; padding: 20px; border-radius: 8px; border: 1px solid #222; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th {{ text-align: left; color: #555; font-size: 12px; border-bottom: 2px solid #222; padding: 10px; }}
            td {{ padding: 15px 10px; border-bottom: 1px solid #1a1a1a; }}
            .tag {{ background: #222; padding: 2px 6px; border-radius: 4px; font-size: 11px; }}
            .act-STRONG {{ color: #00ff66; border: 1px solid #00ff66; padding: 2px 5px; }}
            .act-AVOID {{ color: #ff4444; opacity: 0.6; }}
            .act-HEDGE {{ background: #ff4444; color: #fff; padding: 2px 5px; }}
        </style></head>
        <body>
            <div class="card">
                <h2>TRUMP_CODE 实战机会看板</h2>
                <div style="color:#666; font-size:13px;">实时头条: {data['top_news']}</div>
                <table>
                    <thead><tr><th>相关资产</th><th>分析维度</th><th>情绪极性</th><th>5D动量</th><th>机会得分</th><th>实战建议</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        </body></html>
        """
        os.makedirs('docs', exist_ok=True)
        with open('docs/index.html', 'w', encoding='utf-8') as f: f.write(html)

if __name__ == "__main__":
    bot = RealTimeQuant()
    res = bot.analyze_opportunities()
    bot.render(res)
