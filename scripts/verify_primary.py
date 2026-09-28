"""Reconcile latest information tables with SEC XML without changing raw archives."""
import json,pathlib,subprocess,xml.etree.ElementTree as ET,concurrent.futures
BASE=pathlib.Path(__file__).resolve().parents[1]
def fetch(url):
 r=subprocess.run(['curl','--fail','-L','-s','--max-time','15',url],capture_output=True,text=True)
 if r.returncode:raise RuntimeError('SEC download unavailable')
 return r.stdout
def one(f):
 r=f['filings'][0];acc=r['accession'].replace('-','');base=f'https://www.sec.gov/Archives/edgar/data/{int(f["cik"])}/{acc}/'
 filenames=['infotable.xml']
 if f['id']=='adar1':filenames=['xmladar1latest.xml','infotable.xml']
 if f['id']=='perceptive':filenames=['form13fInfoTable.xml','infotable.xml']
 for fn in filenames:
  url=base+fn
  try:
   cached=BASE/'data/raw'/f'{acc}-verified.xml'
   xml=cached.read_text() if cached.exists() else fetch(url);root=ET.fromstring(xml)
   for el in root.iter():el.tag=el.tag.split('}')[-1]
   nodes=root.findall('.//infoTable')
   if not nodes:continue
   ticks={p['cusip']:p['ticker'] for p in r['positions']};positions=[]
   for n in nodes:
    val=lambda k:n.findtext('.//'+k)
    positions.append({'ticker':ticks.get(val('cusip')),'name':val('nameOfIssuer'),'class':val('titleOfClass'),'cusip':val('cusip'),'value':float(val('value')),'shares':float(val('sshPrnamt')),'option':val('putCall')})
   total=sum(p['value'] for p in positions)
   if abs(total-r['reportedTotal'])/max(1,r['reportedTotal'])>.005:raise ValueError('SEC total mismatch')
   (BASE/'data/raw'/f'{acc}-verified.xml').write_text(xml)
   r.update(positions=positions,provenance='SEC information table XML; ticker mapping from 13f.info',xml=url,reportedTotal=total)
   r.pop('primaryFetchNote',None);return f
  except Exception:pass
 return f
def main():
 p=BASE/'data/holdings.json';d=json.loads(p.read_text())
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  d['funds']=list(pool.map(one,d['funds']))
 p.write_text(json.dumps(d,indent=2))
 for f in d['funds']:print(f['name'],f['filings'][0]['provenance'],flush=True)
if __name__=='__main__':main()
