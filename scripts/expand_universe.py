"""Select 50 current US-based specialist reporters from a documented 60-manager pool."""
import json,pathlib,re,html,subprocess,concurrent.futures,datetime,time
BASE=pathlib.Path(__file__).resolve().parents[1];RAW=BASE/'data/raw'
def get(url,key):
 p=RAW/key
 if p.exists():return p.read_text()
 r=subprocess.run(['curl','--fail','-L','-s','--max-time','30',url],capture_output=True,text=True)
 if r.returncode:raise RuntimeError(f'Public source unavailable: {url}')
 p.write_text(r.stdout);return r.stdout
def plain(s):return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>','',s))).strip()
old=json.loads((BASE/'data/holdings.json').read_text());known={f['cik']:f for f in old['funds']}
discovery=json.loads((BASE/'data/universe-discovery.json').read_text())
pool=[]
for q,matches in discovery.items():
 if not matches:continue
 m=next((m for m in matches if 'Sarissa Capital' in m['name']),matches[0]) if q=='Sarissa' else matches[0]
 cik=re.search(r'/manager/(\d{10})',m['url'])[1]
 pool.append({'id':'f'+cik,'name':q,'legalName':m['name'],'cik':cik,'source':'https://13f.info'+m['url'],'location':m.get('extra'),'inclusionSources':['https://www.biopharmawatch.com/biotech-hedge-funds','https://rxdatalab.com/research/biotech-specialist-investors/','https://www.stifel.com/newsletters/investmentbanking/bal/marketing/healthcare/biopharma_timopler/2026/BiopharmaMarketUpdate_052826.pdf'],'rationale':'US-based healthcare/life-sciences specialist candidate; current public equity reporting; ranked by reported 13F value within the researched candidate pool.'})
pool.extend({k:v for k,v in f.items() if k!='filings'} for f in old['funds'] if f['cik'] not in {x['cik'] for x in pool})
def metadata(f):
 page=get(f['source'],f['id']+'-manager.html');records=[];seen=set()
 for row in re.findall(r'<tr[^>]*>(.*?)</tr>',page,re.S):
  link=re.search(r'href="(/13f/(\d{18})-[^"]+)"',row);cells=[plain(c) for c in re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)]
  if not link or len(cells)<6 or not re.match(r'Q[1-4] 20\d\d',cells[0]) or cells[0] in seen:continue
  quarter=cells[0];seen.add(quarter);q=int(quarter[1]);year=int(quarter[3:7]);period=f'{year}-{q*3:02d}-'+('30' if q in (2,3) else '31');acc=link[2];dash=f'{acc[:10]}-{acc[10:12]}-{acc[12:]}'
  records.append({'quarter':quarter,'period':period,'filed':cells[5],'accession':dash,'form':cells[4],'source':'https://13f.info'+link[1],'sec':f'https://www.sec.gov/Archives/edgar/data/{int(f["cik"])}/{acc}/{dash}-index.html','reportedTotal':float(cells[2].replace(',',''))*1000,'provenance':'13f.info reproduction of SEC filing; values at $1,000 precision'})
  if len(records)>=9:break
 if not records:raise RuntimeError('No quarterly filing: '+f['name'])
 return {**f,'filings':records}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as p:metadata_funds=list(p.map(metadata,pool))
period=max(f['filings'][0]['period'] for f in metadata_funds)
eligible=[f for f in metadata_funds if f['filings'][0]['period']==period]
selected=sorted(eligible,key=lambda f:-f['filings'][0]['reportedTotal'])[:50]
if len(selected)<50:raise RuntimeError(f'Only {len(selected)} current candidates; do not fabricate fund coverage')
(BASE/'data/universe-selection.json').write_text(json.dumps({'period':period,'candidateCount':len(pool),'currentCandidates':len(eligible),'selection':'Largest 50 reported 13F portfolios among a curated US-based healthcare-specialist pool; not a comprehensive global ranking or a return ranking. Includes crossover investors; 13F value is not AUM.','selected':[{k:v for k,v in f.items() if k!='filings'}|{'reportedValue':f['filings'][0]['reportedTotal']} for f in selected],'excluded':[{'name':f['name'],'period':f['filings'][0]['period'],'value':f['filings'][0]['reportedTotal']} for f in metadata_funds if f not in selected]},indent=2))
for f in selected:print('SELECT',f['name'],f['cik'],round(f['filings'][0]['reportedTotal']/1e9,2),flush=True)
def holdings(f):
 prior=known.get(f['cik'])
 for i,r in enumerate(f['filings']):
  if prior:
   oldr=next((x for x in prior['filings'] if x['accession']==r['accession']),None)
   if oldr:f['filings'][i]=oldr;continue
  acc=r['accession'].replace('-','');rows=json.loads(get('https://13f.info/data/13f/'+acc,acc+'.json'))['data']
  r['positions']=[{'ticker':x[0] or None,'name':x[1],'class':x[2],'cusip':x[3],'value':x[4]*1000,'shares':x[6],'option':x[8] or None} for x in rows]
 print('LOADED',f['name'],len(f['filings']),flush=True)
 return f
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as p:funds=list(p.map(holdings,selected))
stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
(BASE/'data/holdings-10-original.json').write_text(json.dumps(old,indent=2))
(BASE/'data/holdings.json').write_text(json.dumps({'retrieved':stamp,'funds':funds,'errors':[]},indent=2))
(BASE/'data/universe.json').write_text(json.dumps([{k:v for k,v in f.items() if k!='filings'} for f in funds],indent=2))
print('COMPLETE',len(funds),'funds',sum(len(f['filings']) for f in funds),'quarterly snapshots',flush=True)
