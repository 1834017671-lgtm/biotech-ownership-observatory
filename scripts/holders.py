"""Broader 13F shareholder context; these managers do not enter the screen universe."""
import json,pathlib,subprocess,concurrent.futures,datetime,os,time,random
BASE=pathlib.Path(__file__).resolve().parents[1]
CACHE=BASE/'data'/'holder-raw';CACHE.mkdir(exist_ok=True)
HOLDINGS=json.loads((BASE/'data/holdings.json').read_text())
PERIOD=max(f['filings'][0]['period'] for f in HOLDINGS['funds'] if f['filings'])
# HOLDERS_FORCE=0 reuses cached quarter tables even when FORCE_REFRESH=1; HOLDERS_DELAY/HOLDERS_WORKERS pace 13f.info requests.
FORCE=os.environ.get('HOLDERS_FORCE',os.environ.get('FORCE_REFRESH'))=='1';DELAY=float(os.environ.get('HOLDERS_DELAY','0'));WORKERS=int(os.environ.get('HOLDERS_WORKERS','3'))
YEAR=int(PERIOD[:4]);QUARTER=int(PERIOD[5:7])//3
def one(p):
 result={'period':PERIOD,'holders':[],'sources':[],'retrieved':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  merged={}
  for cusip in set(p['cusips']):
   url=f'https://13f.info/data/cusip/{cusip}/{YEAR}/{QUARTER}';cache=CACHE/(cusip+f'-{YEAR}-{QUARTER}.json')
   legacy=CACHE/(cusip+'.json')
   if not cache.exists() and legacy.exists() and PERIOD=='2026-06-30':cache.write_text(legacy.read_text())
   if cache.exists() and not FORCE:s=cache.read_text()
   else:
    time.sleep(DELAY*(1+random.random()/2))
    r=subprocess.run(['curl','--fail','-L','-s','--max-time','25','--retry','3','--retry-connrefused',url],capture_output=True,text=True)
    if r.returncode:raise RuntimeError('Holder source unavailable')
    s=r.stdout;cache.write_text(s)
   data=json.loads(s)['data'];result['sources'].append(f'https://13f.info/cusip/{cusip}/{YEAR}/{QUARTER}')
   for row in data:
    if row[4] or row[1][0]!=PERIOD:continue
    name,cik,_=row[0];key=cik
    if key not in merged:merged[key]={'name':name,'cik':cik,'shares':0,'value':0,'source':'https://13f.info/13f/'+row[1][1]}
    merged[key]['shares']+=row[3] or 0;merged[key]['value']+=row[2]*1000
  result['holders']=sorted(merged.values(),key=lambda h:-h['value'])[:30];result['reportedHolderCount']=len(merged)
 except Exception as e:result['error']=str(e)
 return p['ticker'] or p['key'],result
def main():
 candidates=json.loads((BASE/'data/candidates.json').read_text());result={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
  for ticker,info in pool.map(one,candidates):
   result[ticker]=info;print(ticker,len(info['holders']),flush=True)
 (BASE/'data/holders.json').write_text(json.dumps(result,indent=2))
if __name__=='__main__':main()
