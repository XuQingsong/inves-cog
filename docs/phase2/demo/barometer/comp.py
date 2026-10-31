"""综合指数：恐惧侧（压力）与贪婪侧（过热）各 0–100。
每个指标按事先写定的“平常值 → 极端值”线性映射到 0–100；方面 = 指标平均；综合 = 方面平均。
没有单项触发、没有升降档规则：读数随底层数据连续变化，数据回到平常，读数自然回落。"""
import pandas as pd, numpy as np
a=pd.read_csv('px.csv',index_col=0,parse_dates=True); b=pd.read_csv('px2.csv',index_col=0,parse_dates=True)
px=a.join(b[[c for c in b if c not in a]],how='left').sort_index()
idx=px['SPY'].dropna().index; px=px.reindex(idx).ffill(limit=3)
S,Q,V,V3,SMH=px['SPY'],px['QQQ'],px['^VIX'],px['^VIX3M'],px['SMH']
sect=['XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY']
AI=['NVDA','AMD','AVGO','MRVL','TSM','ASML','AMAT','LRCX','KLAC','MU','SNDK','WDC','DELL','SMCI','ANET','CIEN','COHR','VRT','GEV','CEG','INTC','ARM','QCOM']
ma=lambda p,n:p.rolling(n).mean()
def sc(x,lo,hi):  # 平常值 lo → 0，极端值 hi → 100
    return ((x-lo)/(hi-lo)*100).clip(0,100)
def rsi(p,n=14):
    d=p.diff(); return 100-100/(1+d.clip(lower=0).rolling(n).mean()/(-d.clip(upper=0)).rolling(n).mean())
M={}
for n,p in [('QQQ',Q),('SPY',S)]:
    r=p.pct_change(); M[n+'_1d']=r*100; M[n+'_sig']=r/r.rolling(60).std().shift(1)
    M[n+'_dd63']=(p/p.rolling(63).max()-1)*100; M[n+'_5d']=p.pct_change(5)*100; M[n+'_20d']=p.pct_change(20)*100
    for w in (20,50,100,200): M[f'{n}距{w}日线']=(p/ma(p,w)-1)*100
    M[n+'距半年低点']=(p/p.rolling(126).min()-1)*100; M[n+'_RSI']=rsi(p); M[n]=p
    M[n+'_dd250']=(p/p.rolling(250).max()-1)*100
M['VIX']=V; M['VIX_5d']=V.pct_change(5)*100; M['VIX/VIX3M']=V/V3
M['MOVE']=px['^MOVE']; M['10Y']=px['^TNX']; M['10Y_10dbp']=(px['^TNX']-px['^TNX'].shift(10))*100
M['HYG-IEF_10d']=(px['HYG'].pct_change(10)-px['IEF'].pct_change(10))*100
sp=px[sect]; nn=sp.notna().sum(axis=1)
M['行业破50日线']=(sp<ma(sp,50)).sum(axis=1)/nn*100
M['行业5日下跌占比']=((sp.pct_change()<0).sum(axis=1)/nn*100).rolling(5).mean()
na=px[AI].notna().sum(axis=1)
M['AI站上50日线']=(px[AI]>ma(px[AI],50)).sum(axis=1)/na*100
M['AI20日涨超25%占比']=(px[AI].pct_change(20)>0.25).sum(axis=1)/na*100
M['AI120日涨超50%占比']=(px[AI].pct_change(120)>0.5).sum(axis=1)/na*100
M['AI20日涨超25%']=(px[AI].pct_change(20)>0.25).sum(axis=1); M['AI家数']=na
M['MTUM/SPY5d']=(px['MTUM']/S).pct_change(5)*100
M['TQQQ5d']=px['TQQQ'].pct_change(5)*100; M['TQQQ60d']=px['TQQQ'].pct_change(60)*100; M['SOXL60d']=px['SOXL'].pct_change(60)*100; M['SOXL20d']=px['SOXL'].pct_change(20)*100
M['TLT10d']=px['TLT'].pct_change(10)*100; M['SPY10d']=S.pct_change(10)*100
M['日元5d']=-px['JPY=X'].pct_change(5)*100; M['黄金5d']=px['GLD'].pct_change(5)*100; M['比特币5d']=px['BTC-USD'].pct_change(5)*100
M['SMH20d']=SMH.pct_change(20)*100; M['SMH_RSI']=rsi(SMH)
for w in (20,50,200): M[f'SMH距{w}日线']=(SMH/ma(SMH,w)-1)*100
M['SMH相对QQQ20d']=M['SMH20d']-M['QQQ_20d']
up=(Q.pct_change()>0).astype(float); M['QQQ15日上涨天数']=up.rolling(15).sum()
M=pd.DataFrame(M)
worst=lambda a,b_:pd.concat([a,b_],axis=1).max(axis=1)
mean=lambda *xs:pd.concat(xs,axis=1).mean(axis=1)   # 缺数据的指标不计入
# ---------- 恐惧侧：五个方面 ----------
F={}
F['下跌冲击']=mean(worst(sc(-M.QQQ_sig,1,5),sc(-M.SPY_sig,1,5)),
                 worst(sc(-M.QQQ_5d,1,10),sc(-M.SPY_5d,1,8)),
                 worst(sc(-M.QQQ_dd63,3,20),sc(-M.SPY_dd63,3,15)))
F['恐慌情绪']=mean(sc(M.VIX,15,45),sc(M['VIX/VIX3M'],0.85,1.15),sc(M.VIX_5d,0,80))
F['债市信用']=mean(sc(M.MOVE,80,160),sc(M['10Y_10dbp'].abs(),10,60),sc(-M['HYG-IEF_10d'],0,6))
F['超卖扩散']=mean(sc(M['行业破50日线'],30,100),sc(M['行业5日下跌占比'],50,85),sc(50-M.QQQ_RSI,5,30))
sb=pd.concat([-M.SPY10d,-M.TLT10d],axis=1).min(axis=1)          # 股债同跌：取两者跌幅较小者
co=pd.concat([-M.SPY_5d/5,-M['黄金5d']/3,-M['比特币5d']/12],axis=1).min(axis=1)  # 股票、黄金、比特币同跌
F['去杠杆']=mean(sc(-M['MTUM/SPY5d'],0,6),sc(-M.TQQQ5d,0,30),sc(sb,0,5),sc(co,0,1.5),sc(M['日元5d'],0,6))
F=pd.DataFrame(F); FI=F.mean(axis=1)
# ---------- 贪婪侧：五个方面 ----------
G={}
G['超买']=mean(sc(M.QQQ_RSI,55,85),sc(M.SMH_RSI,55,88),sc(M['QQQ距20日线'],0,8),sc(M['SMH距20日线'],0,18))
G['连续上涨']=mean(sc(M.QQQ_20d,2,12),sc(M.SMH20d,5,35),sc(M['QQQ15日上涨天数'],8,13))
G['多头与杠杆']=mean(sc(M.TQQQ60d,10,90),sc(M.SOXL60d,20,250),sc(-M.VIX,-18,-11))
G['获利盘']=mean(sc(M['QQQ距200日线'],5,25),sc(M['SMH距200日线'],10,70),sc(M['AI120日涨超50%占比'],0,60))
G['情绪普涨']=mean(sc(M['AI站上50日线'],60,100),sc(M['AI20日涨超25%占比'],0,50),sc(M['SMH相对QQQ20d'],0,20))
G=pd.DataFrame(G); GI=G.mean(axis=1)
# 超卖反弹：此前 20 日内恐惧侧高、自低点快速反弹、长期趋势仍受损（获利盘少）
reb=mean(sc(FI.rolling(20).max(),20,60),sc(M['QQQ距半年低点'].where(M.QQQ_dd250<-8),3,15),100-G['获利盘'])
out=pd.concat([FI.rename('恐惧'),GI.rename('贪婪'),reb.rename('反弹特征'),F.add_prefix('F_'),G.add_prefix('G_')],axis=1).round(1)
out.to_pickle('comp.pkl'); M.to_pickle('M.pkl')
o=out.loc['2018':]
print(o[['恐惧','贪婪']].describe(percentiles=[.5,.75,.9,.95,.99]).round(1))
for a_,b_,l in [('2018-01-02','2018-01-26','2018-01融涨'),('2018-02-01','2018-02-15','2018-02'),('2018-10-01','2018-12-31','2018Q4'),('2020-02-20','2020-04-10','2020疫情'),('2020-07-01','2020-09-02','2020-08科技'),('2021-01-04','2021-12-31','2021'),('2022-01-01','2022-10-31','2022'),('2022-11-01','2022-12-31','2022末'),('2023-03-06','2023-03-24','2023-03'),('2023-05-15','2023-07-31','2023AI'),('2024-07-15','2024-08-15','2024-08'),('2025-03-25','2025-04-30','2025-04'),('2026-04-10','2026-06-30','2026-05半导体'),('2026-09-01','2026-09-30','2026-09'),('2026-10-01','2026-10-30','2026-10')]:
    s=o.loc[a_:b_]; print(f'{l:10s} 恐惧 均{s.恐惧.mean():5.1f} 最高{s.恐惧.max():5.1f} | 贪婪 均{s.贪婪.mean():5.1f} 最高{s.贪婪.max():5.1f} | 反弹最高{s.反弹特征.max():5.1f}')
# ---------- 输出给页面 ----------
import json
fl=np.interp(FI.fillna(0),[0,7,15,30,45,100],[0,1,2,3,4,5]); gl=np.interp(GI.fillna(0),[0,15,30,45,60,100],[0,1,2,3,4,5])
fl=pd.Series(fl,index=idx); gl=pd.Series(gl,index=idx)
SH=G[['超买','连续上涨','情绪普涨']].mean(axis=1); AC=G[['多头与杠杆','获利盘']].mean(axis=1)
def stage(f,g):
    fi,gi=min(int(f),4),min(int(g),4)
    if fi>=2 and fi>=gi: return -(fi-1)
    if gi>=2: return gi-1
    return 0
def nature(g,sh,ac):
    if ac>=45 and sh>=40: return '堆积型过热：超买叠加多头、杠杆与获利盘堆积，遇利空易集中兑现'
    if ac>=45: return '堆积未释放：短期已降温，但获利盘与杠杆仍在高位'
    if g>=25 and sh>=ac+25 and ac<25: return '超卖反弹型：短期急涨，但多头与获利盘并未堆积'
    return ''
cols=[c for c in M.columns]
rows=[]
for d in M.loc['2018-01-01':].index:
    m=M.loc[d]; f,g=fl[d],gl[d]
    rows.append({'d':d.strftime('%Y-%m-%d'),'F':round(float(FI[d]),1),'G':round(float(GI[d]),1),'fl':round(float(f),2),'gl':round(float(g),2),
      'st':stage(f,g),'pc':round(float(np.clip(max(g-1,0)-max(f-1,0),-3.4,3.4)),2),'sh':round(float(SH[d]),1),'ac':round(float(AC[d]),1),'nat':nature(GI[d],SH[d],AC[d]),
      'FD':{k:(None if pd.isna(F.loc[d,k]) else round(float(F.loc[d,k]))) for k in F},'GD':{k:(None if pd.isna(G.loc[d,k]) else round(float(G.loc[d,k]))) for k in G},
      'm':{k:(None if pd.isna(m[k]) else round(float(m[k]),2)) for k in cols}})
cape=pd.read_csv('shiller-pe.csv'); cape['Date']=pd.to_datetime(cape['Date']); cape=cape.set_index('Date')['Value'].astype(float).sort_index()
cape=cape.reindex(idx.union(cape.index)).ffill().reindex(idx)
fr=pd.read_csv('fred.csv',index_col=0,parse_dates=True)['DGS2']; fr=fr.reindex(idx.union(fr.index)).ffill().reindex(idx)
ai_ew=(1+px[AI].pct_change(fill_method=None).mean(axis=1)).cumprod(); aix=(ai_ew.pct_change(120)-S.pct_change(120))*100
for r in rows:
    d=pd.Timestamp(r['d']); r['m'].update({'席勒PE':None if pd.isna(cape[d]) else round(float(cape[d]),1),'2Y_126dbp':None if pd.isna(fr[d]-fr.shift(126)[d]) else round(float((fr[d]-fr.shift(126)[d])*100)),'AI超额120日':None if pd.isna(aix[d]) else round(float(aix[d]),1)})
json.dump(rows,open('baro.json','w'),ensure_ascii=False)
ST=['绝望','悲观','谨慎','理性','乐观','兴奋','狂热']
s=pd.Series([r['st'] for r in rows]).map(lambda k:ST[k+3]); print(s.value_counts(normalize=True).round(3).to_dict())
for r in rows:
    if r['d'] in ('2022-08-03','2025-04-09','2025-04-24','2026-06-02','2026-06-05','2026-06-26','2026-10-30'): print(r['d'],r['F'],r['G'],ST[r['st']+3],r['sh'],r['ac'],r['nat'])
