import os
import yfinance as yf
import pandas as pd
from datetime import datetime

def get_market_data():
    try:
        # 抓取标的数据：DJT(特朗普概念股), BTC-USD(加密市场), SPY(标普500)
        tickers = ["DJT", "BTC-USD", "SPY"]
        # 获取最近30天的历史数据
        df = yf.download(tickers, period="30d", interval="1d")['Close']
        
        # 计算实时涨跌幅 (相比30天前)
        djt_return = (df['DJT'].iloc[-1] / df['DJT'].iloc[0] - 1) * 100
        
        # 计算相关性 (Pearson Correlation)
        returns = df.pct_change().dropna()
        btc_corr = returns['DJT'].corr(returns['BTC-USD'])
        spy_corr = returns['DJT'].corr(returns['SPY'])
        
        return {
            "return": f"{djt_return:+.2f}%",
            "btc_corr": f"{btc_corr:.2f}",
            "spy_corr": f"{spy_corr:.2f}",
            "time": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
    except Exception as e:
        return {"return": "Fetch Error", "btc_corr": "0.00", "spy_corr": "0.00", "time": str(e)}

def save_html(data):
    html_template = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TRUMP/CODE 实时量化看板</title>
        <style>
            body {{ background: #050505; color: #fff; font-family: sans-serif; display: flex; justify-content: center; padding: 40px; }}
            .container {{ width: 100%; max-width: 800px; }}
            .header {{ border-bottom: 1px solid #333; padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: flex-end; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }}
            .card {{ background: #111; padding: 25px; border-radius: 12px; border: 1px solid #222; text-align: center; }}
            .label {{ color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 10px; }}
            .value {{ font-size: 32px; font-weight: bold; color: #52c41a; }}
            .time {{ color: #444; font-size: 12px; margin-top: 20px; text-align: right; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin:0;">TRUMP/CODE <span style="font-weight:100; color:#888;">Live</span></h1>
            </div>
            <div class="grid">
                <div class="card"><div class="label">DJT 30日累计收益</div><div class="value">{data['return']}</div></div>
                <div class="card"><div class="label">BTC 相关性</div><div class="value" style="color:#fadb14;">{data['btc_corr']}</div></div>
                <div class="card"><div class="label">SPY 相关性</div><div class="value" style="color:#ff4d4f;">{data['spy_corr']}</div></div>
            </div>
            <p class="time">数据由 Yahoo Finance 实时驱动 | 最后同步: {data['time']}</p>
        </div>
    </body>
    </html>
    """
    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(html_template)

if __name__ == "__main__":
    market_data = get_market_data()
    save_html(market_data)
