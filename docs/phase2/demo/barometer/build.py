import json
rows=json.load(open('baro.json'))
html=r'''<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>市场晴雨表 Demo</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--ink:#1d2321;--ink2:#56605c;--line:#e3e6e4;--bg:#f6f7f5;--card:#fff}
*{box-sizing:border-box}body{margin:0;font:14px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--bg)}
.wrap{max-width:1180px;margin:0 auto;padding:20px}
h1{font-size:20px;margin:0}.sub{color:var(--ink2);font-size:12px}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-top:14px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.gauge{border-radius:10px;padding:16px;color:#fff}
.gauge .lab{font-size:12px;opacity:.85}.gauge .lv{font-size:30px;font-weight:700;margin:2px 0 6px}
.gauge .why{font-size:13px;line-height:1.7}
.dims{display:grid;gap:6px;margin-top:10px}
.dim{display:grid;grid-template-columns:72px 1fr 54px;align-items:center;gap:8px;font-size:13px}
.bar{height:10px;background:#eef0ee;border-radius:5px;overflow:hidden}.bar i{display:block;height:100%}
.chips span{display:inline-block;padding:2px 8px;border-radius:10px;margin:2px 4px 2px 0;font-size:12px;border:1px solid var(--line);color:var(--ink2)}
.chips span.on{background:#a8322d;color:#fff;border-color:#a8322d}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}
th{color:var(--ink2);font-weight:500}td.n{text-align:right;font-variant-numeric:tabular-nums}
a{color:#1f5f8b;cursor:pointer;text-decoration:none}
.legend span{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 10px;vertical-align:middle}
#chart{height:520px}
.note{font-size:12px;color:var(--ink2);margin-top:8px}
input[type=date]{font:inherit;padding:4px 6px;border:1px solid var(--line);border-radius:6px}
details summary{cursor:pointer;color:var(--ink2)}
</style></head><body><div class="wrap">
<div class="top"><div><h1>市场晴雨表 <span class="sub">Demo · 只量体温，不做预测</span></h1>
<div class="sub">体温量“压力”（下跌、恐慌、债市、扩散、跨资产）；过热度量“狂热”（涨速、超买、普涨追涨、杠杆追涨）。离线数据：Yahoo、FRED、multpl，阈值为初始值、未登记。</div></div>
<div>日期 <input type="date" id="day"> <a id="latest">最新</a></div></div>
<div class="two">
 <div class="gauge" id="gT"></div>
 <div class="gauge" id="gH"></div>
</div>
<div class="two">
 <div class="card" style="margin-top:14px"><b>体温五个方面</b><div class="dims" id="dT"></div></div>
 <div class="card" style="margin-top:14px"><b>过热度四个方面</b><div class="dims" id="dH"></div></div>
</div>
<div class="two">
 <div class="card"><b>放大器：离被迫卖出还有多远</b><div id="amp"></div>
  <div style="margin-top:8px"><b style="font-size:13px">去杠杆迹象</b> <span class="sub">两项以上同时出现，体温至少“紧张”</span><div class="chips" id="fp"></div></div></div>
 <div class="card"><b>背景（慢变量，不参与读数）</b><div id="bg"></div></div>
</div>
<div class="card"><div class="top"><b>2018 年至今</b><span class="legend sub">体温<span style="background:#cfd8d3"></span>平静<span style="background:#9fb8ad"></span>正常<span style="background:#e0a33a"></span>偏紧张<span style="background:#d9622b"></span>紧张<span style="background:#a8322d"></span>恐慌 · 过热度<span style="background:#cfd8d3"></span>冷静<span style="background:#b7c6e6"></span>升温<span style="background:#7f9fd8"></span>偏热<span style="background:#5b4fc4"></span>过热<span style="background:#8e2fa8"></span>狂热</span></div>
<div class="sub">上：QQQ（对数）；中：体温；下：过热度。点击图上任意一天查看当天读数。</div><div id="chart"></div></div>
<div class="card"><b>历次事件对照</b><table id="ep"><thead><tr><th>时段</th><th>事件</th><th>体温最高</th><th>体温分布（天）</th><th>过热度分布（天）</th></tr></thead><tbody></tbody></table></div>
<div class="card"><details><summary>计算口径</summary><div class="note" style="line-height:1.9">
<b>体温</b>：五个方面各 0–4 分。股价：QQQ/SPY 单日跌幅是近 60 日波动的几倍（1.5/2.5/4/6）、距 63 日高点回撤（3/6/10/15%）、5 日跌幅（2.5/4/7/10%）。恐慌：VIX（15/20/25/35）、VIX 5 日涨幅、VIX/VIX3M（0.92/0.98/1.0/1.15，>1 为期限倒挂）。债市：MOVE（90/110/130/160）、10 年美债 10 日变化（20/30/50/80 基点）、HYG 10 日跌幅。扩散：行业 ETF 跌破 50/200 日线比例、10 个以上行业同日下跌且 SPY 跌 1.5%；指数没跌时扩散最多“偏紧张”。跨资产：日元 5 日升值、股债同跌、黄金比特币股票同跌。<br>
合成：取最高方面；只有它一个方面高、其余都低两档以上时降一档；去杠杆迹象两项以上至少“紧张”。升档立即，降档需连续 3 天低于当前档。<br>
<b>过热度</b>：涨速（QQQ/SMH 20 日涨幅、距 50 日线，在过去 5 年的分位 80/90/97/99.5）、超买（RSI 70/75/80/88）、普涨追涨（AI 链站上 50 日线比例、20 日涨超 25% 的比例）、杠杆追涨（SOXL/TQQQ 20 日涨幅分位）。合成同上；“狂热”须普涨追涨与杠杆追涨同时到位。</div></details></div>
</div>
<script src="lightweight-charts.js"></script>
<script>
const R=__DATA__;const byD={};R.forEach((r,i)=>byD[r.d]=i);
const TN=['平静','正常波动','偏紧张','紧张','恐慌'],HN=['冷静','升温','偏热','过热','狂热'];
const TC=['#7d8f86','#6f9384','#c98a1e','#cf5a24','#a8322d'],HC=['#7d8f86','#7c8fbf','#5f7fcf','#5b4fc4','#8e2fa8'];
const TCL=['#cfd8d3','#9fb8ad','#e0a33a','#d9622b','#a8322d'],HCL=['#cfd8d3','#b7c6e6','#7f9fd8','#5b4fc4','#8e2fa8'];
const f=(v,d=1)=>v==null?'—':(+v).toFixed(d), s=(v,d=1)=>v==null?'—':(v>0?'+':'')+(+v).toFixed(d);
function whyT(r){const m=r.m,D=r.D,p=[];
 if(D['股价']>=1)p.push(`纳指 ${s(m.QQQ_1d)}%（平时 ${f(Math.abs(m.QQQ_sig))} 倍），距 63 日高点 ${s(m.QQQ_dd63)}%，5 日 ${s(m.QQQ_5d)}%`);
 if(D['恐慌']>=1)p.push(`VIX ${f(m.VIX)}（5 日 ${s(m.VIX_5d,0)}%）${m['VIX/VIX3M']>1?'，期限倒挂':''}`);
 if(D['债市']>=2)p.push(`MOVE ${f(m.MOVE,0)}，10 年美债 10 日 ${s(m['10Y_10dbp'],0)} 基点（${f(m['10Y'],2)}%）`+(m['债市偏紧连续天']>60?`，债市偏紧已持续 ${m['债市偏紧连续天']} 个交易日`:''));
 if(D['扩散']>=2)p.push(`${f(m['行业破50日线'],0)}% 行业跌破 50 日线`);
 if(D['跨资产']>=2)p.push(`日元 5 日 ${s(m['日元5d'])}%，黄金 ${s(m['黄金5d'])}%，比特币 ${s(m['比特币5d'])}%`);
 if(r.FP.length)p.push('去杠杆迹象：'+r.FP.join('、'));
 if(r.T>r.Tr)p.push(`（当天原始读数 ${TN[r.Tr]}，降档需连续 3 天确认）`);
 return p.join('；')||'各方面都平稳';}
function whyH(r){const m=r.m,p=[];
 p.push(`SMH 20 日 ${s(m.SMH20d)}%，距 50 日线 ${s(m['SMH距50日线'])}%，RSI ${f(m.SMH_RSI,0)}`);
 p.push(`AI 链 ${f(m['AI站上50日线'],0)}% 站上 50 日线，${m['AI20日涨超25%']}/${m['AI家数']} 家 20 日涨超 25%`);
 p.push(`SOXL 20 日 ${s(m.SOXL20d,0)}%`);return p.join('；');}
function dims(el,D,C){el.innerHTML=Object.entries(D).map(([k,v])=>`<div class="dim"><span>${k}</span><div class="bar"><i style="width:${(v||0)*25}%;background:${C[v||0]}"></i></div><span class="sub">${v==null?'缺':v+' / 4'}</span></div>`).join('');}
function show(d){let i=byD[d];if(i==null){const ks=Object.keys(byD).filter(k=>k<=d);i=byD[ks[ks.length-1]];}
 const r=R[i],m=r.m;document.getElementById('day').value=r.d;
 const main=Object.entries(r.D).sort((a,b)=>(b[1]||0)-(a[1]||0))[0][0];
 document.getElementById('gT').style.background=TC[r.T];
 document.getElementById('gT').innerHTML=`<div class="lab">体温 · ${r.d}</div><div class="lv">${TN[r.T]}${r.T>=2?' · '+main+'承压':''}</div><div class="why">${whyT(r)}</div>`;
 const mainH=Object.entries(r.HD).sort((a,b)=>(b[1]||0)-(a[1]||0))[0][0];
 document.getElementById('gH').style.background=HC[r.H];
 document.getElementById('gH').innerHTML=`<div class="lab">过热度 · ${r.d}</div><div class="lv">${HN[r.H]}${r.H>=2?' · '+mainH:''}</div><div class="why">${whyH(r)}</div>`;
 dims(document.getElementById('dT'),r.D,TC);dims(document.getElementById('dH'),r.HD,HC);
 const row=(n)=>{const c=(w)=>{const v=m[`${n}距${w}日线`];return `<td class="n" style="color:${v<0?'#a8322d':'inherit'}">${s(v)}%${v<0?' 已跌破':''}</td>`};
   return `<tr><td>${n} ${f(m[n],2)}</td>${c(50)}${c(100)}${c(200)}<td class="n">${f(m[n+'半年低点'],2)}（${s(m[n+'距半年低点'])}%）</td></tr>`};
 document.getElementById('amp').innerHTML=`<table><tr><th></th><th>距 50 日线</th><th>距 100 日线</th><th>距 200 日线</th><th>半年低点</th></tr>${row('QQQ')}${row('SPY')}</table><div class="note">趋势跟踪基金（CTA）通常参考 50/100/200 日线；跌破 200 日线和前低，倾向于转为卖出，杠杆仓位可能被追加保证金。</div>`;
 document.getElementById('fp').innerHTML=['动量股踩踏','杠杆ETF重挫','VIX期限倒挂','股债同跌','全资产抛售','日元急升'].map(k=>`<span class="${r.FP.includes(k)?'on':''}">${k}</span>`).join('');
 document.getElementById('bg').innerHTML=`<table><tr><td>席勒市盈率</td><td class="n">${f(m['席勒PE'])}</td><td class="sub">过去 5 年 ${f(m['席勒PE分位'],0)} 分位</td></tr><tr><td>AI 链相对大盘（120 日）</td><td class="n">${s(m['AI超额120日'])}%</td><td class="sub">${f(m['AI超额分位'],0)} 分位</td></tr><tr><td>10 年美债</td><td class="n">${f(m['10Y'],2)}%</td><td class="sub">MOVE ${f(m.MOVE,0)}</td></tr></table><div class="note">估值高、资金拥挤只说明“同样的冲击这次反应可能更大”，不决定体温。</div>`;
}
const day=document.getElementById('day');day.min=R[0].d;day.max=R[R.length-1].d;day.onchange=()=>show(day.value);
document.getElementById('latest').onclick=()=>show(R[R.length-1].d);
const ch=LightweightCharts.createChart(document.getElementById('chart'),{layout:{background:{color:'#fff'},textColor:'#56605c',panes:{separatorColor:'#e3e6e4'}},grid:{vertLines:{visible:false},horzLines:{color:'#f0f2f0'}},rightPriceScale:{borderVisible:false},timeScale:{borderVisible:false},localization:{locale:'zh-CN'}});
const q=ch.addSeries(LightweightCharts.LineSeries,{color:'#1d2321',lineWidth:1,priceLineVisible:false,lastValueVisible:true},0);
q.priceScale().applyOptions({mode:1});q.setData(R.filter(r=>r.m.QQQ!=null).map(r=>({time:r.d,value:r.m.QQQ})));
const t=ch.addSeries(LightweightCharts.HistogramSeries,{priceLineVisible:false,lastValueVisible:false,priceFormat:{type:'custom',formatter:v=>TN[Math.round(v)]||''}},1);
t.setData(R.map(r=>({time:r.d,value:r.T+0.2,color:TCL[r.T]})));
const h=ch.addSeries(LightweightCharts.HistogramSeries,{priceLineVisible:false,lastValueVisible:false,priceFormat:{type:'custom',formatter:v=>HN[Math.round(v)]||''}},2);
h.setData(R.map(r=>({time:r.d,value:r.H+0.2,color:HCL[r.H]})));
ch.timeScale().fitContent();const ps=ch.panes();ps[0].setHeight(260);ps[1].setHeight(120);ps[2].setHeight(120);
ch.subscribeClick(p=>{if(p.time){const d=typeof p.time==='string'?p.time:`${p.time.year}-${String(p.time.month).padStart(2,'0')}-${String(p.time.day).padStart(2,'0')}`;show(d);window.scrollTo({top:0,behavior:'smooth'});}});
const EP=[['2018-01-02','2018-01-26','融涨（随后波动率暴跌）'],['2018-02-01','2018-02-15','波动率暴跌'],['2018-10-01','2018-12-31','加息+贸易战'],['2020-02-20','2020-04-10','疫情'],['2020-07-01','2020-09-02','科技股狂热'],['2022-01-01','2022-10-31','加息熊市'],['2023-03-06','2023-03-24','硅谷银行'],['2023-05-15','2023-07-31','AI 行情'],['2024-07-15','2024-08-15','日元套息平仓'],['2025-03-25','2025-04-30','关税冲击'],['2026-04-10','2026-06-04','半导体连续大涨'],['2026-09-01','2026-09-30','加息前后'],['2026-10-01','2026-10-30','债市危机+回调']];
const cnt=(a,N)=>{const c={};a.forEach(v=>c[N[v]]=(c[N[v]]||0)+1);return N.filter(n=>c[n]).map(n=>`${n} ${c[n]}`).join('，')};
document.querySelector('#ep tbody').innerHTML=EP.map(([a,b,l])=>{const s_=R.filter(r=>r.d>=a&&r.d<=b);const mx=s_.reduce((x,r)=>r.T>x.T?r:x,s_[0]);
 return `<tr><td><a onclick="show('${mx.d}');scrollTo({top:0,behavior:'smooth'})">${a} ~ ${b}</a></td><td>${l}</td><td>${TN[mx.T]}（${mx.d}）</td><td>${cnt(s_.map(r=>r.T),TN)}</td><td>${cnt(s_.map(r=>r.H),HN)}</td></tr>`}).join('');
show(R[R.length-1].d);
</script></body></html>'''
open('index.html','w').write(html.replace('__DATA__',json.dumps(rows,ensure_ascii=False,separators=(',',':'))))
print(len(rows))
