"""市场晴雨表 Demo：体温（压力）+ 过热度。离线数据：Yahoo / FRED / multpl。"""
import json, pandas as pd, numpy as np
a=pd.read_csv('px.csv',index_col=0,parse_dates=True); b=pd.read_csv('px2.csv',index_col=0,parse_dates=True)
px=a.join(b[[c for c in b if c not in a]],how='left').sort_index()
idx=px['SPY'].dropna().index; px=px.reindex(idx).ffill(limit=3)
S,Q,V,V3,SMH=px['SPY'],px['QQQ'],px['^VIX'],px['^VIX3M'],px['SMH']
sect=['XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY']
AI=['NVDA','AMD','AVGO','MRVL','TSM','ASML','AMAT','LRCX','KLAC','MU','SNDK','WDC','DELL','SMCI','ANET','CIEN','COHR','VRT','GEV','CEG','INTC','ARM','QCOM']
lv=lambda x,c: sum((x>=k) for k in c).astype(float).where(x.notna())
pct=lambda s:s.rolling(1260,min_periods=504).apply(lambda x:(x[:-1]<x[-1]).mean()*100 if not np.isnan(x[-1]) else np.nan,raw=True)
ma=lambda p,n:p.rolling(n).mean()
def rsi(p):
    d=p.diff(); return 100-100/(1+d.clip(lower=0).rolling(14).mean()/(-d.clip(upper=0)).rolling(14).mean())
M={}  # raw metrics for explanation
for n,p in [('QQQ',Q),('SPY',S)]:
    r=p.pct_change(); M[n+'_1d']=r*100; M[n+'_sig']=(r/r.rolling(60).std().shift(1)); M[n+'_dd63']=(p/p.rolling(63).max()-1)*100; M[n+'_5d']=p.pct_change(5)*100
def price(n):
    p=Q if n=='QQQ' else S
    near_low=(p/p.rolling(10).min()-1)<=0.03          # 仍在 10 日低点 3% 以内 = 还在承压
    dd=lv(-M[n+'_dd63'],[3,6,10,15]); dd=dd.where(near_low,dd.clip(upper=2))   # 已企稳：回撤再深最多偏紧张
    return pd.concat([lv(-M[n+'_sig'],[1.5,2.5,4,6]),dd,lv(-M[n+'_5d'],[2.5,4,7,10])],axis=1).max(axis=1)
D={}
D['股价']=pd.concat([price('QQQ'),price('SPY')],axis=1).max(axis=1)
M['VIX']=V; M['VIX_5d']=V.pct_change(5)*100; M['VIX/VIX3M']=V/V3
D['恐慌']=pd.concat([lv(V,[15,20,25,35]),lv(M['VIX_5d'],[15,30,60,100]).clip(upper=3),lv(M['VIX/VIX3M'],[0.92,0.98,1.0,1.15])],axis=1).max(axis=1)
M['MOVE']=px['^MOVE']; M['10Y']=px['^TNX']; M['10Y_10dbp']=(px['^TNX']-px['^TNX'].shift(10))*100; M['HYG_10d']=px['HYG'].pct_change(10)*100
D['债市']=pd.concat([lv(M['MOVE'],[90,110,130,160]),lv(M['10Y_10dbp'].abs(),[20,30,50,80]).clip(upper=3),lv(-M['HYG_10d'],[1.5,3,6,10])],axis=1).max(axis=1)
sp=px[sect]; nn=sp.notna().sum(axis=1)
M['行业破50日线']=(sp<ma(sp,50)).sum(axis=1)/nn*100; M['行业破200日线']=(sp<ma(sp,200)).sum(axis=1)/nn*100
down=(sp.pct_change()<0).sum(axis=1)/nn
mass=((down>=10/11)&(S.pct_change()<=-0.015)).astype(float)*3
dif=pd.concat([lv(M['行业破50日线']/100,[0.4,0.6,0.8,2]),lv(M['行业破200日线']/100,[0.5,0.65,0.8,0.9]),mass],axis=1).max(axis=1)
D['扩散']=dif.where(~((dif>=3)&(D['股价']<2)),2)   # 修正2：无股价确认时扩散最多偏紧张
M['日元5d']=-px['JPY=X'].pct_change(5)*100; M['黄金5d']=px['GLD'].pct_change(5)*100; M['比特币5d']=px['BTC-USD'].pct_change(5)*100; M['TLT10d']=px['TLT'].pct_change(10)*100
liq=((M['黄金5d']<=-2)&(M['比特币5d']<=-8)&(M['SPY_5d']<=-3)).astype(float)*3
sb=((S.pct_change(10)<=-0.03)&(M['TLT10d']<=-3)).astype(float)*2
D['跨资产']=pd.concat([lv(M['日元5d'],[1.5,3,5,7]),liq,sb],axis=1).max(axis=1)
D=pd.DataFrame(D)
M['MTUM/SPY5d']=(px['MTUM']/S).pct_change(5)*100; M['TQQQ5d']=px['TQQQ'].pct_change(5)*100
FP=pd.DataFrame({'动量股踩踏':M['MTUM/SPY5d']<=-3,'杠杆ETF重挫':M['TQQQ5d']<=-15,'VIX期限倒挂':M['VIX/VIX3M']>1.0,'股债同跌':sb>0,'全资产抛售':liq>0,'日元急升':M['日元5d']>=3})
def agg(Dm):
    s=np.sort(Dm.fillna(0).values,axis=1); top,sec=s[:,-1],s[:,-2]
    return pd.Series(np.where(sec>=top-1,top,top-1),index=Dm.index)
def settle(raw,clear):  # 升档立即；有“出清确认”时直接降到原始读数；否则每天最多降一档
    vals=raw.fillna(0).values; cl=clear.reindex(raw.index).fillna(False).values; out=[]
    for i,v in enumerate(vals):
        if not out or v>=out[-1] or cl[i]: out.append(v)
        else: out.append(max(v,out[-1]-1))
    return pd.Series(out,index=raw.index)
rawT=agg(D); rawT=rawT.where(FP.sum(axis=1)<2,np.maximum(rawT,3))
up=(sp.pct_change()>0).sum(axis=1)/nn
CL=pd.DataFrame({'广度推力日':(up>=9/11)&(S.pct_change()>=0.015),'VIX自峰值回落25%':V<=V.rolling(10).max()*0.75,'VIX期限恢复正常':M['VIX/VIX3M']<0.97,'自低点反弹5%未再创新低':(Q/Q.rolling(10).min()-1>=0.05)&(Q.rolling(3).min()>Q.rolling(10).min().shift(3))})
clearT=CL.sum(axis=1)>=2
shockT=(S.pct_change()<=-0.03)|(V.pct_change()>=0.20)|(Q<=Q.rolling(10).min().shift(1))   # 新冲击：大跌、VIX 急升或创 10 日新低
def settle_t(raw):
    vals=raw.fillna(0).values; cl=clearT.reindex(raw.index).fillna(False).values; sh=shockT.reindex(raw.index).fillna(False).values
    out=[]; aft=[]; cleared=False; vix=V.reindex(raw.index).values
    for i,v in enumerate(vals):
        if sh[i]: cleared=False
        if cl[i] and not sh[i]: cleared=True
        if cleared: d_=min(v,3 if vix[i]>=40 else 2)   # 出清后：余震期最多偏紧张（VIX≥40 时最多紧张）
        elif not out or v>=out[-1]: d_=v
        else: d_=max(v,out[-1]-1)
        if cleared and v<2 : cleared=False           # 原始读数已回到正常，余震结束
        out.append(d_); aft.append(cleared and d_>=2)
    return pd.Series(out,index=raw.index), pd.Series(aft,index=raw.index)
T,AFT=settle_t(rawT)
# heat
M['QQQ20d']=Q.pct_change(20)*100; M['SMH20d']=SMH.pct_change(20)*100; M['SMH距50日线']=(SMH/ma(SMH,50)-1)*100; M['QQQ距50日线']=(Q/ma(Q,50)-1)*100
M['SMH_RSI']=rsi(SMH); M['QQQ_RSI']=rsi(Q)
na=px[AI].notna().sum(axis=1); M['AI站上50日线']=(px[AI]>ma(px[AI],50)).sum(axis=1)/na*100; M['AI20日涨超25%']=(px[AI].pct_change(20)>0.25).sum(axis=1); M['AI家数']=na
M['SOXL20d']=px['SOXL'].pct_change(20)*100
H={}
H['涨速']=pd.concat([lv(pct(M['QQQ20d']),[80,90,97,99.5]),lv(pct(M['SMH20d']),[80,90,97,99.5]),lv(pct(M['QQQ距50日线']),[80,90,97,99.5]),lv(pct(M['SMH距50日线']),[80,90,97,99.5])],axis=1).max(axis=1)
H['超买']=pd.concat([lv(M['QQQ_RSI'],[70,75,80,88]),lv(M['SMH_RSI'],[70,75,80,88])],axis=1).max(axis=1)
H['普涨追涨']=pd.concat([lv(M['AI站上50日线']/100,[0.75,0.9,0.95,2]),lv(M['AI20日涨超25%']/na,[0.1,0.2,0.35,0.5])],axis=1).max(axis=1)
H['杠杆追涨']=pd.concat([lv(pct(M['SOXL20d']),[80,90,97,99.5]),lv(pct(px['TQQQ'].pct_change(20)),[80,90,97,99.5])],axis=1).max(axis=1)
H=pd.DataFrame(H); rawH=agg(H)
rawH=rawH.where(~((rawH>=4)&~((H['普涨追涨']>=3)&(H['杠杆追涨']>=3))),3)  # 修正3：狂热须普涨+杠杆同时到位
clearH=(M['SMH20d']<=0)|(M['AI站上50日线']<=50)
Hh=settle(rawH,clearH)
# amplifier & background
for n,p in [('QQQ',Q),('SPY',S)]:
    for w in (50,100,200): M[f'{n}距{w}日线']=(p/ma(p,w)-1)*100
    M[n+'距半年低点']=(p/p.rolling(126).min()-1)*100; M[n+'半年低点']=p.rolling(126).min(); M[n]=p
cape=pd.read_csv('shiller-pe.csv'); cape['Date']=pd.to_datetime(cape['Date']); cape=cape.set_index('Date')['Value'].astype(float).sort_index()
cape=cape.reindex(idx.union(cape.index)).ffill().reindex(idx); M['席勒PE']=cape; M['席勒PE分位']=pct(cape)
ai_ew=(1+px[AI].pct_change(fill_method=None).mean(axis=1)).cumprod(); M['AI超额120日']=(ai_ew.pct_change(120)-S.pct_change(120))*100; M['AI超额分位']=pct(M['AI超额120日'])
fr=pd.read_csv('fred.csv',index_col=0,parse_dates=True)['DGS2']; fr=fr.reindex(idx.union(fr.index)).ffill().reindex(idx)
M['2Y']=fr; M['2Y_126dbp']=(fr-fr.shift(126))*100
# hold-streak for bond (2023 note)
bond_hi=(D['债市']>=2).astype(int); M['债市偏紧连续天']=bond_hi.groupby((bond_hi!=bond_hi.shift()).cumsum()).cumsum()*bond_hi
M=pd.DataFrame(M)
start='2018-01-01'
sel=lambda x:x.loc[start:]
rows=[]
for d in sel(M).index:
    m=M.loc[d]
    mD=np.nanmean([D.loc[d,k] for k in D]); mH=np.nanmean([H.loc[d,k] for k in H]); pc=float(np.clip(Hh[d]-T[d]+0.5*(mH/4-mD/4),-4,4))
    rows.append({'d':d.strftime('%Y-%m-%d'),'p':round(pc,2),'T':int(T[d]),'Tr':int(rawT[d]),'H':int(Hh[d]),'Hr':int(rawH[d]),
      'D':{k:(None if pd.isna(D.loc[d,k]) else int(D.loc[d,k])) for k in D},'HD':{k:(None if pd.isna(H.loc[d,k]) else int(H.loc[d,k])) for k in H},
      'FP':[k for k in FP if bool(FP.loc[d,k])],'CL':[k for k in CL if bool(CL.loc[d,k])],'aft':bool(AFT[d]),'m':{k:(None if pd.isna(v) else round(float(v),2)) for k,v in m.items()}})
json.dump(rows,open('baro.json','w'),ensure_ascii=False)
o=pd.DataFrame({'T':sel(T),'H':sel(Hh)}); nm=['平静','正常波动','偏紧张','紧张','恐慌']; hm=['冷静','升温','偏热','过热','狂热']
print('体温',o['T'].map(lambda x:nm[int(x)]).value_counts(normalize=True).round(3).to_dict())
print('过热',o['H'].map(lambda x:hm[int(x)]).value_counts(normalize=True).round(3).to_dict())
r=sel(rawT); print('单日紧张跳变（原始）',int(((r>=3)&(r.shift(1)<3)&(r.shift(-1)<3)).sum()))
for a_,b_,l in [('2018-01-02','2018-01-26','2018-01融涨'),('2018-02-01','2018-02-15','2018-02'),('2018-10-01','2018-12-31','2018Q4'),('2020-02-20','2020-04-10','2020疫情'),('2020-07-01','2020-09-02','2020-08科技'),('2022-01-01','2022-10-31','2022'),('2023-03-06','2023-03-24','2023-03'),('2023-05-15','2023-07-31','2023AI'),('2024-07-15','2024-08-15','2024-08'),('2025-03-25','2025-04-30','2025-04'),('2026-04-10','2026-06-04','2026-05半导体'),('2026-09-01','2026-09-30','2026-09'),('2026-10-01','2026-10-30','2026-10')]:
    s=o.loc[a_:b_]; print(f'{l:10s} 体温',s['T'].map(lambda x:nm[int(x)]).value_counts().to_dict(),'| 过热',s['H'].map(lambda x:hm[int(x)]).value_counts().to_dict())
print(o.tail(3))
