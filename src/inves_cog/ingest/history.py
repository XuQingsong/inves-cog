"""R7 CSV.gz import: source exports stay outside the repository."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from inves_cog.ingest.repository import identity, json_text, Repository

TABLES={'data.insider_transactions','data.vix_daily'}

def read_exports(directory):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text())
    verified=[]
    for table in manifest['tables']:
        if table['table'] not in TABLES: continue
        filename=table['file']
        if Path(filename).name!=filename or not filename.endswith('.csv.gz'):
            raise ValueError('Invalid export filename')
        data=(directory/filename).read_bytes()
        if hashlib.sha256(data).hexdigest()!=table['sha256']:
            raise ValueError('Export checksum mismatch: '+filename)
        rows=list(csv.DictReader(io.StringIO(gzip.decompress(data).decode('utf-8'))))
        if len(rows)!=table['rows']: raise ValueError('Export row count mismatch: '+filename)
        for row in rows:
            if None in row: raise ValueError('Malformed CSV record')
            verified.append({'table':table['table'],'raw':row,'file_sha256':table['sha256']})
    if not verified: raise ValueError('No R7 Form 4/VIX exports')
    yield from verified

def number(value):
    if value in (None,'','\\N'): return None
    result=float(value)
    if not math.isfinite(result): raise ValueError('Non-finite export number')
    return result

def boolean(value):
    if value in (None,'','\\N'): return None
    if value.lower() in {'true','t','1'}: return True
    if value.lower() in {'false','f','0'}: return False
    raise ValueError('Invalid export boolean')

def form4_record(record,*,clock):
    raw=dict(record['raw'])
    raw['import_flags']=['visibility_time_unknown','accession_missing']
    raw['file_sha256']=record['file_sha256']
    return {'event_id':'muse-form4:'+identity(record['raw']),'ticker':raw['ticker'],
        'filed_at':None,'insider_name':raw.get('owner'), 'is_officer':boolean(raw.get('is_officer')),
        'transaction_code':raw.get('code'),'shares':number(raw.get('shares')),
        'price':number(raw.get('price')),'accession':None,'transaction_index':None,
        'source':'MuseExport','raw':raw}

def import_exports(directory,*,connection,clock):
    records=list(read_exports(directory))
    counts={name:{'source_rows':0,'inserted':0} for name in TABLES}
    repo=Repository(connection)
    with connection.transaction():
        for record in records:
            table,raw=record['table'],record['raw']
            counts[table]['source_rows']+=1
            gaps=['visibility_time_unknown','accession_missing'] if table.endswith('insider_transactions') else ['historical_vintage_unknown']
            inserted=connection.execute('INSERT INTO ingest.offline_history (source_table,record_id,raw,file_sha256,imported_at,gaps) VALUES (%s,%s,%s::jsonb,%s,%s,%s) ON CONFLICT (source_table,record_id) DO NOTHING RETURNING record_id',
                (table,identity(raw),json_text(raw),record['file_sha256'],clock.now_utc(),gaps)).fetchone()
            counts[table]['inserted']+=inserted is not None
            if table.endswith('insider_transactions'):
                repo.write('form4_events',form4_record(record,clock=clock))
        # No observation date is relabelled as FRED realtime_start.
        repo.set_cursor('r7-offline-import',{'tables':counts,'form4_gaps':['filed_at','accession'],
            'vix_gap':'No historical vintage supplied; retained in offline_history, excluded from PIT macro observations'},clock.now_utc())
    return counts

def main():
    from inves_cog.clock import SystemClock
    from inves_cog.ingest.cli import connect
    from inves_cog.ingest.settings import read_environment
    parser=argparse.ArgumentParser(description='Import authorized R7 offline exports into inves_cog')
    parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    with connect(read_environment()) as connection:
        report=import_exports(args.directory,connection=connection,clock=SystemClock())
    if args.output: args.output.write_text(json_text(report)+'\n')
    print(json_text(report))

if __name__=='__main__': main()
