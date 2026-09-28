"""Public filing snapshot collector. Standard library only; caches source responses."""
import json, re, time, urllib.request, urllib.error, urllib.parse, pathlib, html, datetime, xml.etree.ElementTree as ET, os, random, ssl
BASE=pathlib.Path(__file__).resolve().parents[1]
CACHE=BASE/'data'/'raw'; CACHE.mkdir(parents=True,exist_ok=True)
FUNDS=[('perceptive','Perceptive Advisors',1224962,'perceptive-advisors-llc'),('avoro','Avoro Capital',1633313,'avoro-capital-advisors-llc'),('ra','RA Capital',1346824,'ra-capital-management-l-p'),('cormorant','Cormorant',1583977,'cormorant-asset-management-lp'),('ecor1','EcoR1 Capital',1587114,'ecor1-capital-llc'),('caligan','Caligan Partners',1727492,'caligan-partners-lp'),('bvf','BVF Partners',1056807,'bvf-inc-il'),('adar1','ADAR1 Capital',1940272,'adar1-capital-management-llc'),('deeptrack','Deep Track',1856083,'deep-track-capital-lp'),('rtw','RTW Investments',1493215,'rtw-investments-lp')]
UNIVERSE={}
if (BASE/'data/universe.json').exists():
 entries=json.loads((BASE/'data/universe.json').read_text());UNIVERSE={f['id']:f for f in entries}
 FUNDS=[(f['id'],f['name'],int(f['cik']),f['source'].split('/manager/')[1][11:]) for f in entries]
# ONLY_FUNDS="Opaleye,Decheng" (names or ids) limits FORCE_REFRESH re-downloads to those managers; others reuse cached pages.
ONLY={x.strip().lower() for x in os.environ.get('ONLY_FUNDS','').split(',') if x.strip()}
# COLLECT_DELAY seconds (plus up to 50% jitter) between network requests; transient failures retry with exponential backoff.
DELAY=float(os.environ.get('COLLECT_DELAY','.25'));ATTEMPTS=int(os.environ.get('COLLECT_ATTEMPTS','4'))
def fetch(url):
 for attempt in range(ATTEMPTS):
  time.sleep(DELAY*(1+random.random()/2))
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'BiotechOwnershipResearch/1.0 public data research','Accept':'*/*'})
   with urllib.request.urlopen(req,timeout=35) as r: return r.read().decode()
  except urllib.error.HTTPError as e:
   if e.code not in (429,500,502,503,504) or attempt==ATTEMPTS-1:raise
   wait=float(e.headers.get('Retry-After') or 0)
  except (urllib.error.URLError,TimeoutError,ConnectionError,ssl.SSLError) as e:
   if attempt==ATTEMPTS-1:raise
   wait=0
  backoff=max(wait,5*2**attempt*(1+random.random()/2));print(f'  retry {attempt+1}/{ATTEMPTS-1} in {backoff:.0f}s: {url}',flush=True);time.sleep(backoff)
def get(url,key,fresh=False):
 p=CACHE/key
 if p.exists() and not fresh: return p.read_text()
 s=fetch(url);p.write_text(s); return s
def text(s):return html.unescape(re.sub('<[^>]+>','',s)).strip()
def main():
 out=[]; errors=[]
 for fid,name,cik,slug in FUNDS:
  try:
   url=f'https://13f.info/manager/{cik:010d}-{slug}'
   page=get(url,f'{fid}-manager.html',fresh=os.environ.get('FORCE_REFRESH')=='1' and (not ONLY or fid.lower() in ONLY or name.lower() in ONLY))
   records=[]; seen=set()
   for row in re.findall(r'<tr[^>]*>(.*?)</tr>',page,re.S):
    link=re.search(r'href="(/13f/(\d{18})-[^"]+)"',row)
    cells=[text(x) for x in re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)]
    if not link or len(cells)<6:continue
    quarter=cells[0]
    if quarter in seen or not re.match(r'Q[1-4] 20\d\d',quarter):continue
    seen.add(quarter)
    acc=link[2]; q=int(quarter[1]);year=int(quarter[3:7]); period=f'{year}-{q*3:02d}-'+('30' if q in (2,3) else '31')
    try:
     dataurl=f'https://13f.info/data/13f/{acc}'
     rows=json.loads(get(dataurl,f'{acc}.json'))['data']
     positions=[{'ticker':r[0] or None,'name':r[1],'class':r[2],'cusip':r[3],'value':r[4]*1000,'shares':r[6],'option':r[8] or None} for r in rows]
     dash=f'{acc[:10]}-{acc[10:12]}-{acc[12:]}'
     rec={'quarter':quarter,'period':period,'filed':cells[5],'accession':dash,'form':cells[4],'source':f'https://13f.info{link[1]}','sec':f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{dash}-index.html','reportedTotal':float(cells[2].replace(',',''))*1000,'positions':positions,'provenance':'13f.info reproduction of SEC filing; values rounded to $1,000'}
     # The latest quarter is cross-checked against SEC XML when accessible.
     if not records:
      try:
       index=get(rec['sec'],f'{acc}-index.html')
       xmls=re.findall(r'href="([^"]+\.xml)"',index)
       info=[x for x in xmls if 'primary' not in x and 'xsl' not in x]
       if not info:info=[f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/infotable.xml']
       for path in info:
        xmlurl=urllib.parse.urljoin(rec['sec'],path)
        xml=get(xmlurl,f'{acc}-info.xml')
        root=ET.fromstring(xml)
        for el in root.iter():el.tag=el.tag.split('}')[-1]
        nodes=root.findall('.//infoTable')
        if not nodes:continue
        ticks={p['cusip']:p['ticker'] for p in positions};primary=[]
        for n in nodes:
         val=lambda k:n.findtext('.//'+k)
         primary.append({'ticker':ticks.get(val('cusip')),'name':val('nameOfIssuer'),'class':val('titleOfClass'),'cusip':val('cusip'),'value':float(val('value')),'shares':float(val('sshPrnamt')),'option':val('putCall')})
        # Current schema reports dollars. Reject units mismatches.
        total=sum(p['value'] for p in primary)
        if abs(total-rec['reportedTotal'])/max(1,rec['reportedTotal'])<.005:
         rec['positions']=primary;rec['provenance']='SEC information table XML; ticker mapping from 13f.info';rec['xml']=xmlurl;rec['reportedTotal']=total
        break
      except Exception as e:rec['primaryFetchNote']=str(e)
     records.append(rec)
     print(name,quarter,len(positions),flush=True)
    except Exception as e:errors.append({'fund':name,'quarter':quarter,'error':str(e)})
    if len(records)>=9:break
   out.append({**UNIVERSE.get(fid,{}),'id':fid,'name':name,'cik':str(cik).zfill(10),'source':url,'filings':records})
  except Exception as e:errors.append({'fund':name,'error':str(e)})
  (BASE/'data'/'holdings.json').write_text(json.dumps({'retrieved':datetime.datetime.now(datetime.timezone.utc).isoformat(),'funds':out,'errors':errors},indent=2))
 print(json.dumps({'funds':len(out),'errors':errors}),flush=True)
if __name__=='__main__':main()
