cat <<EOF > build_dashboard.py
import os
from datetime import datetime

# --- 1. 核心数据 (手动更新区) ---
DATA = {
    "total_return": "+52.33%",
    "sharpe": "0.99",
    "mdd": "-8.42%",
    "win_rate": "61.1%",
    "z_score": "+5.30",
    "btc_corr": "0.65",
    "djt_corr": "0.88",
    "total_trades": "566",
    "success_trades": "346",
    "update_time": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
}

# --- 2. 恢复子模型排行数据 ---
MODELS = [
    {"name": "A3_relief_rocket", "n": 11, "rate": "72.7%"},
    {"name": "D3_volume_spike", "n": 47, "rate": "70.2%"},
    {"name": "D2_sig_change", "n": 88, "rate": "70.0%"},
    {"name": "B3_action_pre", "n": 33, "rate": "66.7%"},
    {"name": "C1_burst_silence", "n": 177, "rate": "65.0%"}
]

# --- 3. 全量 HTML 模板 (包含之前丢失的所有组件) ---
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TRUMP/CODE Pro Dashboard</title>
    <style>
        body {{ background: #0a0a0a; color: #fff; font-family: -apple-system, sans-serif; padding: 30px; line-height: 1.4; }}
        .header {{ border-bottom: 1px solid #333; padding-bottom: 15px; margin-bottom: 25px; display: flex; justify-content: space-between; }}
        .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }}
        .card {{ background: #141414; padding: 20px; border-radius: 8px; border: 1px solid #262626; }}
        .val {{ font-size: 24px; font-weight: bold; color: #52c41a; margin-top: 5px; }}
        .label {{ color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .red {{ color: #ff4d4f; }}
        .yellow {{ color: #fadb14; }}
        
        /* 恢复子模型列表样式 */
        .model-list {{ margin-top: 30px; background: #141414; padding: 20px; border-radius: 8px; border: 1px solid #262626; }}
        .model-item {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #222; font-size: 13px; }}
        .model-name {{ color: #d9d9d9; }}
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin:0;">TRUMP/CODE <span style="font-weight:normal; color:#888;">监控看板 · 真实回测版</span></h2>
        <div style="color:#444; font-size:12px;">LAST SYNC: {DATA['update_time']}</div>
    </div>

    <div class="grid">
        <div class="card"><div class="label">累计收益率</div><div class="val">{DATA['total_return']}</div></div>
        <div class="card"><div class="label">夏普比率 (Sharpe)</div><div class="val">{DATA['sharpe']}</div></div>
        <div class="card"><div class="label">最大回撤 (MDD)</div><div class="val red">{DATA['mdd']}</div></div>
        <div class="card"><div class="label">Z-SCORE</div><div class="val yellow">{DATA['z_score']}</div></div>
    </div>

    <div class="grid" style="margin-top:15px;">
        <div class="card"><div class="label">核心胜率</div><div class="val">{DATA['win_rate']}</div></div>
        <div class="card"><div class="label">BTC 相关性</div><div class="val yellow">{DATA['btc_corr']}</div></div>
        <div class="card"><div class="label">DJT 相关性</div><div class="val red">{DATA['djt_corr']}</div></div>
        <div class="card"><div class="label">成交样本 (N)</div><div class="val" style="color:#aaa;">{DATA['total_trades']}</div></div>
    </div>

    <div class="model-list">
        <div class="label" style="margin-bottom:15px;">子模型排行 (部分显示)</div>
        {"".join([f'<div class="model-item"><span class="model-name">⭐ {m["name"]}</span><span>N={m["n"]} | <b style="color:#52c41a;">{m["rate"]}</b></span></div>' for m in MODELS])}
    </div>

    <div style="margin-top: 20px; color: #444; font-size: 11px; text-align: center;">
        TRUMP CODE · QUANTITATIVE ANALYSIS · NOT FINANCIAL ADVICE
    </div>
</body>
</html>
"""

os.makedirs('docs', exist_ok=True)
with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)
print("✅ 看板完全体已恢复生成")
EOF
