import pandas as pd, numpy as np
a=pd.read_csv('px.csv',index_col=0,parse_dates=True); b=pd.read_csv('px2.csv',index_col=0,parse_dates=True)
px=a.join(b[[c for c in b if c not in a]]).dropna(subset=['SPY']); idx=px.index
pct=lambda s:s.rolling(1260,min_periods=504).apply(lambda x:(x[:-1]<x[-1]).mean()*100 if not np.isnan(x[-1]) else np.nan,raw=True)
lv=lambda x,c: sum((x>=k) for k in c).astype(float).where(x.notna())
def rsi(p):
    d=p.diff(); return 100-100/(1+d.clip(lower=0).rolling(14).mean()/(-d.clip(upper=0)).rolling(14).mean())
H={}
H['涨速']=pd.concat([lv(pct(px[t].pct_change(20)),[80,90,97,99.5]) for t in ['QQQ','SMH']]+[lv(pct(px[t]/px[t].rolling(50).mean()),[80,90,97,99.5]) for t in ['QQQ','SMH']],axis=1).max(axis=1)
H['超买']=pd.concat([lv(rsi(px[t]),[70,75,80,88]) for t in ['QQQ','SMH']],axis=1).max(axis=1)
ai=['NVDA','AMD','AVGO','MRVL','TSM','ASML','AMAT','LRCX','KLAC','MU','SNDK','WDC','DELL','SMCI','ANET','CIEN','COHR','VRT','GEV','CEG','INTC','ARM','QCOM']
n=px[ai].notna().sum(axis=1); br=(px[ai]>px[ai].rolling(50).mean()).sum(axis=1)/n; big=(px[ai].pct_change(20)>0.25).sum(axis=1)/n
H['普涨追涨']=pd.concat([lv(br,[0.75,0.9,0.95,2]),lv(big,[0.1,0.2,0.35,0.5])],axis=1).max(axis=1)
H['杠杆追涨']=pd.concat([lv(pct(px[t].pct_change(20)),[80,90,97,99.5]) for t in ['SOXL','TQQQ']],axis=1).max(axis=1)
H=pd.DataFrame(H); srt=np.sort(H.fillna(0).values,axis=1); top,sec=srt[:,-1],srt[:,-2]
heat=pd.Series(np.where(sec>=top-1,top,top-1),index=idx)
nm={0:'冷静',1:'升温',2:'偏热',3:'过热',4:'狂热'}
o=pd.read_csv('thermo.csv',index_col=0,parse_dates=True)
out=pd.concat([heat.rename('过热度'),heat.map(nm).rename('过热档'),H],axis=1).loc['2018-01-01':]
out=out.join(o[['体温','档位']]); out.to_csv('heat.csv')
print(out['过热档'].value_counts(normalize=True).round(3).to_dict())
for a_,b_,l in [('2017-12-15','2018-01-26','2018-01融涨'),('2020-07-01','2020-09-02','2020-08科技'),('2021-01-04','2021-02-16','2021-02'),('2023-05-15','2023-07-31','2023 AI'),('2024-02-15','2024-07-10','2024半导体'),('2026-04-10','2026-06-04','2026-05半导体'),('2022-01-01','2022-10-31','2022熊市'),('2026-10-01','2026-10-30','2026-10')]:
    s=out.loc[a_:b_]; print(f'{l:10s}', '过热', s['过热档'].value_counts().to_dict(), '| 体温', s['档位'].value_counts().to_dict())
pd.set_option('display.width',200); print(out.loc['2026-04-01':'2026-07-31'].iloc[::5].to_string())
