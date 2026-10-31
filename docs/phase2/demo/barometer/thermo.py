import pandas as pd, numpy as np
a=pd.read_csv('px.csv',index_col=0,parse_dates=True); b=pd.read_csv('px2.csv',index_col=0,parse_dates=True)
px=a.join(b[[c for c in b if c not in a]],how='left').sort_index()
idx=px['SPY'].dropna().index; px=px.reindex(idx).ffill(limit=3)
S,Q,V,V3=px['SPY'],px['QQQ'],px['^VIX'],px['^VIX3M']
sect=['XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY']
def lv(x,cuts):  # cuts ascending thresholds for 1..4
    return sum((x>=c) for c in cuts).astype(float).where(x.notna())
D={}
# 1 price: worst of SPY/QQQ
def price(p):
    r=p.pct_change(); z=(-r)/r.rolling(60).std().shift(1); dd=-(p/p.rolling(63).max()-1)*100; r5=-p.pct_change(5)*100
    return pd.concat([lv(z,[1.5,2.5,4,6]),lv(dd,[3,6,10,15]),lv(r5,[2.5,4,7,10])],axis=1).max(axis=1)
D['股价']=pd.concat([price(S),price(Q)],axis=1).max(axis=1)
ratio=V/V3
D['恐慌']=pd.concat([lv(V,[15,20,25,35]),lv(V.pct_change(5)*100,[15,30,60,100]).clip(upper=3),lv(ratio,[0.92,0.98,1.0,1.15])],axis=1).max(axis=1)
tnx=px['^TNX']; dy=(tnx-tnx.shift(10)).abs()*100
D['债市']=pd.concat([lv(px['^MOVE'],[90,110,130,160]),lv(dy,[20,30,50,80]).clip(upper=3),lv(-px['HYG'].pct_change(10)*100,[1.5,3,6,10])],axis=1).max(axis=1)
sp=px[sect]; below50=(sp<sp.rolling(50).mean()).sum(axis=1)/sp.notna().sum(axis=1); below200=(sp<sp.rolling(200).mean()).sum(axis=1)/sp.notna().sum(axis=1)
down=(sp.pct_change()<0).sum(axis=1)/sp.notna().sum(axis=1)
mass=((down>=10/11)&(S.pct_change()<=-0.015)).astype(float)*3
D['扩散']=pd.concat([lv(below50,[0.4,0.6,0.8,2]),lv(below200,[0.5,0.65,0.8,0.9]),mass],axis=1).max(axis=1)
yen=-px['JPY=X'].pct_change(5)*100
liq=((px['GLD'].pct_change(5)<=-0.02)&(px['BTC-USD'].pct_change(5)<=-0.08)&(S.pct_change(5)<=-0.03)).astype(float)*3
sb=((S.pct_change(10)<=-0.03)&(px['TLT'].pct_change(10)<=-0.03)).astype(float)*2
D['跨资产']=pd.concat([lv(yen,[1.5,3,5,7]),liq,sb],axis=1).max(axis=1)
D=pd.DataFrame(D)
# deleveraging fingerprints (amplifier evidence)
mom=(px['MTUM']/S).pct_change(5)*100
delev=pd.DataFrame({'动量股踩踏':mom<=-3,'杠杆ETF重挫':px['TQQQ'].pct_change(5)<=-0.15,'VIX倒挂':ratio>1.0,'股债同跌':sb>0,'全资产抛售':liq>0,'日元急升':yen>=3})
nd=delev.sum(axis=1)
# temperature: max dimension, downgraded one level if no second dimension within 1 level; deleveraging (>=2 fingerprints) -> at least 3
srt=np.sort(D.fillna(0).values,axis=1); top,second=srt[:,-1],srt[:,-2]
T=np.where(second>=top-1,top,top-1); T=pd.Series(T,index=idx)
T=T.where(nd<2,np.maximum(T,3))
names={0:'平静',1:'正常波动',2:'偏紧张',3:'紧张',4:'恐慌'}
ma=lambda p,n:p.rolling(n).mean()
amp=pd.DataFrame({'QQQ距50日线%':(Q/ma(Q,50)-1)*100,'QQQ距200日线%':(Q/ma(Q,200)-1)*100,'QQQ距半年低点%':(Q/Q.rolling(126).min()-1)*100,'SPY距200日线%':(S/ma(S,200)-1)*100})
out=pd.concat([T.rename('体温'),T.map(names).rename('档位'),D,delev,amp.round(1)],axis=1).loc['2018-01-01':]
out.to_csv('thermo.csv')
print(out['档位'].value_counts(normalize=True).round(3).to_dict())
def ep(a,b,lab):
    s=out.loc[a:b]; print(f'{lab:14s} {a}~{b} 最高 {names[int(s["体温"].max())]}  分布 {s["档位"].value_counts().to_dict()}')
for a,b,l in [('2018-02-01','2018-02-15','2018-02波动率'),('2018-10-01','2018-12-31','2018Q4'),('2020-02-20','2020-04-10','2020疫情'),('2022-01-01','2022-10-31','2022加息'),('2023-03-06','2023-03-24','2023硅谷银行'),('2024-07-15','2024-08-15','2024-08套息'),('2025-03-25','2025-04-30','2025关税'),('2019-01-15','2019-12-31','2019'),('2026-09-01','2026-09-30','2026-09加息'),('2026-10-01','2026-10-30','2026-10')]: ep(a,b,l)
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
print(out.loc['2026-10-13':,['档位','股价','恐慌','债市','扩散','跨资产','QQQ距200日线%','QQQ距半年低点%']])
