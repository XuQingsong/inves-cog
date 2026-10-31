import json
rows=json.load(open('baro.json'))
html=r'''<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>市场情绪钟摆 · 晴雨表 Demo</title>
<style>
:root{--bg:#0b0d10;--card:#12161b;--line:#262c33;--ink:#e9e4d8;--ink2:#9a9a92;--gold:#d6ad5f}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 50% -10%,#1d1a12 0%,var(--bg) 60%);color:var(--ink);font:14px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1240px;margin:0 auto;padding:22px}
.head{display:grid;grid-template-columns:1fr auto 1fr;align-items:end;gap:16px}
.title{text-align:center}.title h1{margin:0;font-size:34px;letter-spacing:6px;color:var(--gold);font-family:"Songti SC","STSong",serif}
.title .s{color:var(--ink2);font-size:13px;letter-spacing:2px}
.quote{font-size:12px;color:var(--ink2);font-style:italic}
.ctl{text-align:right;font-size:13px;color:var(--ink2)}
input[type=date]{background:#1a1f25;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:4px 6px;font:inherit;color-scheme:dark}
a{color:var(--gold);cursor:pointer;text-decoration:none}
.hero{display:grid;grid-template-columns:300px 1fr 300px;gap:16px;margin-top:14px;align-items:stretch}
.side{border:1px solid var(--line);border-radius:12px;padding:16px;background:linear-gradient(180deg,rgba(255,255,255,.02),rgba(255,255,255,0))}
.side h3{margin:0 0 2px;font-size:18px}.side .k{font-size:12px;color:var(--ink2)}
.side .lv{font-size:26px;font-weight:700;margin:8px 0 4px}
.side .why{font-size:13px;color:#cfcabd;line-height:1.75}
.fear{border-color:#1f5a3c;box-shadow:inset 0 0 40px rgba(47,191,113,.06)}.fear h3{color:#43d17f}
.greed{border-color:#6a2626;box-shadow:inset 0 0 40px rgba(226,58,58,.07)}.greed h3{color:#ef5a4a}
.stage{text-align:center;margin-top:-8px}.stage .n{font-size:30px;font-weight:700;letter-spacing:4px}.stage .d{color:var(--ink2);font-size:13px}
.stage .warn{display:inline-block;margin-top:6px;padding:2px 10px;border:1px solid #c98a1e;color:#e9b34a;border-radius:12px;font-size:12px}
.steps{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-top:16px;border:1px solid var(--line);border-radius:12px;padding:12px;background:var(--card)}
.step{border-radius:8px;padding:8px;border:1px solid var(--line);opacity:.55}.step.on{opacity:1;box-shadow:0 0 0 2px currentColor inset}
.step b{display:block;font-size:14px}.step span{font-size:12px;color:var(--ink2)}.step i{display:block;font-style:normal;font-size:11px;color:#8b877c;margin-top:4px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h4{margin:0 0 10px;font-size:15px;color:var(--gold);font-weight:600}.card h4 em{font-style:normal;display:inline-grid;place-items:center;width:20px;height:20px;border-radius:50%;border:1px solid var(--gold);font-size:12px;margin-right:6px}
.dim{display:grid;grid-template-columns:64px 1fr 34px;gap:8px;align-items:center;font-size:12px;margin:5px 0}
.bar{height:8px;background:#1f252c;border-radius:4px;overflow:hidden}.bar i{display:block;height:100%}
table{border-collapse:collapse;width:100%;font-size:12.5px}td,th{padding:5px 6px;border-bottom:1px solid var(--line);text-align:left}th{color:var(--ink2);font-weight:500}
td.n{text-align:right;font-variant-numeric:tabular-nums}.red{color:#ef5a4a}.grn{color:#43d17f}
.chips span{display:inline-block;padding:1px 8px;border-radius:10px;margin:3px 4px 0 0;font-size:11.5px;border:1px solid var(--line);color:var(--ink2)}.chips span.on{background:#8f2a24;border-color:#ef5a4a;color:#fff}
.liq{display:flex;justify-content:space-between;align-items:center;margin:6px 0 10px}.liq div{text-align:center;flex:1;font-size:12px;color:var(--ink2);padding:6px;border-radius:8px}.liq div.on{color:#fff;background:#2a2f36;box-shadow:0 0 0 1px var(--gold) inset}
#chart{height:430px}
.note{font-size:11.5px;color:var(--ink2);margin-top:8px;line-height:1.7}
.foot{text-align:center;color:var(--ink2);font-size:12px;margin:22px 0 6px;font-family:"Songti SC",serif;letter-spacing:1px}
details summary{cursor:pointer;color:var(--ink2)}
</style></head><body><div class="wrap">
<div class="head"><div class="quote">“投资不是预测未来，而是在赔率对自己最有利的时候下注。”<br>—— 霍华德·马克斯</div>
<div class="title"><h1>市场情绪钟摆</h1><div class="s">只量体温 · 不做预测 · 钟摆永远不会停</div></div>
<div class="ctl">日期 <input type="date" id="day"> <a id="latest">最新</a><br><span style="font-size:11px">Demo · 离线数据 Yahoo / FRED / multpl · 阈值未登记</span></div></div>
<div class="hero">
 <div class="side fear" id="fear"></div>
 <div><svg id="pend" viewBox="0 0 800 430" width="100%"></svg><div class="stage" id="stage"></div></div>
 <div class="side greed" id="greed"></div>
</div>
<div class="steps" id="steps"></div>
<div class="grid3">
 <div class="card"><h4><em>1</em>两侧读数分项</h4><div class="k" style="font-size:12px;color:#43d17f">恐惧侧 · 体温（压力）</div><div id="dT"></div><div class="k" style="font-size:12px;color:#ef5a4a;margin-top:10px">贪婪侧 · 过热度</div><div id="dH"></div></div>
 <div class="card"><h4><em>2</em>放大器：离被迫卖出多远</h4><div id="amp"></div><div style="margin-top:10px;font-size:12px;color:var(--ink2)">去杠杆迹象（两项以上，体温至少“紧张”）</div><div class="chips" id="fp"></div></div>
 <div class="card"><h4><em>3</em>流动性与估值（背景）</h4><div class="liq" id="liq"></div><div id="bg"></div></div>
</div>
<div class="card" style="margin-top:16px"><h4><em>4</em>钟摆轨迹 2018 至今 <span style="font-size:12px;color:var(--ink2);font-weight:400">上：QQQ（对数）；下：钟摆位置，绿色偏恐惧、红色偏贪婪。默认显示近 3 年，可拖动或缩放到 2018 年；点击任一天查看当天。</span></h4><div id="chart"></div></div>
<div class="card" style="margin-top:16px"><h4><em>5</em>历次行情对照</h4><table id="ep"><thead><tr><th>时段</th><th>行情</th><th>摆到最远</th><th>阶段分布（天）</th></tr></thead><tbody></tbody></table></div>
<div class="card" style="margin-top:16px"><details><summary>计算口径</summary><div class="note">
<b>恐惧侧（体温）</b>五个方面各 0–4：股价（QQQ/SPY 单日跌幅相当于近 60 日波动的倍数、距 63 日高点回撤、5 日跌幅）、恐慌（VIX、5 日涨幅、VIX/VIX3M 期限）、债市（MOVE、10 年美债 10 日变化、HYG 10 日跌幅）、扩散（行业 ETF 跌破 50/200 日线比例；指数没跌时最多偏紧张）、跨资产（日元急升、股债同跌、黄金比特币股票同跌）。<br>
<b>贪婪侧（过热度）</b>四个方面各 0–4：涨速（QQQ/SMH 20 日涨幅、距 50 日线的 5 年分位）、超买（RSI）、普涨追涨（AI 链站上 50 日线比例、20 日涨超 25% 比例）、杠杆追涨（SOXL/TQQQ 20 日涨幅分位）；狂热须普涨与杠杆同时到位。<br>
两侧各自取最高方面，只有一个方面高时降一档。升档立即。<b>出清确认</b>：广度推力日（9 个以上行业上涨且 SPY 涨 1.5%）、VIX 自 10 日峰值回落 25%、VIX 期限恢复正常、QQQ 自 10 日低点反弹 5% 且未再创新低，四项中满足两项即确认出清，当天直接降到“余震期”（最多偏紧张，VIX≥40 时最多紧张）；余震期内再出现新冲击（SPY 跌 3%、VIX 单日涨 20% 或 QQQ 创 10 日新低）立即回升。没有出清确认时每天最多降一档。回撤只在仍处 10 日低点 3% 以内时计满分，企稳后最多偏紧张。<b>钟摆位置</b> = 贪婪侧档位 − 恐惧侧档位（各自“正常”以下记 0），−3 到 +3 对应七个阶段。两侧同时发热时标“剧烈摆动”。<br>
七阶段名称与“马克斯原图做法”只作对照，系统不据此交易；交易仍按规则 A。</div></details></div>
<div class="foot">钟摆不会停，但你可以在它的节奏中，找到属于自己的机会。—— 霍华德·马克斯</div>
</div>
<script src="lightweight-charts.js"></script>
<script>
const R=__DATA__;const byD={};R.forEach((r,i)=>byD[r.d]=i);
const TN=['平静','正常波动','偏紧张','紧张','恐慌'],HN=['冷静','升温','偏热','过热','狂热'];
const ST=[['绝望','恐慌抛售，股价大幅下跌','重仓买入'],['悲观','对未来失去信心，继续下跌','开始布局'],['谨慎','担忧升温，市场开始承压','继续持有'],['理性','估值合理，市场趋于平衡','观察等待'],['乐观','上涨形成共识，开始加仓','降低仓位'],['兴奋','人人谈论牛市，风险偏好上升','卖出一部分'],['狂热','FOMO 情绪爆发，追涨泡沫','保持现金']];
const SC=['#2fbf71','#5ccf5a','#a6d84a','#e9c43b','#f29b38','#ef6a32','#e23a3a'];
const f=(v,d=1)=>v==null?'—':(+v).toFixed(d), s=(v,d=1)=>v==null?'—':(v>0?'+':'')+(+v).toFixed(d);
const pos=r=>Math.max(r.H-1,0)-Math.max(r.T-1,0);
function cont(r){const mD=Object.values(r.D).reduce((a,b)=>a+(b||0),0)/20,mH=Object.values(r.HD).reduce((a,b)=>a+(b||0),0)/16;return Math.max(-3.4,Math.min(3.4,pos(r)+0.45*(mH-mD)));}
function whyT(r){const m=r.m,D=r.D,p=[];
 p.push(`纳指 ${s(m.QQQ_1d)}%（平时 ${f(Math.abs(m.QQQ_sig))} 倍），距 63 日高点 ${s(m.QQQ_dd63)}%`);
 p.push(`VIX ${f(m.VIX)}${m['VIX/VIX3M']>1?'，期限倒挂':'，期限正常'}`);
 if(D['债市']>=2)p.push(`MOVE ${f(m.MOVE,0)}，10 年美债 10 日 ${s(m['10Y_10dbp'],0)} 基点`+(m['债市偏紧连续天']>60?`（已持续 ${m['债市偏紧连续天']} 天）`:''));
 if(D['扩散']>=2)p.push(`${f(m['行业破50日线'],0)}% 行业跌破 50 日线`);
 if(D['跨资产']>=2)p.push(`日元 5 日 ${s(m['日元5d'])}%，黄金 ${s(m['黄金5d'])}%，比特币 ${s(m['比特币5d'])}%`);
 if(r.FP.length)p.push('<b style="color:#ef5a4a">去杠杆迹象：'+r.FP.join('、')+'</b>');
 if(r.aft)p.push(`<b style="color:#e9c43b">余震期</b>：风险已出清（${r.CL.join('、')||'此前确认'}），当天原始读数 ${TN[r.Tr]}`);else if(r.T>r.Tr)p.push(`当天原始读数 ${TN[r.Tr]}，逐日回落中`);return p.join('；');}
function whyH(r){const m=r.m;return `SMH 20 日 ${s(m.SMH20d)}%，距 50 日线 ${s(m['SMH距50日线'])}%，RSI ${f(m.SMH_RSI,0)}；AI 链 ${f(m['AI站上50日线'],0)}% 站上 50 日线，${m['AI20日涨超25%']}/${m['AI家数']} 家 20 日涨超 25%；SOXL 20 日 ${s(m.SOXL20d,0)}%`+(r.H>r.Hr?`；当天原始读数 ${HN[r.Hr]}，降档待确认`:'');}
const tcol=['#6f8f80','#6f8f80','#a6d84a','#5ccf5a','#2fbf71'],hcol=['#8b877c','#8b877c','#f29b38','#ef6a32','#e23a3a'];
function dims(el,D,C){el.innerHTML=Object.entries(D).map(([k,v])=>`<div class="dim"><span>${k}</span><div class="bar"><i style="width:${(v||0)*25}%;background:${C}"></i></div><span style="color:var(--ink2)">${v==null?'缺':v}/4</span></div>`).join('');}
function drawPend(r){const P=[400,26],L=330,ang=x=>x/3*52*Math.PI/180,pt=(a,l=L)=>[P[0]+l*Math.sin(a),P[1]+l*Math.cos(a)];
 let g=`<defs><radialGradient id="bob" cx="35%" cy="30%"><stop offset="0" stop-color="#fff3c8"/><stop offset=".35" stop-color="#e3b75c"/><stop offset="1" stop-color="#6b4a14"/></radialGradient>
 <linearGradient id="arc" x1="0" x2="1"><stop offset="0" stop-color="#2fbf71"/><stop offset=".5" stop-color="#e9c43b"/><stop offset="1" stop-color="#e23a3a"/></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="6"/></filter></defs>`;
 const a0=pt(ang(-3.4)),a1=pt(ang(3.4));g+=`<path d="M${a0} A${L} ${L} 0 0 0 ${a1}" fill="none" stroke="url(#arc)" stroke-width="5" opacity=".9"/>`;
 const st=pos(r)+3;
 for(let i=0;i<7;i++){const [x,y]=pt(ang(i-3)),on=i===st;g+=`<circle cx="${x}" cy="${y}" r="${on?17:11}" fill="${SC[i]}" ${on?'stroke="#fff" stroke-width="2"':'opacity=".75"'}/>`;
  const [lx,ly]=pt(ang(i-3),L+(i===3?38:34));g+=`<text x="${lx}" y="${ly+4}" fill="${on?'#fff':SC[i]}" font-size="${on?16:13}" font-weight="${on?700:500}" text-anchor="middle">${ST[i][0]}</text>`;}
 g+=`<text x="120" y="400" fill="#43d17f" font-size="13">← 机会越来越大</text><text x="680" y="400" fill="#ef5a4a" font-size="13" text-anchor="end">风险越来越大 →</text>`;
 const a=ang(cont(r)),[bx,by]=pt(a,L-40);
 g+=`<rect x="${P[0]-46}" y="${P[1]-16}" width="92" height="8" rx="4" fill="#3a3326"/><line x1="${P[0]}" y1="${P[1]}" x2="${bx}" y2="${by}" stroke="#d6ad5f" stroke-width="4" stroke-linecap="round"/><circle cx="${P[0]}" cy="${P[1]}" r="8" fill="#d6ad5f" stroke="#6b4a14" stroke-width="2"/>`;
 g+=`<circle cx="${bx}" cy="${by}" r="48" fill="${SC[st]}" opacity=".4" filter="url(#glow)"/><circle cx="${bx}" cy="${by}" r="34" fill="url(#bob)"/>`;
 document.getElementById('pend').innerHTML=g;}
function show(d){let i=byD[d];if(i==null){const ks=Object.keys(byD).filter(k=>k<=d);i=byD[ks[ks.length-1]];}
 const r=R[i],m=r.m,st=pos(r)+3;document.getElementById('day').value=r.d;drawPend(r);
 const both=r.T>=3&&r.H>=2;
 document.getElementById('stage').innerHTML=`<div class="n" style="color:${SC[st]}">${ST[st][0]}</div><div class="d">${r.d} · ${ST[st][1]}</div>`+(both?`<div class="warn">两侧同时发热 · 剧烈摆动</div>`:'');
 const mT=Object.entries(r.D).sort((a,b)=>(b[1]||0)-(a[1]||0))[0][0],mH=Object.entries(r.HD).sort((a,b)=>(b[1]||0)-(a[1]||0))[0][0];
 document.getElementById('fear').innerHTML=`<h3>恐惧侧 · 体温</h3><div class="k">下跌、恐慌、债市、扩散、跨资产</div><div class="lv" style="color:${r.T>=2?tcol[r.T]:'#cfcabd'}">${TN[r.T]}${r.aft?'<span style="font-size:14px;font-weight:400"> · 余震期</span>':r.T>=2?'<span style="font-size:14px;font-weight:400"> · '+mT+'承压</span>':''}</div><div class="why">${whyT(r)}</div>`;
 document.getElementById('greed').innerHTML=`<h3>贪婪侧 · 过热度</h3><div class="k">涨速、超买、普涨追涨、杠杆追涨</div><div class="lv" style="color:${r.H>=2?hcol[r.H]:'#cfcabd'}">${HN[r.H]}${r.H>=2?'<span style="font-size:14px;font-weight:400"> · '+mH+'</span>':''}</div><div class="why">${whyH(r)}</div>`;
 document.getElementById('steps').innerHTML=ST.map((x,k)=>`<div class="step ${k===st?'on':''}" style="color:${SC[k]}"><b>${k+1} ${x[0]}</b><span>${x[1]}</span><i>马克斯原图做法：${x[2]}</i></div>`).join('');
 dims(document.getElementById('dT'),r.D,'#2fbf71');dims(document.getElementById('dH'),r.HD,'#ef5a4a');
 const row=n=>{const c=w=>{const v=m[`${n}距${w}日线`];return `<td class="n ${v<0?'red':''}">${s(v)}%</td>`};return `<tr><td>${n}</td>${c(50)}${c(100)}${c(200)}<td class="n">${s(m[n+'距半年低点'])}%</td></tr>`};
 document.getElementById('amp').innerHTML=`<table><tr><th></th><th>50 日</th><th>100 日</th><th>200 日</th><th>半年低点</th></tr>${row('QQQ')}${row('SPY')}</table><div class="note">红色为已跌破。趋势跟踪基金常参考 50/100/200 日线；跌破 200 日线和前低，倾向转为卖出，杠杆仓位可能被追加保证金。</div>`;
 document.getElementById('fp').innerHTML=['动量股踩踏','杠杆ETF重挫','VIX期限倒挂','股债同跌','全资产抛售','日元急升'].map(k=>`<span class="${r.FP.includes(k)?'on':''}">${k}</span>`).join('');
 const lq=m['2Y_126dbp'],ls=lq==null?1:lq>=50?0:lq<=-50?2:1;
 document.getElementById('liq').innerHTML=['收紧 · 加息预期','中性','宽松 · 降息预期'].map((x,k)=>`<div class="${k===ls?'on':''}">${x}</div>`).join('');
 document.getElementById('bg').innerHTML=`<table><tr><td>2 年美债半年变化</td><td class="n">${s(lq,0)} 基点</td></tr><tr><td>10 年美债 / MOVE</td><td class="n">${f(m['10Y'],2)}% / ${f(m.MOVE,0)}</td></tr><tr><td>席勒市盈率</td><td class="n">${f(m['席勒PE'])}（5 年 ${f(m['席勒PE分位'],0)} 分位）</td></tr><tr><td>AI 链相对大盘 120 日</td><td class="n">${s(m['AI超额120日'])}%</td></tr></table><div class="note">流动性和估值是慢变量，只说明“同样的冲击这次反应可能更大”，不决定钟摆位置。</div>`;}
const day=document.getElementById('day');day.min=R[0].d;day.max=R[R.length-1].d;day.onchange=()=>show(day.value);
document.getElementById('latest').onclick=()=>show(R[R.length-1].d);
const ch=LightweightCharts.createChart(document.getElementById('chart'),{layout:{background:{color:'transparent'},textColor:'#9a9a92',panes:{separatorColor:'#262c33'}},grid:{vertLines:{visible:false},horzLines:{color:'#1b2026'}},rightPriceScale:{borderVisible:false},timeScale:{borderVisible:false},localization:{locale:'zh-CN'}});
const q=ch.addSeries(LightweightCharts.LineSeries,{color:'#d6ad5f',lineWidth:1,priceLineVisible:false},0);q.priceScale().applyOptions({mode:1});
q.setData(R.filter(r=>r.m.QQQ!=null).map(r=>({time:r.d,value:r.m.QQQ})));
const b=ch.addSeries(LightweightCharts.BaselineSeries,{baseValue:{type:'price',price:0},topLineColor:'#e23a3a',topFillColor1:'rgba(226,58,58,.45)',topFillColor2:'rgba(226,58,58,.05)',bottomLineColor:'#2fbf71',bottomFillColor1:'rgba(47,191,113,.05)',bottomFillColor2:'rgba(47,191,113,.45)',lineWidth:1,priceLineVisible:false,lastValueVisible:false,priceFormat:{type:'custom',formatter:v=>{const k=Math.round(v)+3;return ST[k]?ST[k][0]:''}}},1);
b.setData(R.map(r=>({time:r.d,value:pos(r)})));
ch.timeScale().setVisibleRange({from:R[Math.max(0,R.length-756)].d,to:R[R.length-1].d});const ps=ch.panes();ps[0].setHeight(250);ps[1].setHeight(160);
ch.subscribeClick(p=>{if(p.time){const d=typeof p.time==='string'?p.time:`${p.time.year}-${String(p.time.month).padStart(2,'0')}-${String(p.time.day).padStart(2,'0')}`;show(d);scrollTo({top:0,behavior:'smooth'});}});
const EP=[['2018-01-02','2018-01-26','融涨（随后波动率暴跌）'],['2018-02-01','2018-02-15','波动率暴跌'],['2018-10-01','2018-12-31','加息 + 贸易战'],['2020-02-20','2020-04-10','疫情'],['2020-07-01','2020-09-02','科技股狂热'],['2022-01-01','2022-10-31','加息熊市'],['2023-03-06','2023-03-24','硅谷银行'],['2023-05-15','2023-07-31','AI 行情'],['2024-07-15','2024-08-15','日元套息平仓'],['2025-03-25','2025-04-30','关税冲击'],['2026-04-10','2026-06-04','半导体连续大涨'],['2026-09-01','2026-09-30','加息前后'],['2026-10-01','2026-10-30','债市危机 + 回调']];
document.querySelector('#ep tbody').innerHTML=EP.map(([a,b_,l])=>{const s_=R.filter(r=>r.d>=a&&r.d<=b_);const far=s_.reduce((x,r)=>Math.abs(pos(r))>Math.abs(pos(x))?r:x,s_[0]);const c={};s_.forEach(r=>{const k=pos(r)+3;c[k]=(c[k]||0)+1});
 return `<tr><td><a onclick="show('${far.d}');scrollTo({top:0,behavior:'smooth'})">${a} ~ ${b_}</a></td><td>${l}</td><td style="color:${SC[pos(far)+3]}">${ST[pos(far)+3][0]}（${far.d}）</td><td>${Object.keys(c).sort().map(k=>`<span style="color:${SC[k]}">${ST[k][0]} ${c[k]}</span>`).join('，')}</td></tr>`}).join('');
show(R[R.length-1].d);
</script></body></html>'''
open('index.html','w').write(html.replace('__DATA__',json.dumps(rows,ensure_ascii=False,separators=(',',':'))))
