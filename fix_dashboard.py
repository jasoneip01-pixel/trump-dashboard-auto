#!/usr/bin/env python3
"""
fix_dashboard.py
================
读取已计算好的 real_backtest.json，重新生成正确的 trump_dashboard.html
包含：真实胜率54.59%、Sharpe 0.99、累计收益+52.33%、完整权益曲线

用法：
    cd ~/Downloads
    python3 fix_dashboard.py
"""

import json, ssl, urllib.request, warnings
from pathlib import Path
from datetime import datetime, timezone

warnings.filterwarnings("ignore")

def ssl_ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c

def get_url(url):
    req = urllib.request.Request(url, headers={"User-Agent":"trump-code/1.0"})
    with urllib.request.urlopen(req, context=ssl_ctx(), timeout=15) as r:
        return r.read()

# ── 1. 读取已算好的回测数据 ──────────────────────────
bt_path = Path("paper_results/real_backtest.json")
if not bt_path.exists():
    print("❌ paper_results/real_backtest.json 不存在，请先运行回测")
    exit(1)

bt = json.loads(bt_path.read_text(encoding="utf-8"))
print(f"✅ 读取回测数据:")
print(f"   胜率:    {bt['win_rate_pct']}")
print(f"   Sharpe:  {bt['sharpe']}")
print(f"   累计:    {bt['cumulative_return']:+.2%}")
print(f"   回撤:    {bt['max_drawdown']:.2%}")
print(f"   SPY天数: {bt['spy_days']}")

# ── 2. 拉取最新日报 ──────────────────────────────────
daily_en = daily_zh = ""
try:
    raw = json.loads(get_url(
        "https://raw.githubusercontent.com/sstklen/trump-code/main/data/daily_report.json"
    ))
    daily_en = raw.get("summary",{}).get("en","") or raw.get("en","")
    daily_zh = raw.get("summary",{}).get("zh","") or raw.get("zh","")
    print(f"✅ 今日日报已获取")
except Exception as e:
    print(f"⚠  日报获取失败（{e}），使用空白")

# ── 3. 生成 HTML ─────────────────────────────────────
eq   = bt.get("equity_curve", [100.0])
step = max(1, len(eq)//150)
eq_s = eq[::step]

months = bt.get("months", {})
ml = json.dumps(list(months.keys()))
mr = json.dumps([round(v["win_rate"]*100,1) for v in months.values()])
mc = json.dumps([v["total"] for v in months.values()])

models = bt.get("models", {})
rows = ""
for mid, d in sorted(models.items(), key=lambda x: -x[1]["win_rate"]):
    wr  = d["win_rate"]*100
    ico = "⭐" if wr>=65 else ("⚠" if wr<50 else "")
    bc  = "#00e5a0" if wr>=65 else ("#f5a623" if wr>=53 else "#ff4d6a")
    arc = "#00e5a0" if d["avg_return"]>0 else "#ff4d6a"
    rows += (
        f'<tr>'
        f'<td style="font-family:monospace;font-size:11px;color:#c8daea">{ico} {mid}</td>'
        f'<td style="text-align:right;font-family:monospace;font-size:11px;color:#8aa4b8">{d["total"]}</td>'
        f'<td style="text-align:right;font-family:monospace;font-weight:700;color:{bc}">{wr:.1f}%</td>'
        f'<td style="font-size:10px;color:#8aa4b8">{d["ci_lo"]:.0%}–{d["ci_hi"]:.0%}</td>'
        f'<td style="text-align:right;font-family:monospace;font-size:11px;color:{arc}">{d["avg_return"]:+.3%}</td>'
        f'</tr>'
        f'<tr><td colspan="5" style="padding:0 0 3px">'
        f'<div style="height:2px;background:#1e2d3d">'
        f'<div style="height:2px;width:{int(wr)}%;background:{bc}"></div>'
        f'</div></td></tr>'
    )

wr_val  = bt.get("win_rate_pct","N/A")
ci_str  = bt.get("ci_str","N/A")
z       = bt.get("z_score",0)
sharpe  = bt.get("sharpe",0)
mdd     = bt.get("max_drawdown",0)
cumret  = bt.get("cumulative_return",0)
avg_ret = bt.get("avg_return",0)
total   = bt.get("total",0)
correct = bt.get("correct",0)
spy_d   = bt.get("spy_days",0)
perm_p  = bt.get("perm_p","N/A")
gen_at  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

wrc = "#00e5a0" if bt.get("win_rate",0)>=0.58 else ("#f5a623" if bt.get("win_rate",0)>=0.53 else "#ff4d6a")
crc = "#00e5a0" if cumret>=0 else "#ff4d6a"
sc  = "#00e5a0" if sharpe>1 else "#f5a623"
zc  = "#00e5a0" if abs(z)>1.96 else "#f5a623"
sig = "✅ 统计显著" if bt.get("significant") else "⚠ 不显著"

eq_j = json.dumps(eq_s)

html = f"""<!DOCTYPE html>
<html lang="zh"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trump Code 监控看板</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#080c10;--bg2:#0d1318;--bg3:#111820;--border:#1e2d3d;--border2:#243447;
  --green:#00e5a0;--red:#ff4d6a;--amber:#f5a623;--blue:#3d9eff;
  --muted:#4a6178;--text:#c8daea;--text2:#8aa4b8}}
body{{background:var(--bg);color:var(--text);font-family:'DM Sans',system-ui,sans-serif;font-size:13px}}
body::before{{content:'';position:fixed;inset:0;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,229,160,.012) 2px,rgba(0,229,160,.012) 4px);
  pointer-events:none;z-index:999}}
header{{display:flex;align-items:center;justify-content:space-between;padding:12px 24px;
  border-bottom:1px solid var(--border);background:var(--bg2)}}
.logo{{font-family:monospace;font-size:14px;color:var(--green)}}
.badges{{display:flex;gap:8px;align-items:center}}
.badge{{font-family:monospace;font-size:9px;padding:3px 8px;border-radius:2px;letter-spacing:.06em}}
.br{{background:rgba(61,158,255,.1);color:var(--blue);border:1px solid rgba(61,158,255,.3)}}
.bp{{background:rgba(0,229,160,.08);color:var(--green);border:1px solid rgba(0,229,160,.2)}}
.bt{{color:var(--muted)}}
.g4{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:1px;background:var(--border);margin:1px 0}}
.kpi{{background:var(--bg2);padding:18px 22px}}
.kl{{font-family:monospace;font-size:9px;letter-spacing:.1em;color:var(--muted);text-transform:uppercase}}
.kv{{font-family:monospace;font-size:30px;font-weight:700;margin-top:6px;line-height:1}}
.ks{{font-size:10px;color:var(--text2);margin-top:4px}}
.sec{{background:var(--bg2);margin:1px 0;padding:18px 24px}}
.st{{font-family:monospace;font-size:9px;letter-spacing:.12em;color:var(--muted);text-transform:uppercase;
  margin-bottom:14px;display:flex;align-items:center;gap:8px}}
.st::after{{content:'';flex:1;height:1px;background:var(--border)}}
.two{{display:grid;grid-template-columns:2fr 1fr;gap:1px;background:var(--border);margin:1px 0}}
.half{{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--border);margin:1px 0}}
table{{width:100%;border-collapse:collapse}}
td,th{{padding:5px 4px;border-bottom:1px solid var(--border)}}
tr:last-child td{{border-bottom:none}}
th{{text-align:left;font-family:monospace;font-size:9px;color:var(--muted);padding-bottom:8px}}
.mb{{display:flex;flex-direction:column;gap:5px}}
.mbr{{display:flex;align-items:center;gap:8px}}
.mbl{{font-family:monospace;font-size:9px;color:var(--muted);width:52px;flex-shrink:0}}
.mbt{{flex:1;height:14px;background:var(--bg3);border-radius:2px;overflow:hidden}}
.mbf{{height:100%;border-radius:2px;transition:width 1.2s ease}}
.mbv{{font-family:monospace;font-size:9px;width:38px;text-align:right;flex-shrink:0}}
.mbn{{font-size:9px;color:var(--muted);width:28px;text-align:right}}
.daily{{background:var(--bg3);border:1px solid var(--border2);border-radius:4px;
  padding:14px;font-size:12px;color:var(--text2);line-height:1.7}}
.daily strong{{color:var(--text)}}
.sg{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.si{{background:var(--bg3);border:1px solid var(--border2);border-radius:3px;padding:10px 12px}}
.sl{{font-family:monospace;font-size:9px;color:var(--muted);letter-spacing:.08em}}
.sv{{font-family:monospace;font-size:18px;font-weight:700;margin-top:3px}}
footer{{padding:10px 24px;border-top:1px solid var(--border);background:var(--bg2);
  display:flex;justify-content:space-between}}
.fl{{font-family:monospace;font-size:9px;color:var(--muted)}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.dot{{display:inline-block;width:6px;height:6px;border-radius:50%;
  background:var(--green);animation:pulse 2s infinite;margin-right:4px}}
canvas{{max-height:240px}}
</style></head><body>

<header>
  <div class="logo">TRUMP/CODE &nbsp;<span style="color:#4a6178;font-size:10px">监控看板 · 真实SPY验证</span></div>
  <div class="badges">
    <span class="badge br">real_spy · 438条验证</span>
    <span class="badge bp"><span class="dot"></span>PAPER MODE</span>
    <span class="badge bt">{gen_at}</span>
  </div>
</header>

<div class="g4">
  <div class="kpi">
    <div class="kl">真实胜率（SPY价格验证）</div>
    <div class="kv" style="color:{wrc}">{wr_val}</div>
    <div class="ks">95% CI: {ci_str}</div>
  </div>
  <div class="kpi">
    <div class="kl">Z-score</div>
    <div class="kv" style="color:{zc}">{z:+.2f}</div>
    <div class="ks">{sig} · p={perm_p}</div>
  </div>
  <div class="kpi">
    <div class="kl">模拟累计收益</div>
    <div class="kv" style="color:{crc}">{cumret:+.1%}</div>
    <div class="ks">基于 {total:,} 条预测 · SPY {spy_d}天</div>
  </div>
  <div class="kpi">
    <div class="kl">Sharpe 年化</div>
    <div class="kv" style="color:{sc}">{sharpe:.2f}</div>
    <div class="ks">最大回撤 {mdd:.1%} · 均收益 {avg_ret:+.3%}</div>
  </div>
</div>

<div class="sec">
  <div class="st">模拟权益曲线（基准100，非真实资金）</div>
  <canvas id="eq" style="height:220px"></canvas>
</div>

<div class="two">
  <div class="sec">
    <div class="st">模型表现排行（真实SPY价格验证）</div>
    <table>
      <tr>
        <th>模型</th><th style="text-align:right">N</th>
        <th style="text-align:right">胜率</th><th>CI</th>
        <th style="text-align:right">均收益</th>
      </tr>
      {rows}
    </table>
  </div>
  <div class="sec">
    <div class="st">月度胜率</div>
    <div class="mb" id="mb"></div>
  </div>
</div>

<div class="half">
  <div class="sec">
    <div class="st">统计摘要</div>
    <div class="sg">
      <div class="si"><div class="sl">总预测</div>
        <div class="sv" style="color:var(--blue)">{total:,}</div></div>
      <div class="si"><div class="sl">正确次数</div>
        <div class="sv" style="color:var(--green)">{correct:,}</div></div>
      <div class="si"><div class="sl">平均每笔</div>
        <div class="sv" style="font-size:14px;color:{'var(--green)' if avg_ret>0 else 'var(--red)'}">{avg_ret:+.3%}</div></div>
      <div class="si"><div class="sl">SPY验证天数</div>
        <div class="sv" style="font-size:14px;color:var(--text)">{spy_d}</div></div>
    </div>
  </div>
  <div class="sec">
    <div class="st">今日日报（GitHub 实时）</div>
    <div class="daily">
      <strong>EN</strong><br>{daily_en or "（数据未获取）"}<br><br>
      <strong>中文</strong><br>{daily_zh or "—"}
    </div>
  </div>
</div>

<footer>
  <div class="fl">TRUMP CODE · PAPER TRADING ONLY · NOT FINANCIAL ADVICE · 过去表现不代表未来</div>
  <div class="fl">数据: GitHub sstklen/trump-code + Yahoo Finance · {gen_at}</div>
</footer>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
const EQ = {eq_j};
const ML = {ml};
const MR = {mr};
const MC = {mc};

(function() {{
  const ctx = document.getElementById('eq').getContext('2d');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: EQ.map((_,i) => i),
      datasets: [
        {{
          label: '模拟权益',
          data: EQ,
          borderColor: '#00e5a0',
          backgroundColor: 'rgba(0,229,160,.07)',
          borderWidth: 1.5,
          pointRadius: 0,
          tension: .3,
          fill: true,
        }},
        {{
          label: '基准100',
          data: EQ.map(() => 100),
          borderColor: '#243447',
          borderWidth: 1,
          borderDash: [4,4],
          pointRadius: 0,
        }}
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{labels: {{color:'#8aa4b8',font:{{size:9}},boxWidth:10,usePointStyle:true}}}},
        tooltip: {{
          backgroundColor:'#111820',borderColor:'#1e2d3d',borderWidth:1,
          titleColor:'#4a6178',bodyColor:'#c8daea',
          callbacks: {{label: c => `${{c.dataset.label}}: ${{c.parsed.y.toFixed(2)}}`}}
        }}
      }},
      scales: {{
        x: {{display: false}},
        y: {{
          ticks: {{color:'#4a6178',font:{{size:8}},callback:v=>v.toFixed(1)}},
          grid: {{color:'rgba(30,45,61,.5)'}}
        }}
      }}
    }},
    plugins: [{{
      id: 'mutLine',
      afterDraw(chart) {{
        const {{ctx:c,chartArea:a,scales:s}} = chart;
        const x = s.x.getPixelForValue(Math.floor(EQ.length*0.75));
        c.save();
        c.beginPath(); c.moveTo(x,a.top); c.lineTo(x,a.bottom);
        c.strokeStyle='rgba(245,166,35,.4)'; c.lineWidth=1;
        c.setLineDash([4,3]); c.stroke();
        c.fillStyle='rgba(245,166,35,.7)';
        c.font='9px monospace';
        c.fillText('DEC MUTATION',x+4,a.top+12);
        c.restore();
      }}
    }}]
  }});
}})();

(function() {{
  const wrap = document.getElementById('mb');
  ML.forEach((ym,i) => {{
    const wr=MR[i], n=MC[i];
    const color = wr>=65?'#00e5a0': wr>=53?'#f5a623':'#ff4d6a';
    const row = document.createElement('div');
    row.className='mbr';
    row.innerHTML=`
      <span class="mbl">${{ym.slice(2)}}</span>
      <div class="mbt"><div class="mbf" style="width:${{wr}}%;background:${{color}}"></div></div>
      <span class="mbv" style="color:${{color}}">${{wr}}%</span>
      <span class="mbn">${{n}}次</span>`;
    wrap.appendChild(row);
  }});
}})();
</script>
</body></html>"""

# ── 4. 写文件 ────────────────────────────────────────
out = Path("trump_dashboard.html")
out.write_text(html, encoding="utf-8")
print(f"\n✅ trump_dashboard.html 已生成")
print(f"   胜率:   {wr_val}")
print(f"   Sharpe: {sharpe:.2f}")
print(f"   累计:   {cumret:+.2%}")
print(f"   回撤:   {mdd:.2%}")
print(f"\n下一步: 复制到 trump-dashboard-auto/docs/index.html 并 git push")
