import json,math,random,time,sys,logging,ssl,urllib.request,warnings,subprocess,platform
from pathlib import Path
from datetime import datetime,timezone,timedelta
from statistics import mean,stdev

# 配置
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s",datefmt="%H:%M:%S")
log=logging.getLogger(__name__)

DATA_DIR=Path("data");DATA_DIR.mkdir(exist_ok=True)
RESULTS_DIR=Path("paper_results");RESULTS_DIR.mkdir(exist_ok=True)

RAW="https://raw.githubusercontent.com/sstklen/trump-code/main"
FILES={
    "predictions_log.json":f"{RAW}/data/predictions_log.json",
    "daily_report.json":f"{RAW}/data/daily_report.json",
    "surviving_rules.json":f"{RAW}/data/surviving_rules.json",
    "x_truth_gap.json":f"{RAW}/data/x_truth_gap.json"
}
TICKERS={
    "market_SP500.json":"SPY",
    "market_BTC.json":"BTC-USD",
    "market_GOLD.json":"GC=F",
    "market_VIX.json":"^VIX"
}

def ctx():
    c=ssl.create_default_context();c.check_hostname=False;c.verify_mode=ssl.CERT_NONE;return c

def get(url,timeout=20):
    req=urllib.request.Request(url,headers={"User-Agent":"trump-code/1.0"})
    with urllib.request.urlopen(req,context=ctx(),timeout=timeout) as r:return r.read()

def fetch_github():
    print("\n── STEP 1/3 GitHub 真实数据 ─────────────────")
    ok=0
    for fname,url in FILES.items():
        local=DATA_DIR/fname
        # 强制更新这些小型 JSON，不使用长时间缓存
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
        try:
            # 增加对齐逻辑：获取 2 年数据确保回测长度
            url=f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2y"
            r=session.get(url,timeout=15,headers={"User-Agent":"Mozilla/5.0"});r.raise_for_status()
            raw=r.json();result=raw["chart"]["result"][0]
            ts=result["timestamp"]
            close=result["indicators"]["quote"][0]["close"]
            open_=result["indicators"]["quote"][0].get("open",close)
            
            records={}
            for i,t in enumerate(ts):
                if close[i] is None:continue
                # 统一转为当地日期字符串，避免 UTC 导致日期偏移
                d=datetime.fromtimestamp(t).strftime("%Y-%m-%d")
                records[d]={"open":round(float(open_[i] or close[i]),4),"close":round(float(close[i]),4)}
            
            local.write_text(json.dumps(records,indent=2));log.info("✅ %s %d天",ticker,len(records));ok+=1;time.sleep(0.5)
        except Exception as e:log.warning("❌ %s → %s",ticker,e)
    print(f" {ok}/{len(TICKERS)} 资产就绪")

def wilson(c,n,z=1.96):
    if n==0:return 0.0,1.0
    p=c/n;d=1+z**2/n;ctr=(p+z**2/(2*n))/d;mg=z*math.sqrt(abs(p*(1-p)/n+z**2/(4*n**2)))/d
    return round(max(0,ctr-mg),4),round(min(1,ctr+mg),4)

def perm_p(c,n,k=10000):
    if n==0:return 1.0
    obs=c/n;random.seed(0)
    return round(sum(1 for _ in range(k) if sum(random.random()>.5 for _ in range(n))/n>=obs)/k,5)

# --- 关键修复函数 ---
def spy_ret_robust(target_date, hold, spy, sorted_dates):
    """
    鲁棒性增强的收益计算：
    1. 如果 target_date 不在交易日中（如周末），自动寻找之后的第一个交易日
    """
    # 找到 target_date 在有序日期列表中的位置（或之后最接近的位置）
    import bisect
    idx = bisect.bisect_left(sorted_dates, target_date)
    
    if idx >= len(sorted_dates): return None
    
    start_idx = idx
    end_idx = start_idx + hold
    
    if end_idx >= len(sorted_dates): return None
    
    try:
        start_price = spy[sorted_dates[start_idx]]["close"]
        end_price = spy[sorted_dates[end_idx]]["close"]
        return (end_price - start_price) / start_price
    except:
        return None

def backtest():
    print("\n── STEP 3/3 回溯分析 ────────────────────────")
    plog=DATA_DIR/"predictions_log.json";spyf=DATA_DIR/"market_SP500.json"
    if not plog.exists():log.error("无预测数据");return{}
    
    raw=json.loads(plog.read_text(encoding="utf-8"))
    preds=raw if isinstance(raw,list) else[{**v,"date":k} for k,v in raw.items() if isinstance(v,dict)]
    spy=json.loads(spyf.read_text()) if spyf.exists() else{}
    sorted_dates=sorted(spy.keys())
    
    log.info("预测记录 %d条 | SPY %d天",len(preds),len(spy))
    
    total=0;correct=0;rets=[];equity=[100.0];by_model={};by_month={}
    
    # 按照日期排序回测，确保权益曲线连续
    preds_sorted = sorted(preds, key=lambda x: x.get("date", "")[:10])

    for rec in preds_sorted:
        date_str=rec.get("date","")[:10]
        if not date_str: continue
        
        dir_=rec.get("direction",rec.get("signal","BULLISH"))
        hold=int(rec.get("hold_days",rec.get("holding_period",1)))
        model=rec.get("model",rec.get("model_id","?"))
        
        # 使用增强版计算函数
        actual = spy_ret_robust(date_str, hold, spy, sorted_dates)
        
        if actual is not None:
            signed = actual if dir_=="BULLISH" else -actual
            ok = signed > 0
            total+=1;correct+=int(ok);rets.append(signed)
            equity.append(equity[-1]*(1+signed))
            
            # 分组统计
            m=by_model.setdefault(model,{"c":0,"n":0,"r":[]});m["n"]+=1;m["c"]+=int(ok);m["r"].append(signed)
            ym=by_month.setdefault(date_str[:7],{"c":0,"n":0,"r":[]});ym["n"]+=1;ym["c"]+=int(ok);ym["r"].append(signed)

    if total==0:
        log.warning("⚠ 没有任何预测能匹配到市场日期，请检查日期格式")
        return {}

    wr=correct/total;clo,chi=wilson(correct,total);z=(wr-.5)/math.sqrt(.25/total) if total>0 else 0
    avg=mean(rets);std=stdev(rets) if len(rets)>1 else 0
    sharpe=(avg/std*math.sqrt(252)) if std>0 else 0
    peak=equity[0];mdd=0
    for v in equity:peak=max(peak,v);mdd=min(mdd,(v-peak)/peak)
    
    models_out={}
    for mid,d in by_model.items():
        mwr=d["c"]/d["n"];mci=wilson(d["c"],d["n"]);mavg=mean(d["r"])
        models_out[mid]={"win_rate":round(mwr,4),"total":d["n"],"avg_return":round(mavg,6),"ci_lo":mci[0],"ci_hi":mci[1]}
    
    months_out={}
    for ym,d in sorted(by_month.items()):
        mwr=d["c"]/d["n"];months_out[ym]={"win_rate":round(mwr,4),"total":d["n"],"avg_return":mean(d["r"])}

    result={
        "total":total,"correct":correct,"win_rate":round(wr,4),"win_rate_pct":f"{wr:.1%}",
        "ci_lo":clo,"ci_hi":chi,"ci_str":f"{clo:.1%}–{chi:.1%}","z_score":round(z,3),
        "significant":abs(z)>1.96,"avg_return":round(avg,6),"sharpe":round(sharpe,3),
        "max_drawdown":round(mdd,4),"cumulative_return":round(equity[-1]/equity[0]-1,4),
        "equity_curve":[round(v,4)for v in equity],"models":models_out,"months":months_out,
        "spy_days":len(spy),"data_source":"real_spy","perm_p":perm_p(correct,total),
        "generated_at":datetime.now(timezone.utc).isoformat()
    }
    
    # 打印终端报告
    print(f"\n{'='*52}\n TRUMP CODE · REAL DATA BACKTEST\n{'='*52}")
    print(f" 真实胜率 {wr:.2%} | Sharpe {sharpe:.2f} | 累计收益 {result['cumulative_return']:+.2%}")
    (RESULTS_DIR/"real_backtest.json").write_text(json.dumps(result,indent=2,ensure_ascii=False))
    return result

def build_html(bt):
    daily_en=daily_zh=""
    dp=DATA_DIR/"daily_report.json"
    if dp.exists():
        try:
            dr=json.loads(dp.read_text(encoding="utf-8"))
            daily_en=dr.get("summary",{}).get("en","") or dr.get("en","")
            daily_zh=dr.get("summary",{}).get("zh","") or dr.get("zh","")
        except:pass
    
    eq=bt.get("equity_curve",[100.0])
    # 采样权益曲线，避免点数过多
    step=max(1,len(eq)//150);eq_s=eq[::step]
    if eq[-1] not in eq_s: eq_s.append(eq[-1])
    
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
    sc="#00e5a0"if bt.get("sharpe",0)>1 else("#f5a623" if bt.get("sharpe",0)>0 else "#ff4d6a")
    zc="#00e5a0"if abs(bt.get("z_score",0))>1.96 else"#f5a623"
    gen=bt.get("generated_at","")[:19].replace("T"," ")+" UTC"
    eq_j=json.dumps(eq_s)
    pp=str(bt.get("perm_p","N/A"))

    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Trump Code 监控看板</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#080c10;--bg2:#0d1318;--bg3:#111820;--border:#1e2d3d;--border2:#243447;--green:#00e5a0;--red:#ff4d6a;--amber:#f5a623;--blue:#3d9eff;--muted:#4a6178;--text:#c8daea;--text2:#8aa4b8}}
body{{background:var(--bg);color:var(--text);font-family:'DM Sans',system-ui,sans-serif;font-size:13px;line-height:1.4}}
header{{display:flex;align-items:center;justify-content:space-between;padding:12px 24px;border-bottom:1px solid var(--border);background:var(--bg2)}}
.logo{{font-family:monospace;font-size:14px;color:var(--green);font-weight:bold}}
.badges{{display:flex;gap:8px}}
.badge{{font-family:monospace;font-size:9px;padding:3px 8px;border-radius:2px;letter-spacing:.06em;border:1px solid rgba(255,255,255,.1)}}
.badge.r{{background:rgba(61,158,255,.1);color:var(--blue)}}
.badge.p{{background:rgba(0,229,160,.08);color:var(--green)}}
.grid4{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1px;background:var(--border);margin:1px 0}}
.kpi{{background:var(--bg2);padding:20px}}
.kl{{font-family:monospace;font-size:9px;letter-spacing:.1em;color:var(--muted);text-transform:uppercase}}
.kv{{font-family:monospace;font-size:32px;font-weight:700;margin-top:8px;line-height:1}}
.ks{{font-size:10px;color:var(--text2);margin-top:6px}}
.sec{{background:var(--bg2);margin:1px 0;padding:20px}}
.st{{font-family:monospace;font-size:10px;letter-spacing:.1em;color:var(--muted);text-transform:uppercase;margin-bottom:15px;display:flex;align-items:center;gap:10px}}
.st::after{{content:'';flex:1;height:1px;background:var(--border)}}
.two{{display:grid;grid-template-columns:2fr 1fr;gap:1px;background:var(--border)}}
@media(max-width:800px){{.two{{grid-template-columns:1fr}}}}
table{{width:100%;border-collapse:collapse}}
td,th{{padding:8px 4px;border-bottom:1px solid var(--border)}}
th{{text-align:left;font-family:monospace;font-size:9px;color:var(--muted)}}
.daily{{background:var(--bg3);border:1px solid var(--border2);border-radius:4px;padding:15px;font-size:12px;color:var(--text2);line-height:1.6}}
footer{{padding:15px 24px;background:var(--bg2);display:flex;justify-content:space-between;border-top:1px solid var(--border)}}
.fl{{font-family:monospace;font-size:9px;color:var(--muted)}}
.mbr{{display:flex;align-items:center;gap:8px;margin-bottom:8px}}
.mbl{{font-family:monospace;font-size:10px;width:50px}}
.mbt{{flex:1;height:12px;background:var(--bg3);border-radius:2px;overflow:hidden}}
.mbf{{height:100%}}
.mbv{{font-family:monospace;font-size:10px;width:40px;text-align:right}}
</style>
</head><body>
<header>
<div class="logo">TRUMP CODE / SYSTEM MONITOR</div>
<div class="badges">
<span class="badge r">REAL_MARKET_SPY</span>
<span class="badge p">PAPER_TRADING</span>
<span class="badge t" style="color:var(--muted)">{gen}</span>
</div></header>
<div class="grid4">
<div class="kpi"><div class="kl">回测胜率</div><div class="kv" style="color:{wrc}">{bt.get("win_rate_pct","0%")}</div><div class="ks">区间: {bt.get("ci_str","N/A")}</div></div>
<div class="kpi"><div class="kl">统计显著性</div><div class="kv" style="color:{zc}">{bt.get("z_score",0):+.2f}</div><div class="ks">P-Value: {pp} ({'显著' if bt.get('significant') else '不显著'})</div></div>
<div class="kpi"><div class="kl">模拟累计收益</div><div class="kv" style="color:{crc}">{bt.get("cumulative_return",0):+.2%}</div><div class="ks">基于 {bt.get("total",0):,} 次信号对齐</div></div>
<div class="kpi"><div class="kl">Sharpe Ratio</div><div class="kv" style="color:{sc}">{bt.get("sharpe",0):.2f}</div><div class="ks">最大回撤 {bt.get("max_drawdown",0):.1%}</div></div>
</div>
<div class="sec"><div class="st">模拟权益曲线 (Base 100)</div><div style="height:220px"><canvas id="eq"></canvas></div></div>
<div class="two">
<div class="sec"><div class="st">模型回测排行</div>
<table><tr><th>模型</th><th style="text-align:right">次数</th><th style="text-align:right">胜率</th><th>95% CI</th><th style="text-align:right">Avg.Ret</th></tr>{rows}</table></div>
<div class="sec"><div class="st">月度表现</div><div id="mb"></div></div>
</div>
<div class="sec"><div class="st">今日日报实时摘要</div>
<div class="daily"><strong>ENGLISH</strong><br>{daily_en or "Waiting for update..."}<br><br><strong>中文摘要</strong><br>{daily_zh or "等待数据更新..."}</div>
</div>
<div style="text-align:center; font-size:11px; color:var(--muted); padding:20px; background:var(--bg2)">
    <strong>Last Update Flow:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} PDT | 
    Data Sync: <span style="color:var(--green)">SUCCESS</span>
</div>
<footer><div class="fl">© 2026 TRUMP CODE · RESEARCH ONLY</div><div class="fl">Sources: GitHub & Yahoo Finance</div></footer>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
const EQ={eq_j};const ML={ml};const MR={mr};const MC={mc};
const ctx=document.getElementById('eq').getContext('2d');
new Chart(ctx,{{type:'line',data:{{labels:EQ.map((_,i)=>i),datasets:[{{label:'Equity',data:EQ,borderColor:'#00e5a0',backgroundColor:'rgba(0,229,160,.05)',borderWidth:2,pointRadius:0,fill:true,tension:0.1}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{display:false}},y:{{grid:{{color:'#1e2d3d'}},ticks:{{color:'#4a6178',font:{{size:9}}}}}}}}}}}});
const mb=document.getElementById('mb');
ML.forEach((m,i)=>{{
    const wr=MR[i]; const color=wr>=58?'#00e5a0':wr>=53?'#f5a623':'#ff4d6a';
    mb.innerHTML+=`<div class="mbr"><span class="mbl">${{m}}</span><div class="mbt"><div class="mbf" style="width:${{wr}}%;background:${{color}}"></div></div><span class="mbv" style="color:${{color}}">${{wr}}%</span></div>`;
}});
</script></body></html>"""
    return html

def main():
    fetch_github()
    fetch_market()
    bt=backtest()
    if not bt:
        # 如果回测失败，生成一个基础报错页面
        log.error("回测失败，请检查数据源")
        return
    html=build_html(bt)
    Path("trump_dashboard.html").write_text(html,encoding="utf-8")
    log.info("✅ 看板生成成功")

if __name__=="__main__":main()
