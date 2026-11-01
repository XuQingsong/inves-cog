"""Barometer page: data + v2 visual (pendulum hero, energy arcs, tanks, ECG)."""

# ruff: noqa: E501 — the v2 template carries long JS lines verbatim
import json
from datetime import time as _time

STAGES = ["绝望", "悲观", "谨慎", "理性", "乐观", "兴奋", "狂热"]


def _row(d):
    """barometer_daily row → the prototype record shape."""
    stage = d.get("stage")
    st = STAGES.index(stage) - 3 if isinstance(stage, str) and stage in STAGES else 0
    dims = d.get("dims") or {}
    inp = d.get("inputs") or {}
    return {
        "d": str(d["date"]),
        "F": d["fear"],
        "G": d["greed"],
        "fl": d["fear_level"],
        "gl": d["greed_level"],
        "st": st,
        "pc": d["pendulum"],
        "sh": d["short_heat"],
        "ac": d["accumulation"],
        "nat": d.get("nature") or "",
        "FD": dims.get("fear") or {},
        "GD": dims.get("greed") or {},
        "m": inp,
        "asof": inp.get("_asof") or {},
        "missing": d.get("missing") or [],
    }


def history(connection):
    rows = connection.execute(
        "SELECT date, fear, greed, fear_level, greed_level, stage, pendulum, "
        "short_heat, accumulation, nature, dims, inputs, missing "
        "FROM flows.barometer_daily ORDER BY date"
    ).fetchall()
    return [_row(r) for r in rows]


def today_record(connection, clock):
    """Latest barometer_intraday during 09:30–16:45 ET; else latest daily row."""
    import pytz

    ny = pytz.timezone("America/New_York")
    now = clock.now_utc().astimezone(ny) if hasattr(clock, "now_utc") else None
    rows = []
    if now and _time(9, 30) <= now.time() <= _time(16, 45):
        rows = connection.execute(
            "SELECT ts AS date, asof, fear, greed, fear_level, greed_level, stage, "
            "pendulum, short_heat, accumulation, nature, dims, inputs, missing "
            "FROM flows.barometer_intraday ORDER BY ts DESC LIMIT 1"
        ).fetchall()
    label = "盘中·延时 15 分钟" if rows else None
    if not rows:
        rows = connection.execute(
            "SELECT date, asof, fear, greed, fear_level, greed_level, stage, "
            "pendulum, short_heat, accumulation, nature, dims, inputs, missing "
            "FROM flows.barometer_daily ORDER BY date DESC LIMIT 1"
        ).fetchall()
    if not rows:
        return None, None
    return _row(rows[0]), label


def _fmt(v, unit):
    if v is None:
        return "缺"
    if unit == "%":
        return f"{v:+.1f}%"
    return f"{v:.2f}"


def sentence(rec):
    """One-sentence conclusion — port of the prototype's sentence() logic."""
    m, fi, gi = rec["m"], min(int(rec["fl"] or 0), 4), min(int(rec["gl"] or 0), 4)
    side = "F" if fi >= 2 and fi >= gi else "G" if gi >= 2 else None
    if not side:
        return f"两侧读数都在正常范围：恐惧 {rec['F']:.0f}、贪婪 {rec['G']:.0f}。"
    dims = rec["FD"] if side == "F" else rec["GD"]
    phrases = {
        "下跌冲击": f"纳指 {_fmt(m.get('QQQ_1d'), '%')}（平时 {abs(m.get('QQQ_sig') or 0):.1f} 倍），距高点 {_fmt(m.get('QQQ_dd63'), '%')}",
        "恐慌情绪": f"VIX {m.get('VIX'):.1f}" + ("，期限倒挂" if (m.get("VIX/VIX3M") or 0) > 1 else ""),
        "债市信用": f"10 年美债 10 日 {_fmt(m.get('10Y_10dbp'), '%')} 基点，MOVE {(m.get('MOVE') or 0):.0f}",
        "超卖扩散": f"{(m.get('行业破50日线') or 0):.0f}% 行业跌破 50 日线",
        "去杠杆": f"动量股 5 日 {_fmt(m.get('MTUM/SPY5d'), '%')}，TQQQ {(m.get('TQQQ5d') or 0):.0f}%",
        "资金与杠杆": f"杠杆 ETF 收盘被迫{'卖出' if (m.get('杠杆ETF调仓亿') or 0) < 0 else '买入'} {abs(m.get('杠杆ETF调仓亿') or 0):.0f} 亿美元",
        "超买": f"半导体 RSI {(m.get('SMH_RSI') or 0):.0f}",
        "连续上涨": f"半导体 20 日 {_fmt(m.get('SMH20d'), '%')}",
        "多头与杠杆": f"融资余额同比 {_fmt(m.get('融资余额同比%'), '%')}，杠杆 ETF 20 日净申购 {_fmt(m.get('杠杆ETF净申购20日%'), '%')}",
        "获利盘": f"半导体距 200 日线 {_fmt(m.get('SMH距200日线'), '%')}",
        "情绪普涨": f"AI 链 {(m.get('AI站上50日线') or 0):.0f}% 站上 50 日线",
    }
    top = sorted(dims.items(), key=lambda kv: -(kv[1] or 0))[:2]
    parts = [phrases[k] for k, v in top if (v or 0) >= 20 and k in phrases]
    q = m.get("QQQ距200日线")
    if q is not None:
        if q < 0:
            parts.append(f"纳指已跌破 200 日线（{q:.1f}%）")
        elif q < 5:
            parts.append(f"纳指距 200 日线仅 {q:.1f}%")
    return "；".join(parts) + ("。" if parts else "")


def api_payload(connection, clock):
    rec, label = today_record(connection, clock)
    out = {"today": rec, "label": label, "history": history(connection)}
    if rec:
        out["sentence"] = sentence(rec)
    return out


def render_page(records, today=None, label=None):
    """Full HTML — v2 pendulum design with R[] injected."""
    data = json.dumps(records, ensure_ascii=False)
    tpl = _PAGE.replace("__R__", data)
    return tpl


_PAGE_HEAD = r"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>市场情绪钟摆 · 晴雨表</title>
<style>
:root{--bg:#07090c;--ink:#ece6d6;--ink2:#8f8a7e;--gold:#d9b265;--line:rgba(255,255,255,.07);--fear:47,191,113;--greed:232,72,58;--f:.1;--g:.1}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.serif{font-family:"Songti SC","STSong","Noto Serif SC",serif}.num{font-variant-numeric:tabular-nums;font-family:"SF Mono",ui-monospace,Menlo,monospace}
a{color:var(--gold);cursor:pointer;text-decoration:none}
header{max-width:1280px;margin:0 auto;padding:18px 28px 0;display:flex;align-items:center;justify-content:space-between}
.brand b{font-size:15px;letter-spacing:4px;color:var(--gold)}.brand span{color:var(--ink2);font-size:12px;margin-left:10px;letter-spacing:2px}
.ctl{font-size:12px;color:var(--ink2)}input[type=date]{background:#11151a;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:3px 6px;font:inherit;color-scheme:dark}
.hero{position:relative;max-width:1280px;margin:0 auto;height:760px;overflow:hidden}
.hero:before{content:"";position:absolute;inset:-10% -5%;background:
 radial-gradient(520px 420px at 14% 58%,rgba(var(--fear),var(--f)),transparent 70%),
 radial-gradient(520px 420px at 86% 58%,rgba(var(--greed),var(--g)),transparent 70%),
 radial-gradient(700px 380px at 50% 0%,rgba(217,178,101,.10),transparent 70%);transition:all 1.2s ease}
.side{position:absolute;top:34px;width:300px;z-index:2}.side.l{left:28px}.side.r{right:28px;text-align:right}
.side .t{font-size:12px;letter-spacing:3px;color:var(--ink2)}.side .v{font-size:84px;line-height:1;font-weight:200;margin:6px 0 2px}
.side .lv{font-size:20px;letter-spacing:4px}.side .bar{height:3px;background:rgba(255,255,255,.08);margin-top:12px;border-radius:2px;overflow:hidden}.side .bar i{display:block;height:100%}
.side .k{font-size:11.5px;color:var(--ink2);margin-top:8px}
svg#pend{position:absolute;left:0;top:0;width:100%;height:500px;z-index:1}
.seg{cursor:pointer;transition:opacity .4s}.seg:hover{opacity:1!important;filter:brightness(1.3)}
.tell{position:absolute;left:0;right:0;top:500px;text-align:center;z-index:2;padding:0 120px}
.tell .stage{font-size:64px;letter-spacing:18px;line-height:1.1;margin-left:18px}
.tell .sent{font-size:17px;color:#d8d1bf;margin-top:10px;line-height:1.8}
.tell .sent b{color:var(--ink);font-weight:600}
.chips{margin-top:10px}.chip{display:inline-block;padding:2px 12px;border-radius:14px;font-size:12px;margin:0 4px;border:1px solid}
.rail{display:flex;justify-content:center;gap:6px;margin-top:14px}.rail span{font-size:11px;padding:2px 10px;border-radius:10px;color:var(--ink2);border:1px solid var(--line)}
.rail span.on{color:#0b0d10;font-weight:700;border-color:transparent}
main{max-width:1280px;margin:0 auto;padding:0 28px 40px}
.sec{margin-top:34px}.sec h2{font-size:13px;letter-spacing:4px;color:var(--gold);font-weight:500;margin:0 0 14px;display:flex;align-items:baseline;gap:12px}
.sec h2 small{letter-spacing:0;color:var(--ink2);font-size:12px}
.drawer{border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:16px 0;display:grid;grid-template-columns:220px 1fr;gap:24px;min-height:120px}
.drawer .dn{font-size:28px}.drawer .ds{font-size:12px;color:var(--ink2)}
.ind{display:grid;grid-template-columns:repeat(3,1fr);gap:10px 28px}.ind div{display:flex;justify-content:space-between;border-bottom:1px dashed var(--line);padding:4px 0;font-size:13px}.ind div span{color:var(--ink2)}
.grid2{display:grid;grid-template-columns:1.35fr 1fr;gap:28px}
.tanks{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;align-items:end;height:260px;padding:10px 0 0}
.tank{display:flex;flex-direction:column;align-items:center;height:100%}
.tank .tube{position:relative;flex:1;width:58px;border:1px solid rgba(255,255,255,.12);border-radius:10px;overflow:hidden;background:linear-gradient(#0d1014,#0a0c0f)}
.tank .fill{position:absolute;left:0;right:0;bottom:0;transition:height 1s ease}
.tank .tick{position:absolute;left:0;right:0;border-top:1px dashed rgba(255,255,255,.18)}
.tank .pv{font-size:20px;margin-top:8px}.tank .pl{font-size:12px;color:var(--ink);text-align:center;margin-top:2px}.tank .pa{font-size:10.5px;color:var(--ink2);text-align:center}
.trig{border-left:1px solid var(--line);padding-left:24px}
.tr{display:grid;grid-template-columns:1fr 90px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line)}
.tr .n{font-size:13px}.tr .d{font-size:11.5px;color:var(--ink2)}.tr .x{text-align:right;font-size:17px}
.meter{position:relative;height:4px;background:rgba(255,255,255,.07);border-radius:2px;margin-top:6px}.meter i{position:absolute;top:-3px;width:2px;height:10px;background:#fff}.meter b{position:absolute;top:-3px;width:1px;height:10px;background:#ef5a4a}
canvas#ecg{width:100%;height:230px;display:block;cursor:ew-resize}
.eps{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.ep{border:1px solid var(--line);border-radius:10px;padding:10px 12px;cursor:pointer;transition:border-color .2s}.ep:hover{border-color:var(--gold)}
.ep b{font-size:13px;display:block}.ep span{font-size:11.5px;color:var(--ink2)}.ep .r{display:flex;justify-content:space-between;margin-top:6px;font-size:12px}
details{margin-top:28px;color:var(--ink2);font-size:12px}details summary{cursor:pointer}
.foot{text-align:center;color:var(--ink2);font-size:12px;margin-top:30px;letter-spacing:2px}
</style></head><body>
<header><div class="brand"><b class="serif">市场情绪钟摆</b><span>只量体温 · 不做预测</span></div>
<div class="ctl">日期 <input type="date" id="day"> <a id="latest">最新</a> · <a href="/">返回首页</a></div></header>
<section class="hero" id="hero">
 <div class="side l" id="sl"></div><div class="side r" id="sr"></div>
 <svg id="pend" viewBox="0 0 1280 500"></svg>
 <div class="tell"><div class="stage serif" id="stage"></div><div class="sent" id="sent"></div><div class="chips" id="chips"></div><div class="rail" id="rail"></div></div>
</section>
"""
_PAGE = (
    _PAGE_HEAD
    + r"""<div class="sec"><h2>为什么在这里 <small>点击钟摆下方的光弧切换方面</small></h2><div class="drawer" id="drawer"></div></div>
 <div class="sec grid2">
  <div><h2>杠杆压力仓 <small>各层杠杆处在自身历史的什么位置（0–100 分位）</small></h2><div class="tanks" id="tanks"></div></div>
  <div class="trig"><h2>离被迫卖出还有多远</h2><div id="trig"></div></div>
 </div>
 <div class="sec"><h2>心电图 2018 至今 <small>上：贪婪 · 下：恐惧 · 在图上拖动即回放</small></h2><canvas id="ecg"></canvas></div>
 <div class="sec"><h2>历次行情</h2><div class="eps" id="eps"></div></div>
 <details><summary>计算口径</summary><p>两侧各由多个方面组成，每个方面含 3–7 个指标；每个指标按事先写定的“平常值 → 极端值”折算 0–100，方面分取指标平均，综合读数取方面平均。没有单一指标能单独推高读数，也没有人为的升降档规则。周报、月报按公布日计入。详见《晴雨表需求 v1.0》。七阶段名称来自霍华德·马克斯，只作对照，系统不据此交易。</p></details>
 <div class="foot serif">钟摆不会停，但你可以在它的节奏中，找到属于自己的机会。—— 霍华德·马克斯</div>
</main>
<script>
const R=__R__;
const TN=['平静','正常波动','偏紧张','紧张','恐慌'],HN=['冷静','升温','偏热','过热','狂热'];
const ST=['绝望','悲观','谨慎','理性','乐观','兴奋','狂热'],SC=['#2fbf71','#5ccf5a','#a6d84a','#e9c43b','#f29b38','#ef6a32','#e23a3a'];
const f=(v,d=1)=>v==null?'—':(+v).toFixed(d), s=(v,d=1)=>v==null?'—':(v>0?'+':v<0?'−':'')+Math.abs(+v).toFixed(d);
const lvl=x=>Math.min(Math.floor(x),4);
const DIM={
 '下跌冲击':[['纳指当日','QQQ_1d','%'],['相当于平时','QQQ_sig','x'],['纳指 5 日','QQQ_5d','%'],['距 63 日高点','QQQ_dd63','%'],['标普当日','SPY_1d','%'],['标普 5 日','SPY_5d','%']],
 '恐慌情绪':[['VIX','VIX',''],['VIX/VIX3M','VIX/VIX3M','r'],['VIX 5 日','VIX_5d','%']],
 '债市信用':[['MOVE','MOVE',''],['10 年美债','10Y','y'],['10 日变化','10Y_10dbp','bp'],['高收益债相对国债 10 日','HYG-IEF_10d','%']],
 '超卖扩散':[['行业跌破 50 日线','行业破50日线','p'],['5 日行业下跌占比','行业5日下跌占比','p'],['纳指 RSI','QQQ_RSI','']],
 '去杠杆':[['动量股相对大盘 5 日','MTUM/SPY5d','%'],['TQQQ 5 日','TQQQ5d','%'],['标普 10 日','SPY10d','%'],['长债 10 日','TLT10d','%'],['黄金 5 日','黄金5d','%'],['比特币 5 日','比特币5d','%'],['日元 5 日','日元5d','%']],
 '资金与杠杆':[['杠杆 ETF 收盘调仓','杠杆ETF调仓亿','yi'],['SPDR 资金 5 日','SPDR资金5日%','%'],['杠杆基金净头寸','杠杆基金净头寸%','%'],['杠杆基金 4 周变化','杠杆基金4周变化','pp'],['回购−准备金利率','SOFR-IORB基点','bp'],['美元净流动性 4 周','净流动性4周%','%'],['个股看跌看涨','个股看跌看涨5日','r']],
 '超买':[['纳指 RSI','QQQ_RSI',''],['半导体 RSI','SMH_RSI',''],['纳指距 20 日线','QQQ距20日线','%'],['半导体距 20 日线','SMH距20日线','%']],
 '连续上涨':[['纳指 20 日','QQQ_20d','%'],['半导体 20 日','SMH20d','%'],['纳指 15 日上涨天数','QQQ15日上涨天数','d']],
 '多头与杠杆':[['TQQQ 60 日','TQQQ60d','%'],['SOXL 60 日','SOXL60d','%'],['VIX','VIX',''],['杠杆 ETF 20 日净申购','杠杆ETF净申购20日%','%'],['融资余额同比','融资余额同比%','%'],['资管期货净多分位','资管净多分位','']],
 '获利盘':[['纳指距 200 日线','QQQ距200日线','%'],['半导体距 200 日线','SMH距200日线','%'],['AI 链半年涨超 50%','AI120日涨超50%占比','p']],
 '情绪普涨':[['AI 链站上 50 日线','AI站上50日线','p'],['AI 链 20 日涨超 25%','AI20日涨超25%占比','p'],['半导体相对纳指 20 日','SMH相对QQQ20d','pp']]};
const FMT=(v,u)=>v==null?'缺':u==='%'?s(v)+'%':u==='x'?f(Math.abs(v))+' 倍':u==='r'?f(v,2):u==='y'?f(v,2)+'%':u==='bp'?s(v,0)+' 基点':u==='p'?f(v,0)+'%':u==='pp'?s(v)+' 个百分点':u==='yi'?(v<0?'卖出 ':'买入 ')+f(Math.abs(v),0)+' 亿':u==='d'?f(v,0)+' 天':f(v,1);
const PH={'下跌冲击':m=>`纳指 <b>${s(m.QQQ_1d)}%</b>（平时 ${f(Math.abs(m.QQQ_sig))} 倍），距高点 ${s(m.QQQ_dd63)}%`,'恐慌情绪':m=>`VIX <b>${f(m.VIX)}</b>${m['VIX/VIX3M']>1?'，期限倒挂':''}`,
 '债市信用':m=>`10 年美债 10 日 <b>${s(m['10Y_10dbp'],0)} 基点</b>，MOVE ${f(m.MOVE,0)}`,'超卖扩散':m=>`<b>${f(m['行业破50日线'],0)}%</b> 行业跌破 50 日线`,
 '去杠杆':m=>`动量股 5 日 <b>${s(m['MTUM/SPY5d'])}%</b>，TQQQ ${s(m.TQQQ5d,0)}%`,'资金与杠杆':m=>`杠杆 ETF 收盘被迫${m['杠杆ETF调仓亿']<0?'卖出':'买入'} <b>${f(Math.abs(m['杠杆ETF调仓亿']),0)} 亿美元</b>`,
 '超买':m=>`半导体 RSI <b>${f(m.SMH_RSI,0)}</b>`,'连续上涨':m=>`半导体 20 日 <b>${s(m.SMH20d)}%</b>`,'多头与杠杆':m=>`融资余额同比 <b>${s(m['融资余额同比%'])}%</b>，杠杆 ETF 20 日净申购 ${s(m['杠杆ETF净申购20日%'])}%`,
 '获利盘':m=>`半导体距 200 日线 <b>${s(m['SMH距200日线'],0)}%</b>`,'情绪普涨':m=>`AI 链 <b>${f(m['AI站上50日线'],0)}%</b> 站上 50 日线`};
let cur=R.length-1,selDim=null,curAng=0,anim=null;
// ---------- pendulum ----------
const P=[640,30],L=330,RING=[392,430],ANG=x=>x/3.4*52*Math.PI/180,pt=(a,l)=>[P[0]+l*Math.sin(a),P[1]+l*Math.cos(a)];
function sector(a0,a1,r0,r1){const [x0,y0]=pt(a0,r1),[x1,y1]=pt(a1,r1),[x2,y2]=pt(a1,r0),[x3,y3]=pt(a0,r0);const lg=Math.abs(a1-a0)>Math.PI?1:0;
 return `M${x0},${y0} A${r1},${r1} 0 ${lg} 0 ${x1},${y1} L${x2},${y2} A${r0},${r0} 0 ${lg} 1 ${x3},${y3}Z`;}
function drawStatic(){let g=`<defs><radialGradient id="bob" cx="35%" cy="30%"><stop offset="0" stop-color="#fff6d8"/><stop offset=".35" stop-color="#e2b457"/><stop offset="1" stop-color="#5e4011"/></radialGradient>
 <linearGradient id="arc" x1="0" x2="1"><stop offset="0" stop-color="#2fbf71"/><stop offset=".5" stop-color="#e9c43b"/><stop offset="1" stop-color="#e23a3a"/></linearGradient>
 <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter><filter id="soft"><feGaussianBlur stdDeviation="3"/></filter></defs>`;
 const a0=pt(ANG(-3.6),L),a1=pt(ANG(3.6),L);
 g+=`<path d="M${a0} A${L} ${L} 0 0 0 ${a1}" fill="none" stroke="url(#arc)" stroke-width="2" opacity=".55"/>`;
 for(let i=0;i<7;i++){const [x,y]=pt(ANG(i-3),L),[lx,ly]=pt(ANG(i-3),L-34);g+=`<circle id="tk${i}" cx="${x}" cy="${y}" r="5" fill="${SC[i]}"/><text id="tl${i}" x="${lx}" y="${ly+4}" fill="${SC[i]}" font-size="13" text-anchor="middle" opacity=".7">${ST[i]}</text>`;}
 g+=`<g id="segs"></g><g id="arm"></g>`;document.getElementById('pend').innerHTML=g;}
function drawSegs(r){const F=Object.entries(r.FD),G=Object.entries(r.GD);let g='';
 const span=(list,from,to,rgb,side)=>{const n=list.length,gap=0.012,w=(to-from)/n;list.forEach(([k,v],i)=>{const a0=from+i*w+gap,a1=from+(i+1)*w-gap,val=v||0,op=.10+.9*val/100;
  const d=sector(a0,a1,RING[0],RING[1]);const am=(a0+a1)/2,[tx,ty]=pt(am,RING[1]+26),[vx,vy]=pt(am,(RING[0]+RING[1])/2);
  g+=`${val>=35?`<path d="${d}" fill="rgb(${rgb})" opacity="${.5*val/100}" filter="url(#glow)"/>`:''}<path class="seg" data-k="${k}" d="${d}" fill="rgb(${rgb})" opacity="${op}" stroke="${selDim===k?'#fff':'none'}" stroke-width="1.5"/>
  <text x="${vx}" y="${vy+5}" fill="${val>=45?'#0b0d10':'#fff'}" font-size="14" font-weight="700" text-anchor="middle" pointer-events="none" class="num">${v==null?'缺':v}</text>
  <text x="${tx}" y="${ty+4}" fill="${val>=35?`rgb(${rgb})`:'#8f8a7e'}" font-size="12.5" text-anchor="middle" pointer-events="none">${k}</text>`;});};
 span(F.slice().reverse(),ANG(-3.6)*-1>0?-ANG(3.6):ANG(-3.6),-0.03,'47,191,113');
 span(G,0.03,ANG(3.6),'232,72,58');
 document.getElementById('segs').innerHTML=g;
 document.querySelectorAll('.seg').forEach(e=>e.onclick=()=>{selDim=e.dataset.k;drawSegs(R[cur]);drawer(R[cur]);});}
function drawArm(a,st){const [bx,by]=pt(a,L);const c=SC[st];
 document.getElementById('arm').innerHTML=`<line x1="${P[0]}" y1="${P[1]}" x2="${bx}" y2="${by}" stroke="#d9b265" stroke-width="2.5" opacity=".9"/>
 <rect x="${P[0]-40}" y="${P[1]-12}" width="80" height="6" rx="3" fill="#3b3426"/><circle cx="${P[0]}" cy="${P[1]}" r="6" fill="#d9b265"/>
 <circle cx="${bx}" cy="${by}" r="60" fill="${c}" opacity=".35" filter="url(#glow)"/><circle cx="${bx}" cy="${by}" r="34" fill="url(#bob)"/><circle cx="${bx-12}" cy="${by-14}" r="9" fill="#fff" opacity=".35" filter="url(#soft)"/>`;
 for(let i=0;i<7;i++){document.getElementById('tk'+i).setAttribute('r',i===st?9:5);document.getElementById('tl'+i).setAttribute('opacity',i===st?1:.45);document.getElementById('tl'+i).setAttribute('font-weight',i===st?700:400);}}
function swing(target,st,big){cancelAnimationFrame(anim);if(location.search.includes('static')){curAng=target;drawArm(target,st);return;}const t0=performance.now(),from=big?target+(target>0?-1:1)*ANG(3.4)*.9:curAng,dur=big?2600:900;
 const step=t=>{const k=Math.min(1,(t-t0)/dur);const e=big?Math.exp(-4*k)*Math.cos(k*Math.PI*3.2):1-Math.pow(1-k,3);
  curAng=big?target+(from-target)*e:from+(target-from)*e;drawArm(curAng,st);if(k<1)anim=requestAnimationFrame(step);else{curAng=target;drawArm(target,st);}};anim=requestAnimationFrame(step);}
// ---------- text ----------
function sentence(r){const m=r.m,fi=lvl(r.fl),gi=lvl(r.gl);const side=(fi>=2&&fi>=gi)?'F':gi>=2?'G':null;
 if(!side)return `两侧读数都在正常范围：恐惧 ${f(r.F,0)}、贪婪 ${f(r.G,0)}。`;
 const D=side==='F'?r.FD:r.GD;const top=Object.entries(D).filter(([k,v])=>v>=20).sort((a,b)=>b[1]-a[1]).slice(0,2).map(([k])=>PH[k](m));
 let amp='';const q=m['QQQ距200日线'];if(q!=null){amp=q<0?`纳指<b>已跌破 200 日线</b>（${s(q)}%）`:q<5?`纳指距 200 日线<b>仅 ${f(q)}%</b>`:'';}
 return top.join('；')+(amp?'；'+amp:'')+'。';}
function side(el,lab,v,lv,N,rgb,asR){const p=Math.min(100,v);el.innerHTML=`<div class="t">${lab}</div><div class="v num" style="color:${lv>=2?`rgb(${rgb})`:'#ece6d6'}">${f(v,0)}</div><div class="lv serif" style="color:${lv>=2?`rgb(${rgb})`:'#8f8a7e'}">${N[lv]}</div><div class="bar"><i style="width:${p}%;background:rgb(${rgb});${asR?'margin-left:auto':''}"></i></div>`;}
function drawer(r){const D={...r.FD,...r.GD};if(!selDim||!(selDim in D)){const all=Object.entries(D).sort((a,b)=>(b[1]||0)-(a[1]||0));selDim=all[0][0];}
 const isF=selDim in r.FD,rgb=isF?'47,191,113':'232,72,58';
 document.getElementById('drawer').innerHTML=`<div><div class="ds">${isF?'恐惧侧':'贪婪侧'}</div><div class="dn serif" style="color:rgb(${rgb})">${selDim}</div><div class="num" style="font-size:40px;font-weight:200">${D[selDim]==null?'缺':D[selDim]}<span style="font-size:14px;color:#8f8a7e"> /100</span></div></div>
 <div class="ind">${DIM[selDim].map(([l,k,u])=>`<div><span>${l}</span><b class="num">${FMT(r.m[k],u)}</b></div>`).join('')}</div>`;}
function pctl(key,i,win=1260){const v=R[i].m[key];if(v==null)return null;let n=0,c=0;for(let j=Math.max(0,i-win);j<=i;j++){const x=R[j].m[key];if(x!=null){n++;if(x<=v)c++;}}return n>60?100*c/n:null;}
function tanks(i){const r=R[i],m=r.m,a=r.asof||{};const T=[
 ['融资余额','融资余额同比%',`同比 ${s(m['融资余额同比%'])}% · 截至 ${(a.margin||'').slice(0,7)}`],
 ['杠杆 ETF','杠杆ETF净申购20日%',`20 日净申购 ${s(m['杠杆ETF净申购20日%'])}%`],
 ['资管期货多头','资管净多%',`净多 ${f(m['资管净多%'])}% · 截至 ${a.cftc||'—'}`],
 ['杠杆基金空头','杠杆基金净头寸%',`净头寸 ${s(m['杠杆基金净头寸%'])}%（越低越空）`,true],
 ['期权投机',null,'期权链从生产采集起积累']];
 document.getElementById('tanks').innerHTML=T.map(([n,k,d,inv])=>{let p=k?pctl(k,i):null;if(p!=null&&inv)p=100-p;const c=p==null?'#2a2d31':p>=85?'#e8483a':p>=65?'#f29b38':'#d9b265';
  return `<div class="tank"><div class="tube"><div class="tick" style="bottom:85%"></div><div class="tick" style="bottom:50%"></div><div class="fill" style="height:${p??0}%;background:linear-gradient(to top,${c}33,${c})"></div></div><div class="pv num" style="color:${c}">${p==null?'缺':f(p,0)}</div><div class="pl">${n}</div><div class="pa">${d}</div></div>`}).join('');}
function trig(r){const m=r.m;const rows=[];
 const lineRow=(n,v,sub)=>{const x=Math.max(-10,Math.min(10,v??0));rows.push(`<div class="tr"><div><div class="n">${n}</div><div class="d">${sub}</div><div class="meter"><b style="left:50%"></b><i style="left:${50+x*5}%"></i></div></div><div class="x num" style="color:${v<0?'#ef5a4a':v<3?'#f29b38':'#ece6d6'}">${s(v)}%</div></div>`);};
 lineRow('纳指 · 200 日线',m['QQQ距200日线'],'趋势基金的主要分水岭');lineRow('纳指 · 50 日线',m['QQQ距50日线'],'短期趋势');lineRow('纳指 · 半年低点',m['QQQ距半年低点'],'跌破前低易触发追加保证金');lineRow('标普 · 200 日线',m['SPY距200日线'],'');
 const rb=m['杠杆ETF调仓亿'];rows.push(`<div class="tr"><div><div class="n">今日杠杆 ETF 收盘调仓</div><div class="d">下跌日被迫卖出、上涨日被迫买入</div></div><div class="x num" style="color:${rb<-30?'#ef5a4a':'#ece6d6'}">${rb==null?'缺':(rb<0?'−':'+')+f(Math.abs(rb),0)+'亿'}</div></div>`);
 const vr=m['VIX/VIX3M'];rows.push(`<div class="tr"><div><div class="n">VIX 期限结构</div><div class="d">大于 1 为倒挂：短期恐慌高于长期</div></div><div class="x num" style="color:${vr>1?'#ef5a4a':'#ece6d6'}">${f(vr,2)}</div></div>`);
 document.getElementById('trig').innerHTML=rows.join('');}
// ---------- ECG ----------
const cv=document.getElementById('ecg'),cx=cv.getContext('2d');let W,H;
const EP=[['2018-02-01','2018-02-15','波动率暴跌'],['2018-10-01','2018-12-31','加息+贸易战'],['2020-02-20','2020-04-10','疫情'],['2020-07-01','2020-09-02','科技股狂热'],['2022-01-01','2022-10-31','加息熊市'],['2022-07-15','2022-08-19','熊市反弹'],['2023-03-06','2023-03-24','硅谷银行'],['2023-05-15','2023-07-31','AI 行情'],['2024-07-15','2024-08-15','日元套息平仓'],['2025-03-25','2025-04-30','关税冲击'],['2026-04-10','2026-06-04','半导体大涨'],['2026-10-01','2026-10-30','债市危机+回调']];
function ecg(){const dpr=devicePixelRatio||1;W=cv.clientWidth;H=cv.clientHeight;cv.width=W*dpr;cv.height=H*dpr;cx.setTransform(dpr,0,0,dpr,0,0);cx.clearRect(0,0,W,H);
 const mid=H/2,X=i=>i/(R.length-1)*W,Y=v=>v/100*(mid-14);
 cx.strokeStyle='rgba(255,255,255,.06)';cx.beginPath();cx.moveTo(0,mid);cx.lineTo(W,mid);cx.stroke();
 const band=(key,sign,rgb)=>{cx.beginPath();cx.moveTo(0,mid);R.forEach((r,i)=>cx.lineTo(X(i),mid-sign*Y(r[key])));cx.lineTo(W,mid);cx.closePath();const gr=cx.createLinearGradient(0,mid,0,mid-sign*(mid));gr.addColorStop(0,`rgba(${rgb},.05)`);gr.addColorStop(1,`rgba(${rgb},.75)`);cx.fillStyle=gr;cx.fill();
  cx.beginPath();R.forEach((r,i)=>i?cx.lineTo(X(i),mid-sign*Y(r[key])):cx.moveTo(X(i),mid-sign*Y(r[key])));cx.strokeStyle=`rgba(${rgb},.9)`;cx.lineWidth=1;cx.stroke();};
 band('G',1,'232,72,58');band('F',-1,'47,191,113');
 cx.font='11px -apple-system,PingFang SC';cx.textAlign='center';
 let lastX=-99;EP.forEach(([a,b,l])=>{const i=R.findIndex(r=>r.d>=a);if(i<0)return;const x=X(i);if(x-lastX<70)return;lastX=x;cx.fillStyle='rgba(236,230,214,.55)';cx.fillText(l,x,12);cx.fillStyle='rgba(255,255,255,.15)';cx.fillRect(x,16,1,H-32);});
 let yr='';R.forEach((r,i)=>{const y=r.d.slice(0,4);if(y!==yr){yr=y;cx.fillStyle='rgba(143,138,126,.8)';cx.fillText(y,X(i)+14,H-2);}});
 const x=X(cur);cx.fillStyle='#d9b265';cx.fillRect(x-.5,0,1.5,H);cx.beginPath();cx.arc(x,mid-Y(R[cur].G),3.5,0,7);cx.arc(x,mid+Y(R[cur].F),3.5,0,7);cx.fill();}
let drag=false;const pick=e=>{const b=cv.getBoundingClientRect();const i=Math.round((e.clientX-b.left)/b.width*(R.length-1));show(Math.max(0,Math.min(R.length-1,i)),false);};
cv.onmousedown=e=>{drag=true;pick(e)};window.onmouseup=()=>drag=false;cv.onmousemove=e=>{if(drag)pick(e)};
// ---------- episodes ----------
document.getElementById('eps').innerHTML=EP.map(([a,b,l])=>{const s_=R.filter(r=>r.d>=a&&r.d<=b);if(!s_.length)return'';const mf=s_.reduce((x,r)=>r.F>x.F?r:x),mg=s_.reduce((x,r)=>r.G>x.G?r:x);const far=mf.F>=mg.G?mf:mg;
 return `<div class="ep" data-d="${far.d}"><b>${l}</b><span>${a} ~ ${b}</span><div class="r"><span style="color:#2fbf71">恐惧 ${f(mf.F,0)}</span><span style="color:#e8483a">贪婪 ${f(mg.G,0)}</span><span style="color:${SC[far.st+3]}">${ST[far.st+3]}</span></div></div>`}).join('');
document.querySelectorAll('.ep').forEach(e=>e.onclick=()=>{show(byD[e.dataset.d],true);scrollTo({top:0,behavior:'smooth'});});
// ---------- show ----------
function show(i,big){cur=i;const r=R[i],fi=lvl(r.fl),gi=lvl(r.gl),st=r.st+3;document.getElementById('day').value=r.d;
 const hero=document.getElementById('hero');hero.style.setProperty('--f',(.04+.5*r.F/100).toFixed(3));hero.style.setProperty('--g',(.04+.5*r.G/100).toFixed(3));
 side(document.getElementById('sl'),'恐惧 · 压力',r.F,fi,TN,'47,191,113');side(document.getElementById('sr'),'贪婪 · 过热',r.G,gi,HN,'232,72,58',true);
 document.getElementById('stage').innerHTML=ST[st];document.getElementById('stage').style.color=SC[st];
 document.getElementById('sent').innerHTML=`<span style="color:#8f8a7e">${r.d}</span> · `+sentence(r);
 const ch=[];if(r.nat)ch.push(`<span class="chip" style="color:#e9b34a;border-color:#6b5420">${r.nat.split('：')[0]}</span>`);if(fi>=2&&gi>=2)ch.push(`<span class="chip" style="color:#ef6a32;border-color:#6a2c1c">两侧同时发热 · 剧烈摆动</span>`);
 document.getElementById('chips').innerHTML=ch.join('');
 document.getElementById('rail').innerHTML=ST.map((x,k)=>`<span class="${k===st?'on':''}" style="${k===st?`background:${SC[k]}`:''}">${x}</span>`).join('');
 drawSegs(r);swing(ANG(r.pc),st,big);drawer(r);tanks(i);trig(r);ecg();}
drawStatic();const day=document.getElementById('day');day.min=R[0].d;day.max=R[R.length-1].d;
day.onchange=()=>{const k=Object.keys(byD).filter(x=>x<=day.value);show(byD[k[k.length-1]],true);};
document.getElementById('latest').onclick=()=>show(R.length-1,true);
addEventListener('resize',ecg);show(R.length-1,true);
</script></body></html>"""
)
