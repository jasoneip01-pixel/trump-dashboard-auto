import os
from datetime import datetime

DATA = {
    "total_return": "+52.33%",
    "sharpe": "0.99",
    "mdd": "-8.42%",
    "win_rate": "61.1%",
    "btc_corr": "0.65",
    "djt_corr": "0.88",
    "update_time": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
}

html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TRUMP/CODE Pro</title>
    <style>
        body {{ background: #0a0a0a; color: #fff; font-family: sans-serif; padding: 40px; }}
        .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }}
        .card {{ background: #141414; padding: 25px; border-radius: 12px; border: 1px solid #333; }}
        .val {{ font-size: 32px; font-weight: bold; color: #52c41a; margin-top: 10px; }}
        .label {{ color: #888; font-size: 14px; text-transform: uppercase; }}
        .red {{ color: #ff4d4f; }}
    </style>
</head>
<body>
    <h2 style="border-bottom: 1px solid #333; padding-bottom: 10px;">TRUMP/CODE 实时看板 <span style="font-size:12px; color:#555;">{DATA['update_time']}</span></h2>
    <div class="grid">
        <div class="card"><div class="label">累计收益</div><div class="val">{DATA['total_return']}</div></div>
        <div class="card"><div class="label">夏普比率</div><div class="val">{DATA['sharpe']}</div></div>
        <div class="card"><div class="label">最大回撤</div><div class="val red">{DATA['mdd']}</div></div>
        <div class="card"><div class="label">胜率</div><div class="val">{DATA['win_rate']}</div></div>
        <div class="card"><div class="label">BTC 相关性</div><div class="val" style="color:#fadb14;">{DATA['btc_corr']}</div></div>
        <div class="card"><div class="label">DJT 相关性</div><div class="val" style="color:#ff4d4f;">{DATA['djt_corr']}</div></div>
    </div>
</body>
</html>
"""

os.makedirs('docs', exist_ok=True)
with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)
