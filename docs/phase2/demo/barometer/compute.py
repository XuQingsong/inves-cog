import pandas as pd, numpy as np
px=pd.read_csv('px.csv',index_col=0,parse_dates=True).sort_index()
fr=pd.read_csv('fred.csv',index_col=0,parse_dates=True).sort_index()
def mp(f):
    t=pd.read_csv(f); t['Date']=pd.to_datetime(t['Date']); t['Value']=t['Value'].astype(str).str.replace('†','').str.replace('%','').str.strip().astype(float)
    return t.set_index('Date')['Value'].sort_index()
cape,ey=mp('shiller-pe.csv'),mp('s-p-500-earnings-yield.csv')
idx=px['SPY'].dropna().index
A=lambda s: s.reindex(idx.union(s.index)).ffill().reindex(idx)
fr=fr.apply(A); cape,ey=A(cape),A(ey)
spy=px['SPY'].reindex(idx); vix=px['^VIX'].reindex(idx); v3=px['^VIX3M'].reindex(idx)
ai_t=['MSFT','GOOGL','AMZN','META','ORCL','CRWV','NVDA','AMD','AVGO','MRVL','TSM','ASML','AMAT','LRCX','KLAC','MU','SNDK','WDC','DELL','SMCI','ANET','CIEN','COHR','VRT','GEV','CEG','INTC','ARM','QCOM']
r=px.reindex(idx).pct_change(fill_method=None)
ai_ew=(1+r[ai_t].mean(axis=1,skipna=True)).cumprod()
sect=['XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY']
sp=px[sect].reindex(idx); ma=sp.rolling(200).mean(); above=(sp>ma).astype(float).where(ma.notna())
B1=above.sum(axis=1)/above.notna().sum(axis=1).replace(0,np.nan)
def corr60(w=60):
    out=pd.Series(np.nan,index=idx); R=r[ai_t]
    for i in range(w,len(idx),5):
        c=R.iloc[i-w:i].dropna(axis=1,thresh=int(w*.9)).corr().values; n=c.shape[0]
        out.iloc[i]=(c.sum()-n)/(n*(n-1)) if n>5 else np.nan
    return out.ffill()
ind={
 'S1 VIX(反向)':-vix,'S2 VIX3M/VIX':v3/vix,'S3 SPY 20日涨幅':spy.pct_change(20),
 'V1 席勒PE':cape,'V2 股债收益差(反向)':-(ey-fr['DGS10']),
 'P1 AI链超额120日':ai_ew.pct_change(120)-spy.pct_change(120),'P2 SPY/RSP 120日':(spy/px['RSP'].reindex(idx)).pct_change(120),'P3 SMH/SPY 120日':(px['SMH'].reindex(idx)/spy).pct_change(120),
 'B1 行业站上200日线比例':B1,'B2 SPY距200日线':spy/spy.rolling(200).mean()-1,'B3 距一年高点(反向)':spy/spy.rolling(252).max()-1,
}
grp={'情绪':['S1 VIX(反向)','S2 VIX3M/VIX','S3 SPY 20日涨幅'],'估值':['V1 席勒PE','V2 股债收益差(反向)'],'资金与仓位':['P1 AI链超额120日','P2 SPY/RSP 120日','P3 SMH/SPY 120日'],'市场行为':['B1 行业站上200日线比例','B2 SPY距200日线','B3 距一年高点(反向)']}
def pct(s,w=1260,m=504): return s.rolling(w,min_periods=m).apply(lambda a:(a[:-1]<a[-1]).mean()*100 if not np.isnan(a[-1]) else np.nan,raw=True)
P=pd.DataFrame({k:pct(v) for k,v in ind.items()})
band=lambda p: pd.cut(p,[-1,10,30,70,90,101],labels=[1,2,3,4,5]).astype(float)
Bd=P.apply(band)
G=pd.DataFrame({g:Bd[c].median(axis=1,skipna=True) for g,c in grp.items()})
G=G.apply(lambda s: np.where(s>3,np.floor(s),np.ceil(s))).where(G.notna())
up=(G>=4).sum(axis=1); upx=(G>=5).sum(axis=1); dn=(G<=2).sum(axis=1); dnx=(G<=1).sum(axis=1)
pend=pd.Series('理性',index=idx)
pend[up>=3]='偏乐观'; pend[(up>=3)&(upx>=2)]='狂热'; pend[dn>=3]='偏悲观'; pend[(dn>=3)&(dnx>=2)]='恐慌'
# fragility
corr=corr60(); Pc=pct(corr)
X={'拥挤':(P['P1 AI链超额120日']>=80)|(P['P2 SPY/RSP 120日']>=80)|(Pc>=80),
   '获利盘':(P['B2 SPY距200日线']>=80)&(pct(spy.pct_change(252))>=80),
   '信用':(pct(fr['NFCICREDIT'])>=80)|(pct((px['HYG']/px['IEF']).reindex(idx).pct_change(60))<=20),
   '流动性':(pct(fr['DGS2'].diff(126))>=80)|(pct(fr['NFCI'])>=80)}
X=pd.DataFrame(X); n=X.sum(axis=1)
frag=pd.Series('低',index=idx); frag[n==2]='中'; frag[n>=3]='高'; frag[(X['拥挤']&X['获利盘'])&(frag=='低')]='中'
shock=(spy.pct_change(5)<=-0.04)|(vix.pct_change(5)>=0.5)|(B1.diff(5)<=-5/11)
forced=(vix>=30)&(v3/vix<1)
greedy10=pend.isin(['偏乐观','狂热']).astype(int).rolling(10).max()==1
frag10=(frag=='高').astype(int).rolling(10).max()==1
concl=pd.Series('无需提示',index=idx)
concl[pend.isin(['偏乐观','狂热'])&(frag=='高')]='风险提示'
concl[greedy10&frag10&shock]='危险提示'
concl[pend.isin(['偏悲观','恐慌'])&forced]='机会提示'
out=pd.concat([G.add_prefix('组:'),pend.rename('钟摆'),X.add_prefix('紧:'),frag.rename('脆弱'),shock.rename('冲击'),forced.rename('被迫卖'),concl.rename('结论'),P.round(0)],axis=1)
out=out[out.index>='2018-01-01']; out.to_csv('readings.csv')
print(out['结论'].value_counts(normalize=True).round(3)); print(out['钟摆'].value_counts(normalize=True).round(3)); print(out['脆弱'].value_counts(normalize=True).round(3))
for a,b in [('2018-01-20','2018-02-12'),('2018-09-20','2018-12-31'),('2020-01-15','2020-04-15'),('2021-11-01','2021-12-31'),('2022-01-01','2022-10-31'),('2023-03-01','2023-03-31'),('2024-06-15','2024-08-15'),('2025-02-01','2025-04-30'),('2026-06-01','2026-10-30')]:
    s=out.loc[a:b]; print(a,b,'结论',s['结论'].value_counts().to_dict(),'钟摆',s['钟摆'].value_counts().to_dict(),'脆弱',s['脆弱'].value_counts().to_dict())
print(out.tail(8)[['组:情绪','组:估值','组:资金与仓位','组:市场行为','钟摆','紧:拥挤','紧:获利盘','紧:信用','紧:流动性','脆弱','冲击','结论']])
# Variant B: crowding+profit cushion alone qualifies as risk (draft §5 blind spot); danger = risk within 10d + shock
riskB=pend.isin(['偏乐观','狂热'])&((frag=='高')|(X['拥挤']&X['获利盘']))
cB=pd.Series('无需提示',index=idx); cB[riskB]='风险提示'
cB[(riskB.astype(int).rolling(10).max()==1)&shock]='危险提示'
cB[pend.isin(['偏悲观','恐慌'])&forced]='机会提示'
out['结论B']=cB; out=out[out.index>='2018-01-01']; out.to_csv('readings.csv')
print('B',out['结论B'].value_counts(normalize=True).round(3).to_dict())
for a,b in [('2018-01-02','2018-02-12'),('2018-09-20','2018-12-31'),('2020-01-02','2020-04-15'),('2021-11-01','2022-01-31'),('2022-02-01','2022-10-31'),('2023-03-01','2023-03-31'),('2024-06-15','2024-08-15'),('2025-01-15','2025-04-30'),('2026-06-01','2026-10-30'),('2017-01-01','2017-12-31'),('2019-01-01','2019-12-31')]:
    s=out.loc[a:b]; print(a,b,s['结论B'].value_counts().to_dict())
