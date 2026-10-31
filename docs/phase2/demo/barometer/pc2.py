import json,sys,time,urllib.request,pandas as pd
a,b,fn=sys.argv[1:4]; f=open(fn,'a')
for d in pd.bdate_range(a,b):
    ds=d.strftime('%Y-%m-%d')
    try: j=json.loads(urllib.request.urlopen(urllib.request.Request(f'https://cdn.cboe.com/data/us/options/market_statistics/daily/{ds}_daily_options',headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read())
    except Exception: continue
    f.write(json.dumps({'d':ds,'r':{x['name']:x['value'] for x in j.get('ratios',[])}})+'\n'); f.flush()
