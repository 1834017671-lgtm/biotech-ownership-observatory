"""Scheduled refresh: check SEC EDGAR for new 13F filings, refresh daily prices, rebuild dist/. Partial failures are logged, never fatal."""
import json,pathlib,datetime,subprocess,sys,os,time,urllib.request
BASE=pathlib.Path(__file__).resolve().parents[1]
# SEC asks automated clients to identify themselves with a contact, e.g. SEC_USER_AGENT="Jane Doe research jane@example.com".
UA=os.environ.get('SEC_USER_AGENT','')
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
def run(script,**env):
 r=subprocess.run([sys.executable,str(BASE/'scripts'/script)],cwd=BASE,env={**os.environ,**env})
 return r.returncode==0
def sec_filings(cik):
 req=urllib.request.Request(f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json',headers={'User-Agent':UA,'Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as r:recent=json.load(r)['filings']['recent']
 return [{'accession':a,'form':f,'filed':d,'period':p} for a,f,d,p in zip(recent['accessionNumber'],recent['form'],recent['filingDate'],recent['reportDate']) if f in ('13F-HR','13F-HR/A')]
def main():
 entry={'run':NOW,'newFilings':[],'errors':[]}
 holdings=json.loads((BASE/'data/holdings.json').read_text())
 known={r['accession'] for f in holdings['funds'] for r in f['filings']}
 period=max(f['filings'][0]['period'] for f in holdings['funds'] if f['filings'])
 if UA:
  for f in holdings['funds']:
   try:
    time.sleep(.2)
    latest=[x for x in sec_filings(f['cik']) if x['period']>=period]
    entry['newFilings']+=[{'fund':f['name'],**x} for x in latest if x['accession'] not in known]
   except Exception as e:entry['errors'].append({'source':'SEC EDGAR','fund':f['name'],'error':str(e)})
 else:entry['errors'].append({'source':'SEC EDGAR','error':'SEC_USER_AGENT not set; new-filing check skipped'})
 funds=sorted({x['fund'] for x in entry['newFilings']})
 if funds:
  before=json.loads((BASE/'data/holdings.json').read_text())
  ok=run('collect.py',FORCE_REFRESH='1',ONLY_FUNDS=','.join(funds),COLLECT_DELAY=os.environ.get('COLLECT_DELAY','3'))
  after=json.loads((BASE/'data/holdings.json').read_text())
  if not ok or len(after['funds'])!=len(before['funds']) or any(not f['filings'] for f in after['funds']):
   (BASE/'data/holdings.json').write_text(json.dumps(before,indent=2));entry['errors'].append({'source':'13f.info','error':'Collection incomplete; previous holdings kept. Filings retried next run.','funds':funds})
  else:entry['amendments']=[x for x in entry['newFilings'] if x['form']=='13F-HR/A']
 run('prepare.py')
 if not run('market.py',FORCE_REFRESH='1',MARKET_DELAY=os.environ.get('MARKET_DELAY','1'),MARKET_WORKERS=os.environ.get('MARKET_WORKERS','2')):entry['errors'].append({'source':'Yahoo Finance / Stock Analysis','error':'Market step failed; previous market data kept'})
 market=json.loads((BASE/'data/market.json').read_text())
 entry['prices']={'withPrices':sum(1 for m in market.values() if m.get('technical')),'carriedForward':sorted(t for t,m in market.items() if m.get('carriedForward')),'missing':sorted(t for t,m in market.items() if not m.get('technical'))}
 newperiod=max(f['filings'][0]['period'] for f in json.loads((BASE/'data/holdings.json').read_text())['funds'] if f['filings'])
 if newperiod!=period or os.environ.get('REFRESH_HOLDERS')=='1':
  if not run('holders.py',HOLDERS_DELAY=os.environ.get('HOLDERS_DELAY','2'),HOLDERS_WORKERS='1'):entry['errors'].append({'source':'13f.info holders','error':'Holder step failed; previous holder data kept'})
 log=json.loads((BASE/'data/refresh-log.json').read_text()) if (BASE/'data/refresh-log.json').exists() else []
 (BASE/'data/refresh-log.json').write_text(json.dumps((log+[entry])[-200:],indent=1))
 run('prepare.py')
 print(json.dumps({k:v for k,v in entry.items() if k!='prices'}|{'withPrices':entry['prices']['withPrices'],'carriedForward':len(entry['prices']['carriedForward']),'missing':len(entry['prices']['missing'])}),flush=True)
if __name__=='__main__':main()
