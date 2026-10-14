"""Hash validation and comparison against the independent Muse oracle."""
from datetime import date
import gzip
import hashlib
import json
import math
from inves_cog.ingest.fundamentals.extractors import extract_state

def compare_muse_export(folder):
    manifest=json.loads((folder/'legacy_oracle/manifest.json').read_text())
    if manifest['source_commit']!='aacea04e4562f70854d69330fe724aa2799f2858': raise ValueError('Unapproved source commit')
    mismatches=[]; tickers=set(); dates=set(); caches={}; compared=0
    for row in manifest['items']:
        ticker,as_of=row['ticker'],row['as_of']; tickers.add(ticker); dates.add(as_of)
        blob=(folder/'companyfacts'/f'{ticker}_facts.json.gz').read_bytes()
        if hashlib.sha256(gzip.decompress(blob)).hexdigest()!=row['cache_sha256']: raise ValueError('Companyfacts hash mismatch: '+ticker)
        if ticker not in caches: caches[ticker]=json.loads(gzip.decompress(blob))
        raw=(folder/'legacy_oracle'/row['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['output_sha256']: raise ValueError('Oracle hash mismatch: '+row['file'])
        expected=json.loads(gzip.decompress(raw))['pit_fundamentals']
        actual=extract_state(caches[ticker],ticker=ticker,as_of=date.fromisoformat(as_of),extractor='legacy',price=row['price_input']).oracle_values
        for key in sorted(set(actual)|set(expected)):
            a,b=actual.get(key),expected.get(key); same=(key in actual)==(key in expected)
            if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool): same=same and math.isclose(a,b,rel_tol=1e-9,abs_tol=0)
            else: same=same and a==b
            if not same: mismatches.append({'ticker':ticker,'as_of':as_of,'field':key,'expected':b,'actual':a,'expected_present':key in expected,'actual_present':key in actual})
            compared+=1
    return {'tickers':len(tickers),'dates':len(dates),'states':len(manifest['items']),'fields_compared':compared,'mismatches':mismatches}
