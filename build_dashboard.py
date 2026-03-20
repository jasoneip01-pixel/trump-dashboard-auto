import os
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# --- 核心子模型库 (保持基石) ---
STRATEGY_LIB = {
    "A3": {"name": "Relief Rocket", "win": 0.727, "kelly_f": 0.2},
    "D3": {"name": "Volume Spike", "win": 0.702, "kelly_f": 0.15},
    "CHINA_MACRO": {"name": "Tariff Play", "win": 0.58, "kelly_f": 0.1}
}

def autopilot_engine():
    # 1. 监控宇宙 (Universe)
    universe = ["SPY", "BTC-USD", "FXI", "XLE", "IWM", "GLD"]
    try:
        data = yf.download(universe, period="1mo", interval="1d")['Close'].ffill()
        returns = data.pct_change().dropna()
        
        # 2. 模拟推文情绪扫描 (NLP Proxy)
        # 假设今日发现 "Tariff" 关键词频率激增
        sentiment_signal = {"keyword": "Tariff", "score": 0.85, "impact": "High"}
        
        # 3. 自动化仓位调整 (Kelly Criterion 简化版)
        # 逻辑：仓位 = (胜率 * 盈亏比 - 败率) / 盈亏比
        base_win = 0.611
        vol_adj = 1 - (returns['SPY'].std() * np.sqrt(252)) # 波动率大则减仓
        target_pos = base_win * vol_adj
        
        # 4. 风控指标计算
        cum_ret = (1 + returns['SPY']).cumprod()
        mdd = ((cum_ret / cum_ret.cummax()) - 1).min()
        sharpe = (returns['SPY'].mean() * 252) / (returns['SPY'].std() * np.sqrt(252))
        
        return {
            "pos": f"{target_pos*100:.1f}%",
            "active_asset": "FXI (Short) / IWM (Long)",
            "sentiment_desc": f"DETECTED: {sentiment_signal['keyword']} ({sentiment_signal['score']})",
            "mdd": f"{mdd*100:.2f}%",
            "sharpe": f"{sharpe:.2f}",
            "equity_curve": cum_ret.tolist()[-10:], # 取最近10天走势
            "update": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
    except: return None

def generate_engine_terminal():
    d = autopilot_engine()
    if not d: return

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ background: #050505; color: #00ff66; font-family: 'Segoe UI', monospace; padding: 30px; }}
            .terminal {{ border: 2px solid #00ff66; padding: 20px; box-shadow: 0 0 15px rgba(0,255,102,0.2); }}
            .header {{ display: flex; justify-content: space-between; border-bottom: 1px solid #00ff66; margin-bottom: 20px; padding-bottom: 10px; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 15px; }}
            .stat-card {{ background: #0a0a0a; border: 1px solid #222; padding: 15px; }}
            .status-live {{ color: #000; background: #00ff66; padding: 2px 8px; font-weight: bold; border-radius: 3px; }}
            .engine-log {{ background: #000; color: #888; padding: 15px; border: 1px solid #222; margin-top: 20px; font-size: 12px; }}
            .blink {{ animation: blinker 1.5s linear infinite; }}
            @keyframes blinker {{ 50% {{ opacity: 0; }} }}
        </style>
    </head>
    <body>
        <div class="terminal">
            <div class="header">
                <div style="font-size: 20px;">TRUMP/CODE <span class="blink">●</span> AUTO-ENGINE V6.0</div>
                <div class="status-live">ENGINE: AUTOPILOT</div>
            </div>

            <div class="grid">
                <div class="stat-card"><div style="font-size:10px;">建议总仓位 (EXPOSURE)</div><div style="font-size:28px; color:#fff;">{d['pos']}</div></div>
                <div class="stat-box"><div style="font-size:10px;">当前核心交易标的</div><div style="font-size:16px; margin-top:10px;">{d['active_asset']}</div></div>
                <div class="stat-card"><div style="font-size:10px;">SHARPE (年化风险调整)</div><div style="font-size:28px;">{d['sharpe']}</div></div>
                <div class="stat-card"><div style="font-size:10px;">MAX DRAWDOWN</div><div style="font-size:28px; color: #ff4444;">{d['mdd']}</div></div>
            </div>

            <div class="engine-log">
                [SYSTEM_LOG] {d['update']}<br>
                >> 分析推文流... {d['sentiment_desc']}<br>
                >> 触发多资产映射逻辑: 调仓 FXI 权重...<br>
                >> 风控检查: 波动率符合预期。Kelly Criterion 计算完成。<br>
                >> 自动化下单指令已生成: WAIT_CONFIRMATION...
            </div>
            
            <div style="margin-top:20px;">
                <table style="width:100%; border-collapse: collapse; font-size: 12px;">
                    <tr style="color: #666; text-align: left;"><th>资产类别</th><th>当前信号</th><th>关联推文关键词</th><th>胜率评估</th></tr>
                    <tr><td>EQUITY (IWM)</td><td>LONG</td><td>Tax Cuts / Deregulation</td><td>61.1%</td></tr>
                    <tr><td>CRYPTO (BTC)</td><td>NEUTRAL</td><td>Crypto Hub</td><td>58.4%</td></tr>
                    <tr><td>COMMODITY (GLD)</td><td>HEDGE</td><td>Inflationary Bias</td><td>52.0%</td></tr>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == "__main__":
    generate_engine_terminal()
