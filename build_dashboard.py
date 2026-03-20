import os, yfinance as yf, pandas as pd, numpy as np, requests
from datetime import datetime

class InstitutionalDecisionSupport:
    def __init__(self):
        self.api_key = os.getenv("ALPHAVANTAGE_API_KEY", "DEMO")
        # 核心映射：政策触发词 -> 影响资产
        self.policy_matrix = {
            "TARIFF": {"pos": ["UUP"], "neg": ["FXI", "IWM"], "desc": "贸易保护加剧，美元走强，出海企业受损"},
            "TAX_CUT": {"pos": ["IWM", "SPY"], "neg": [], "desc": "内需企业利好，推升本土中小市值表现"},
            "CRYPTO": {"pos": ["BITO"], "neg": [], "desc": "监管环境放松预期，数字资产动量增强"},
            "ENERGY": {"pos": ["XLE"], "neg": [], "desc": "传统能源审批加速，利好化石能源"}
        }
        self.tickers = ["IWM", "BITO", "QQQ", "FXI", "UUP", "^VIX", "SPY"]

    def fetch_deep_intel(self):
        """抓取并进行政策语义识别"""
        intel_reports = []
        try:
            # 增加 limit 到 50，获取更广的情报池
            url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&limit=50&apikey={self.api_key}"
            data = requests.get(url, timeout=10).json().get("feed", [])
            
            for item in data:
                content = (item.get("title", "") + " " + item.get("summary", "")).upper()
                sentiment = float(item.get("overall_sentiment_score", 0))
                
                # 寻找关键词匹配
                for keyword, impact in self.policy_matrix.items():
                    if keyword in content:
                        intel_reports.append({
                            "keyword": keyword,
                            "sentiment": sentiment,
                            "impact": impact,
                            "headline": item.get("title", "")[:60] + "..."
                        })
        except: pass
        return intel_reports

    def run_analysis(self):
        # 1. 获取行情
        df = yf.download(self.tickers, period="3mo", interval="1d", auto_adjust=True)
        df = df['Close'] if 'Close' in df else df
        df = df.ffill().bfill()

        # 2. 深度情报获取
        intel = self.fetch_deep_intel()
        
        # 3. 资产逻辑计算
        results = []
        for tk in ["IWM", "BITO", "QQQ", "FXI"]:
            # 计算技术面：20日趋势 + 波动率
            recent_ret = (df[tk].iloc[-1] / df[tk].iloc[-20]) - 1
            vol = df[tk].pct_change().std() * np.sqrt(252)
            
            # 匹配情报分：汇总所有提到该资产相关关键词的情报
            rel_intel = [i for i in intel if tk in i['impact']['pos'] or tk in i['impact']['neg']]
            if rel_intel:
                # 如果在 neg 列表里，情绪分取反
                adj_sentiment = np.mean([i['sentiment'] * (-1 if tk in i['impact']['neg'] else 1) for i in rel_intel])
                reason = rel_intel[0]['desc']
                top_head = rel_intel[0]['headline']
            else:
                adj_sentiment = 0
                reason = "无直接政策驱动"
                top_head = "跟随大盘波动"

            # 机会得分 = 情绪权重(0.6) + 趋势权重(0.4)
            opp_score = (adj_sentiment * 60) + (recent_ret * 40)
            
            results.append({
                "tk": tk, "score": round(opp_score, 1),
                "sentiment": "BULL" if adj_sentiment > 0.1 else "BEAR" if adj_sentiment < -0.1 else "NEUTRAL",
                "trend": f"{recent_ret*100:+.1f}%",
                "vol": f"{vol*100:.1f}%",
                "reason": reason, "top_head": top_head
            })

        return {
            "vix": f"{df['^VIX'].iloc[-1]:.1f}",
            "ts": datetime.utcnow().strftime('%m-%d %H:%M'),
            "results": results
        }

    def render(self, data):
        rows = "".join([f"""
            <div class="asset-card">
                <div class="row-top">
                    <b style="font-size:18px;">{r['tk']}</b>
                    <span class="score-tag">机会分: {r['score']}</span>
                </div>
                <div class="metrics">
                    <span>情绪: <b class="{r['sentiment']}">{r['sentiment']}</b></span>
                    <span>20D动量: <b>{r['trend']}</b></span>
                    <span>年化波动: <b>{r['vol']}</b></span>
                </div>
                <div class="reason"><b>驱动逻辑:</b> {r['reason']}</div>
                <div class="headline"><b>最关联情报:</b> {r['top_head']}</div>
            </div>
        """ for r in data['results']])

        html = f"""
        <!DOCTYPE html><html><head><meta charset="UTF-8">
        <style>
            body {{ background: #000; color: #ddd; font-family: -apple-system, sans-serif; padding: 20px; }}
            .asset-card {{ background: #0a0a0a; border: 1px solid #1a1a1a; padding: 20px; margin-bottom: 15px; border-radius: 8px; }}
            .row-top {{ display: flex; justify-content: space-between; margin-bottom: 15px; }}
            .score-tag {{ background: #1a3a2a; color: #00ff88; padding: 4px 10px; border-radius: 4px; font-weight: bold; }}
            .metrics {{ display: flex; gap: 20px; font-size: 13px; color: #888; margin-bottom: 12px; }}
            .BULL {{ color: #00ff88; }} .BEAR {{ color: #ff4444; }} .NEUTRAL {{ color: #888; }}
            .reason {{ font-size: 13px; color: #bbb; margin-bottom: 8px; border-left: 2px solid #333; padding-left: 10px; }}
            .headline {{ font-size: 11px; color: #555; }}
            .vix-bar {{ font-size: 12px; color: #444; margin-bottom: 20px; text-align: right; }}
        </style></head>
        <body>
            <div style="display:flex; justify-content:space-between; align-items:flex-end;">
                <h2 style="margin:0;">TRUMP_CODE 深度机会下钻</h2>
                <div class="vix-bar">VIX: {data['vix']} | {data['ts']} UTC</div>
            </div>
            <hr style="border:0; border-top:1px solid #222; margin: 20px 0;">
            {rows}
        </body></html>
        """
        os.makedirs('docs', exist_ok=True)
        with open('docs/index.html', 'w', encoding='utf-8') as f: f.write(html)

if __name__ == "__main__":
    engine = InstitutionalDecisionSupport()
    data = engine.run_analysis()
    engine.render(data)
