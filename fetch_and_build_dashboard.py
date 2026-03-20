import json,math,random,time,sys,logging,ssl,urllib.request,warnings,subprocess,platform
from pathlib import Path
from datetime import datetime,timezone,timedelta
from statistics import mean,stdev
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s",datefmt="%H:%M:%S")
log=logging.getLogger(__name__)
DATA_DIR=Path("data");DATA_DIR.mkdir(exist_ok=True)
RESULTS_DIR=Path("paper_results");RESULTS_DIR.mkdir(exist_ok=True)
RAW="https://raw.githubusercontent.com/sstklen/trump-code/main"
FILES={"predictions_log.json":f"{RAW}/data/predictions_log.json","daily_report.json":f"{RAW}/data/daily_report.json","surviving_rules.json":f"{RAW}/data/surviving_rules.json","x_truth_gap.json":f"{RAW}/data/x_truth_gap.json"}
TICKERS={"market_SP500.json":"SPY","market_BTC.json":"BTC-USD","market_GOLD.json":"GC=F","market_VIX.json":"^VIX"}
def ctx():
    c=ssl.create_default_context();c.check_hostname=False;c.verify_mode=ssl.CERT_NONE;return c
def get(url,timeout=20):
    req=urllib.request.Request(url,headers={"User-Agent":"trump-code/1.0"})
    with urllib.request.urlopen(req,context=ctx(),timeout=timeout) as r:return r.read()
def fetch_github():
    print("\n── STEP 1/3 GitHub 真实数据 ─────────────────");ok=0
    for fname,url in FILES.items():
        local=DATA_DIR/fname
        if local.exists() and local.stat().st_size>200:log.info("已缓存 %.1fKB %s",local.stat().st_size/1024,fname);ok+=1;continue
        try:
            data=json.loads(get(url));local.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
            log.info("✅ %.1fKB %s",local.stat().st_size/1024,fname);ok+=1;time.sleep(0.3)
        except Exception as e:log.warning("❌ %s → %s",fname,e)
    print(f" {ok}/{len(FILES)} 文件就绪")
def fetch_market():
    print("\n── STEP 2/3 市场价格 Yahoo Finance ──────────")
    try:import requests;session=requests.Session();session.verify=False
    except ImportError:log.error("requests未安装");return
    ok=0
    for fname,ticker in TICKERS.items():
        local=DATA_DIR/fname
        if local.exists() and local.stat().st_size>500:log.info("已缓存 %s (%s)",fname,ticker);ok+=1;continue
        try:
            url=f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2y"
            r=session.get(url,timeout=15,headers={"User-Agent":"Mozilla/5.0"});r.raise_for_status()
            raw=r.json();ts=raw["chart"]["result"][0]["timestamp"]
            close=raw["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            open_=raw["chart"]["result"][0]["indicators"]["quote"][0].get("open",close)
            records={}
            for i,t in enumerate(ts):
                if close[i] is None:continue
                d=datetime.fromtimestamp(t,tz=timezone.utc).strftime("%Y-%m-%d")
                records[d]={"open":round(float(open_[i] or close[i]),4),"close":round(float(close[i]),4)}
            local.write_text(json.dumps(records,indent=2));log.info("✅ %s %d天",ticker,len(records));ok+=1;time.sleep(0.5)
        except Exception as e:log.warning("❌ %s → %s",ticker,e)
    print(f" {ok}/{len(TICKERS)} 资产就绪")
def wilson(c,n,z=1.96):
    if n==0:return 0.0,1.0
    p=c/n;d=1+z**2/n;ctr=(p+z**2/(2*n))/d;mg=z*math.sqrt(p*(1-p)/n+z**2/(4*n**2))/d
    return round(max(0,ctr-mg),4),round(min(1,ctr+mg),4)
def perm_p(c,n,k=10000):
    if n==0:return 1.0
    obs=c/n;random.seed(0)
    return round(sum(1 for _ in range(k) if sum(random.random()>.5 for _ in range(n))/n>=obs)/k,5)
def spy_ret(date,hold,spy,dates):
    if date not in spy or date not in dates:return None
    try:
        i=dates.index(date);j=i+hold
        if j>=len(dates):return None
        e=spy[dates[i]]["close"];x=spy[dates[j]]["close"];return(x-e)/e
    except:return None
def backtest():
    print("\n── STEP 3/3 回溯分析 ────────────────────────")
    plog=DATA_DIR/"predictions_log.json";spyf=DATA_DIR/"market_SP500.json"
    if not plog.exists():log.error("无预测数据");return{}
    raw=json.loads(plog.read_text(encoding="utf-8"))
    preds=raw if isinstance(raw,list) else[{**v,"date":k}for k,v in raw.items() if isinstance(v,dict)]
    spy=json.loads(spyf.read_text())if spyf.exists()else{}
    dates=sorted(spy);log.info("预测记录 %d条 | SPY %d天",len(preds),len(spy))
    total=0;correct=0;rets=[];equity=[100.0];by_model={};by_month={}
    for rec in preds:
        date=rec.get("date","")[:10];dir_=rec.get("direction",rec.get("signal","BULLISH"))
        hold=int(rec.get("hold_days",rec.get("holding_period",1)));model=rec.get("model",rec.get("model_id","?"))
        actual=spy_ret(date,hold,spy,dates)
        if actual is not None:signed=actual if dir_=="BULLISH" else-actual;ok=signed>0
        else:ok=bool(rec.get("correct",rec.get("is_correct",False)));signed=float(rec.get("market_return",rec.get("return",0.0)))
        total+=1;correct+=int(ok);rets.append(signed);equity.append(equity[-1]*(1+signed))
        m=by_model.setdefault(model,{"c":0,"n":0,"r":[]});m["n"]+=1;m["c"]+=int(ok);m["r"].append(signed)
        ym=by_month.setdefault(date[:7],{"c":0,"n":0});ym["n"]+=1;ym["c"]+=int(ok)
    if total==0:return{}
    wr=correct/total;clo,chi=wilson(correct,total);z=(wr-.5)/math.sqrt(.25/total)
    avg=mean(rets)if rets else 0
    std=stdev(rets)if len(rets)>1 else 0
    sharpe=(avg/std*math.sqrt(252))if std>0 else 0
    peak=equity[0];mdd=0
    for v in equity:peak=max(peak,v);mdd=min(mdd,(v-peak)/peak)
    models_out={}
    for mid,d in by_model.items():
        if d["n"]==0:continue
        mwr=d["c"]/d["n"];mci=wilson(d["c"],d["n"]);mavg=mean(d["r"])if d["r"]else 0
        models_out[mid]={"win_rate":round(mwr,4),"total":d["n"],"avg_return":round(mavg,6),"ci_lo":mci[0],"ci_hi":mci[1]}
    months_out={}
    for ym,d in sorted(by_month.items()):
        mwr=d["c"]/d["n"]if d["n"]else 0;months_out[ym]={"win_rate":round(mwr,4),"total":d["n"]}
    result={"total":total,"correct":correct,"win_rate":round(wr,4),"win_rate_pct":f"{wr:.1%}","ci_lo":clo,"ci_hi":chi,"ci_str":f"{clo:.1%}–{chi:.1%}","z_score":round(z,3),"significant":abs(z)>1.96,"avg_return":round(avg,6),"sharpe":round(sharpe,3),"max_drawdown":round(mdd,4),"cumulative_return":round(equity[-1]/equity[0]-1,4),"equity_curve":[round(v,4)for v in equity],"models":models_out,"months":months_out,"spy_days":len(spy),"data_source":"real_spy"if spy else"log_only","perm_p":perm_p(correct,total),"generated_at":datetime.now(timezone.utc).isoformat()}
    print(f"\n{'='*52}\n TRUMP CODE · REAL DATA BACKTEST\n{'='*52}")
    print(f" 数据来源 {result['data_source']}\n 预测总数 {total:,}\n 真实胜率 {wr:.2%}\n 95% CI {clo:.2%} – {chi:.2%}\n Z-score {z:+.2f} ({'✅ 显著' if abs(z)>1.96 else '⚠ 不显著'})\n Sharpe {sharpe:.2f}\n 最大回撤 {mdd:.2%}\n 累计收益 {result['cumulative_return']:+.2%}")
    print(f"\n {'模型':<8} {'N':>4} {'胜率':>6} {'置信区间':>14}")
    for mid,d in sorted(models_out.items(),key=lambda x:-x[1]["win_rate"]):
        ico="⭐"if d["win_rate"]>=.65 else("⚠ "if d["win_rate"]<.50 else" ")
        print(f" {ico}{mid:<6} {d['total']:>4} {d['win_rate']:>6.1%} [{d['ci_lo']:.1%}–{d['ci_hi']:.1%}]")
    print(f"\n 月度胜率")
    for ym,d in months_out.items():
        flag=" ⚠"if d["win_rate"]<.53 else""
        print(f" {ym} {d['total']:>3}次 {d['win_rate']:.1%}{flag}")
    print(f"{'='*52}")
    (RESULTS_DIR/"real_backtest.json").write_text(json.dumps(result,indent=2,ensure_ascii=False))
    return result

def build_html(bt):
    daily_en=daily_zh=""
    dp=DATA_DIR/"daily_report.json"
    if dp.exists():
        try:
            dr=json.loads(dp.read_text(encoding="utf-8"))
            daily_en=dr.get("summary",{}).get("en","")or dr.get("en","")
            daily_zh=dr.get("summary",{}).get("zh","")or dr.get("zh","")
        except:pass

    # === 动态更新信息 ===
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S PDT")
    dynamic_update = f'''
    <div style="text-align:center; font-size:11px; color:#8aa4b8; margin:20px 0; padding:10px; background:#0d1318; border:1px solid #1e2d3d; border-radius:6px;">
        <strong>Last Updated:</strong> {now_str}  |  Win Rate: {bt.get("win_rate_pct", "N/A")}  |  Sharpe: {bt.get("sharpe", "?")}
    </div>
    '''

    eq=bt.get("equity_curve",[100.0]);step=max(1,len(eq)//120);eq_s=eq[::step]
    months=bt.get("months",{})
    ml=json.dumps(list(months.keys()));mr=json.dumps([round(v["win_rate"]*100,1)for v in months.values()]);mc=json.dumps([v["total"]for v in months.values()])
    models=bt.get("models",{})
    rows=""
    for mid,d in sorted(models.items(),key=lambda x:-x[1]["win_rate"]):
        wr=d["win_rate"]*100;ico="⭐"if wr>=65 else("⚠"if wr<50 else"")
        bc="#00e5a0"if wr>=65 else("#f5a623"if wr>=53 else"#ff4d6a")
        rows+=f'<tr><td style="font-family:monospace;font-size:11px">{ico} {mid}</td><td style="text-align:right;font-family:monospace;font-size:11px">{d["total"]}</td><td style="text-align:right;font-family:monospace;font-weight:700;color:{bc}">{wr:.1f}%</td><td style="font-size:10px;color:#8aa4b8">{d["ci_lo"]:.0%}–{d["ci_hi"]:.0%}</td><td style="text-align:right;font-family:monospace;font-size:11px;color:{"#00e5a0"if d["avg_return"]>0 else"#ff4d6a"}">{d["avg_return"]:+.3%}</td></tr><tr><td colspan="5" style="padding:0 0 3px"><div style="height:2px;background:#1e2d3d"><div style="height:2px;width:{int(wr)}%;background:{bc}"></div></div></td></tr>'
    wrc="#00e5a0"if bt.get("win_rate",0)>=.58 else("#f5a623"if bt.get("win_rate",0)>=.53 else"#ff4d6a")
    crc="#00e5a0"if bt.get("cumulative_return",0)>=0 else"#ff4d6a"
    sc="#00e5a0"if bt.get("sharpe",0)>1 else"#f5a623"
    zc="#00e5a0"if abs(bt.get("z_score",0))>1.96 else"#f5a623"
    gen=bt.get("generated_at","")[:19].replace("T"," ")+" UTC"
    eq_j=json.dumps(eq_s)
    pp=str(bt.get("perm_p","N/A"))
    return f"""<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Trump Code 监控看板</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#080c10;--bg2:#0d1318;--bg3:#111820;--border:#1e2d3d;--border2:#243447;--green:#00e5a0;--red:#ff4d6a;--amber:#f5a623;--blue:#3d9eff;--muted:#4a6178;--text:#c8daea;--text2:#8aa4b8}}
body{{background:var(--bg);color:var(--text);font-family:'DM Sans',system-ui,sans-serif;font-size:13px}}
body::before{{content:'';position:fixed;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,229,160,.012) 2px,rgba(0,229,160,.012) 4px);pointer-events:none;z-index:999}}
header{{display:flex;align-items:center;justify-content:space-between;padding:12px 24px;border-bottom:1px solid var(--border);background:var(--bg2)}}
.logo{{font-family:monospace;font-size:14px;color:var(--green)}}
.badges{{display:flex;gap:8px}}
.badge{{font-family:monospace;font-size:9px;padding:3px 8px;border-radius:2px;letter-spacing:.06em}}
.badge.r{{background:rgba(61,158,255,.1);color:var(--blue);border:1px solid rgba(61,158,255,.3)}}
.badge.p{{background:rgba(0,229,160,.08);color:var(--green);border:1px solid rgba(0,229,160,.2)}}
.badge.t{{color:var(--muted)}}
.grid4{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:1px;background:var(--border);margin:1px 0}}
.kpi{{background:var(--bg2);padding:18px 22px}}
.kl{{font-family:monospace;font-size:9px;letter-spacing:.1em;color:var(--muted);text-transform:uppercase}}
.kv{{font-family:monospace;font-size:30px;font-weight:700;margin-top:6px;line-height:1}}
.ks{{font-size:10px;color:var(--text2);margin-top:4px}}
.sec{{background:var(--bg2);margin:1px 0;padding:18px 24px}}
.st{{font-family:monospace;font-size:9px;letter-spacing:.12em;color:var(--muted);text-transform:uppercase;margin-bottom:14px;display:flex;align-items:center;gap:8px}}
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
.mbf{{height:100%;border-radius:2px}}
.mbv{{font-family:monospace;font-size:9px;width:38px;text-align:right;flex-shrink:0}}
.mbn{{font-size:9px;color:var(--muted);width:28px;text-align:right}}
.daily{{background:var(--bg3);border:1px solid var(--border2);border-radius:4px;padding:14px;font-size:12px;color:var(--text2);line-height:1.7}}
.daily strong{{color:var(--text)}}
.sg{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.si{{background:var(--bg3);border:1px solid var(--border2);border-radius:3px;padding:10px 12px}}
.sl{{font-family:monospace;font-size:9px;color:var(--muted);letter-spacing:.08em}}
.sv{{font-family:monospace;font-size:18px;font-weight:700;margin-top:3px}}
footer{{padding:10px 24px;border-top:1px solid var(--border);background:var(--bg2);display:flex;justify-content:space-between}}
.fl{{font-family:monospace;font-size:9px;color:var(--muted)}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.dot{{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s infinite;margin-right:4px}}
canvas{{max-height:220px}}
</style>
</head><body>
<header>
<div class="logo">TRUMP/CODE &nbsp;<span style="color:#4a6178;font-size:10px">监控看板 · 真实数据</span></div>
<div class="badges">
<span class="badge r">真实数据 · {bt.get("data_source","")}</span>
<span class="badge p"><span class="dot"></span>PAPER MODE</span>
<span class="badge t">{gen}</span>
</div></header>
<div class="grid4">
<div class="kpi"><div class="kl">真实胜率</div><div class="kv" style="color:{wrc}">{bt.get("win_rate_pct","N/A")}</div><div class="ks">95% CI: {bt.get("ci_str","N/A")}</div></div>
<div class="kpi"><div class="kl">Z-score</div><div class="kv" style="color:{zc}">{bt.get("z_score",0):+.2f}</div><div class="ks">{'✅ 统计显著 p=' if bt.get("significant") else '⚠ 不显著 p='}{pp}</div></div>
<div class="kpi"><div class="kl">模拟累计收益</div><div class="kv" style="color:{crc}">{bt.get("cumulative_return",0):+.1%}</div><div class="ks">基于 {bt.get("total",0):,} 条预测</div></div>
<div class="kpi"><div class="kl">Sharpe 年化</div><div class="kv" style="color:{sc}">{bt.get("sharpe",0):.2f}</div><div class="ks">最大回撤 {bt.get("max_drawdown",0):.1%} · SPY {bt.get("spy_days",0)}天</div></div>
</div>
<div class="sec"><div class="st">模拟权益曲线（基准100，非真实资金）</div><canvas id="eq"></canvas></div>
<div class="two">
<div class="sec"><div class="st">模型表现排行（真实回测数据）</div>
<table><tr><th>模型</th><th style="text-align:right">N</th><th style="text-align:right">胜率</th><th>CI</th><th style="text-align:right">均收益</th></tr>{rows}</table></div>
<div class="sec"><div class="st">月度胜率</div><div class="mb" id="mb"></div></div>
</div>
<div class="half">
<div class="sec"><div class="st">统计摘要</div><div class="sg">
<div class="si"><div class="sl">总预测</div><div class="sv" style="color:var(--blue)">{bt.get("total",0):,}</div></div>
<div class="si"><div class="sl">正确</div><div class="sv" style="color:var(--green)">{bt.get("correct",0):,}</div></div>
<div class="si"><div class="sl">平均每笔</div><div class="sv" style="font-size:14px;color:{'var(--green)'if bt.get('avg_return',0)>0 else'var(--red)'}">{bt.get("avg_return",0):+.3%}</div></div>
<div class="si"><div class="sl">SPY数据天数</div><div class="sv" style="font-size:14px;color:var(--text)">{bt.get("spy_days",0)}</div></div>
</div></div>
<div class="sec"><div class="st">今日日报（GitHub 实时）</div>
<div class="daily"><strong>EN</strong><br>{daily_en or"（数据未获取）"}<br><br><strong>中文</strong><br>{daily_zh or"—"}</div>
</div>
{dynamic_update}
<footer><div class="fl">TRUMP CODE · PAPER TRADING ONLY · NOT FINANCIAL ADVICE · 过去表现不代表未来</div><div class="fl">数据: GitHub sstklen/trump-code + Yahoo Finance</div></footer>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
const EQ={eq_j};const ML={ml};const MR={mr};const MC={mc};
(function(){{const ctx=document.getElementById('eq').getContext('2d');
new Chart(ctx,{{type:'line',data:{{labels:EQ.map((_,i)=>i),datasets:[{{label:'模拟权益',data:EQ,borderColor:'#00e5a0',backgroundColor:'rgba(0,229,160,.07)',borderWidth:1.5,pointRadius:0,tension:.3,fill:true}},{{label:'基准100',data:EQ.map(()=>100),borderColor:'#243447',borderWidth:1,borderDash:[4,4],pointRadius:0}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#8aa4b8',font:{{size:9}},boxWidth:10,usePointStyle:true}}}},tooltip:{{backgroundColor:'#111820',borderColor:'#1e2d3d',borderWidth:1,titleColor:'#4a6178',bodyColor:'#c8daea',callbacks:{{label:c=>`${{c.dataset.label}}: ${{c.parsed.y.toFixed(2)}}`}}}}}},scales:{{x:{{display:false}},y:{{ticks:{{color:'#4a6178',font:{{size:8}},callback:v=>v.toFixed(1)}},grid:{{color:'rgba(30,45,61,.5)'}}}}}}}},plugins:[{{id:'ml',afterDraw(chart){{const{{ctx:c,chartArea:a,scales:s}}=chart;const x=s.x.getPixelForValue(Math.floor(EQ.length*.75));c.save();c.beginPath();c.moveTo(x,a.top);c.lineTo(x,a.bottom);c.strokeStyle='rgba(245,166,35,.35)';c.lineWidth=1;c.setLineDash([4,3]);c.stroke();c.fillStyle='rgba(245,166,35,.6)';c.font='9px monospace';c.fillText('DEC MUTATION',x+4,a.top+12);c.restore();}}}}]}})}})();
(function(){{const w=document.getElementById('mb');ML.forEach((ym,i)=>{{const wr=MR[i];const n=MC[i];const color=wr>=65?'#00e5a0':wr>=53?'#f5a623':'#ff4d6a';const r=document.createElement('div');r.className='mbr';r.innerHTML=`<span class="mbl">${{ym.slice(2)}}</span><div class="mbt"><div class="mbf" style="width:${{wr}}%;background:${{color}}"></div></div><span class="mbv" style="color:${{color}}">${{wr}}%</span><span class="mbn">${{n}}次</span>`;w.appendChild(r);}});}})();
</script></body></html>"""

def main():
    print("\n"+"="*55+"\n TRUMP CODE · 真实数据接入 + 看板生成\n ⚠ PAPER MODE — 不涉及任何真实资金\n"+"="*55)
    fetch_github()
    fetch_market()
    bt=backtest()
    if not bt:print("\n❌ 回溯失败");sys.exit(1)
    print("\n── 生成看板 HTML ─────────────────────────────")
    html=build_html(bt)
    out=Path("trump_dashboard.html")
    out.write_text(html,encoding="utf-8")
    log.info("✅ 看板已生成: %s",out.resolve())
    print(f"\n{'='*55}\n ✅ 全部完成！\n 看板文件 trump_dashboard.html\n 双击用浏览器打开\n 回测结果 paper_results/real_backtest.json\n{'='*55}\n ⚠ 仅供研究，不构成投资建议\n{'='*55}")
    if platform.system()=="Darwin":subprocess.Popen(["open",str(out)]);print(" 浏览器正在打开...")
if __name__=="__main__":main()
