"""离线拉取资金面/杠杆历史（Demo 用）。"""
import io, json, time, urllib.request, urllib.parse, pandas as pd, datetime as dt, os, sys
UA={'User-Agent':'Mozilla/5.0 (Macintosh) Chrome/130'}
def get(u,timeout=120):
    for i in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=timeout).read()
        except Exception as e: err=e; time.sleep(2)
    raise err
os.makedirs('flows',exist_ok=True)
what=sys.argv[1:] or ['etf','cftc','fred','margin','pc_hist']
if 'etf' in what:
    out=[]
    for t in ['TQQQ','SQQQ','UPRO','SPXU','QLD','SSO','USD','SDS','QID']:
        d=pd.read_csv(io.BytesIO(get(f'https://accounts.profunds.com/etfdata/ByFund/{t}-historical_nav.csv')))
        d.columns=[c.strip() for c in d.columns]; d['Date']=pd.to_datetime(d['Date'])
        out.append(pd.DataFrame({'date':d['Date'],'ticker':t,'nav':d['NAV'],'shares':d['Shares Outstanding (000)']*1000,'aum':d['Assets Under Management']})); print(t,len(d))
    for t in ['spy','xlk','xly','xlf','xle','xli','xlv','xlp','xlu','xlb','xlre','xlc']:
        d=pd.read_excel(io.BytesIO(get(f'https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-{t}.xlsx')),header=3)
        d=d[pd.to_datetime(d['Date'],errors='coerce').notna()]
        out.append(pd.DataFrame({'date':pd.to_datetime(d['Date']),'ticker':t.upper(),'nav':pd.to_numeric(d['NAV'],errors='coerce'),'shares':pd.to_numeric(d['Shares Outstanding'],errors='coerce'),'aum':pd.to_numeric(d['Total Net Assets'],errors='coerce')})); print(t,len(d))
    pd.concat(out).to_csv('flows/etf.csv',index=False)
if 'cftc' in what:
    q={'$select':'report_date_as_yyyy_mm_dd,market_and_exchange_names,open_interest_all,lev_money_positions_long,lev_money_positions_short,asset_mgr_positions_long,asset_mgr_positions_short,dealer_positions_long_all,dealer_positions_short_all',
       '$where':"market_and_exchange_names in ('NASDAQ-100 Consolidated - CHICAGO MERCANTILE EXCHANGE','E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE','NASDAQ MINI - CHICAGO MERCANTILE EXCHANGE','S&P 500 Consolidated - CHICAGO MERCANTILE EXCHANGE','VIX FUTURES - CBOE FUTURES EXCHANGE','JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE','UST 10Y NOTE - CHICAGO BOARD OF TRADE','UST 2Y NOTE - CHICAGO BOARD OF TRADE')",
       '$limit':50000,'$order':'report_date_as_yyyy_mm_dd'}
    d=pd.DataFrame(json.loads(get('https://publicreporting.cftc.gov/resource/gpe5-46if.json?'+urllib.parse.urlencode(q))))
    d.to_csv('flows/cftc.csv',index=False); print('cftc',len(d),d.market_and_exchange_names.value_counts().to_dict())
if 'fred' in what:
    fr={}
    for s in ['WALCL','WTREGEN','RRPONTSYD','SOFR','IORB','IOER','STLFSI4','WRMFNS']:
        d=pd.read_csv(io.BytesIO(get(f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}')),index_col=0,parse_dates=True,na_values='.'); fr[s]=d.iloc[:,0]; print(s,len(d))
    pd.DataFrame(fr).to_csv('flows/fred2.csv')
    d=pd.read_csv(io.BytesIO(get('https://www.financialresearch.gov/financial-stress-index/data/fsi.csv'))); d.to_csv('flows/ofr_fsi.csv',index=False)
    for s in ['SKEW','VVIX','VIX9D']:
        open(f'flows/{s}.csv','wb').write(get(f'https://cdn.cboe.com/api/global/us_indices/daily_prices/{s}_History.csv'))
if 'margin' in what:
    open('flows/margin.xlsx','wb').write(get('https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx'))
if 'pc_hist' in what:
    open('flows/totalpc.csv','wb').write(get('https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv'))
    open('flows/equitypc.csv','wb').write(get('https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv'))
if 'pc_daily' in what:   # 2019-10-07 起逐日
    fn='flows/pc_daily.jsonl'; done=set()
    if os.path.exists(fn): done={json.loads(l)['d'] for l in open(fn)}
    f=open(fn,'a')
    for d in pd.bdate_range('2019-10-07','2026-10-30'):
        ds=d.strftime('%Y-%m-%d')
        if ds in done: continue
        try: j=json.loads(get(f'https://cdn.cboe.com/data/us/options/market_statistics/daily/{ds}_daily_options',timeout=30))
        except Exception as e: continue
        r={x['name']:x['value'] for x in j.get('ratios',[])}; f.write(json.dumps({'d':ds,'r':r})+'\n'); f.flush(); time.sleep(0.3)
if 'cnn' in what:
    j=json.loads(urllib.request.urlopen(urllib.request.Request('https://production.dataviz.cnn.io/index/fearandgreed/graphdata/2020-07-15',headers={**UA,'Referer':'https://www.cnn.com/'}),timeout=60).read())
    json.dump(j,open('flows/cnn.json','w'))
