import json,pathlib,subprocess,concurrent.futures,urllib.parse
BASE=pathlib.Path(__file__).resolve().parents[1]
QUERIES=['Baker Bros','OrbiMed Advisors','Redmile','Deerfield Management','Casdin','Avidity','Braidwell','Frazier Life Sciences','Logos Global','TCG Crossover','Samsara','Vivo Capital','Great Point','Rock Springs','PFM Health','Soleus','Octagon Capital Advisors','Opaleye','Affinity Asset','Boxer Capital Management','Fairmount','Vestal Point','Tang Capital','DAFNA','Palo Alto Investors','First Light Asset','First Turn','Parkman','Silverarc','Ikarian','Tri Locum','Commodore','Paradigm Biocapital','Kynam','Bain Capital Life Sciences','Sofinnova Investments','Integral Health','Stempoint','Prosight','Eagle Health','Bioimpact','VR Adviser','SR One Capital','Decheng','Krensavage','Acuta','Sarissa','Camber Capital','Consonance','Stonepine']
def one(q):
 url='https://13f.info/data/autocomplete?q='+urllib.parse.quote(q)
 r=subprocess.run(['curl','--fail','-L','-s','--max-time','25',url],capture_output=True,text=True)
 try:return q,json.loads(r.stdout).get('managers',[])
 except Exception:return q,[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=dict(pool.map(one,QUERIES))
(BASE/'data/universe-discovery.json').write_text(json.dumps(results,indent=2))
for q,items in results.items():print(q,[(x['name'],x['url'],x.get('extra')) for x in items],flush=True)
