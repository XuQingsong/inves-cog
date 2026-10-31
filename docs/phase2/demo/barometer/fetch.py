import yfinance as yf, pandas as pd, urllib.request, yaml, io
core=yaml.safe_load(open('/Users/xuqingsong/workspace/inves-cog/config/core_companies.yaml'))['companies']
ai=[c['ticker'] if isinstance(c,dict) else c for c in core]
etf=['SPY','RSP','QQQ','IWM','SMH','HYG','LQD','IEF','TLT','XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY','^VIX','^VIX3M']
px=yf.download(etf+ai,start='2012-01-01',auto_adjust=True,progress=False)['Close']
px.to_csv('px.csv'); print(px.shape, ai)
fr={}
for s in ['DGS10','DGS2','T10Y2Y','BAMLH0A0HYM2','BAMLC0A0CM','NFCI','NFCICREDIT','NFCILEVERAGE','NFCIRISK']:
    d=pd.read_csv(io.StringIO(urllib.request.urlopen(f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}',timeout=60).read().decode()),index_col=0,parse_dates=True,na_values='.')
    fr[s]=d.iloc[:,0]; print(s,d.index.min().date(),d.index.max().date())
pd.DataFrame(fr).to_csv('fred.csv')
