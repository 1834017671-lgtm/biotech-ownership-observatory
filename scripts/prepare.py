"""Normalize common equity and produce the browser snapshot; no inferred shorts."""
import json,pathlib,re,collections,datetime,os,hashlib
BASE=pathlib.Path(__file__).resolve().parents[1]
# Positions per fund that receive market and holder data; the dashboard offers cutoffs up to 50.
CANDIDATE_DEPTH=int(os.environ.get('CANDIDATE_DEPTH','50'))
MAPPINGS={'SPYRE THERAPEUTICS':'SYRE','XENON PHARMACEUTICALS':'XENE','ANAPTYSBIO':'ANAB','REVOLUTION MEDICINES':'RVMD','ABIVAX':'ABVX','AKTIS ONCOLOGY':'AKTS','PARABILIS MEDICINES':'PBLS','ASCENDIS PHARMA':'ASND','ROIVANT SCIENCES':'ROIV','VERADERMICS':'MANUAL','HEMAB THERAPEUTICS':'MANUAL'}
ADJACENT={'BKD','NVCR','BBNX','CAI','HNGE','NEO','CAH','AVR','WGS','BLFS','LAB','HTFL','SIBN','AXGN','MASS','MOBI','JNJ','GH','NTRA','EXAS','ILMN','DHR','TMO','INSP','GMED','ESTA','MASI','DXCM','PODD','ISRG','BSX','MDT','ALGN','EW','ABT','ZBH','SYK','RMD','OSUR','QDEL','TXG','PACB','SLGC','BFLY','SDGR','TEM','UNH','HUM','CVS','CI','ELV','CNC','MOH','HCA','UHS','THC','DVA','FMS','LH','DGX','IQV','MEDP','CRL','WST','WAT','A','BIO','BDX','BAX','GEHC','HOLX','COO','TFX','ICUI','IRTC','NVST','ALHC','OSCR','PRCT','GKOS','ENSG','PACS','VTRS','BTSG','CHE','DOCS','VEEV','OMCL','HIMS','SUPN','ACHC','ADUS','AHCO','PGNY','SEM','RGEN','ICLR','XRAY','ZTS','ELAN','IDXX'}
def equity(p):
 n=p['name'].upper();c=p['class'].upper()
 return not p['option'] and not any(x in c for x in ['WARRANT','W EXP','*W','NOTE','PUT','CALL','UNIT','PFD','PREFERRED']) and not any(x in n for x in ['SPDR','ISHARES','ETF','INVESCO','ALPHA ARCHITECT','VANGUARD','TREASURY','SERIES TRUST','ACQUISITION CORP','CAPITAL SOLUTIONS'])
def mapped(p):
 t=p['ticker'];note=None
 for name,tk in MAPPINGS.items():
  if name in p['name'].upper() and tk!='MANUAL':
   if t!=tk:note=f'Issuer-name correction: provider ticker {t or "unmapped"} → {tk}; original CUSIP retained.'
   t=tk;break
 if not t or '.' in t: return None,'Ticker requires review; position retained by CUSIP.'
 return t,note
def prepare():
 d=json.loads((BASE/'data/holdings.json').read_text());funds=[]
 areas_src=json.loads((BASE/'data/therapeutic-areas.json').read_text()) if (BASE/'data/therapeutic-areas.json').exists() else {'areas':[],'tickers':{},'nameContains':{},'note':''}
 tick_map={k.upper():v for k,v in areas_src.get('tickers',{}).items()};name_map=areas_src.get('nameContains',{})
 def area_of(ticker,name):
  if ticker and ticker.upper() in tick_map:return tick_map[ticker.upper()]
  up=(name or '').upper()
  for frag,aid in name_map.items():
   if frag in up:return aid
  return 'unclassified'
 for f in d['funds']:
  histories=[]
  for r in f['filings']:
   merged={};equity_total=sum(p['value'] for p in r['positions'] if equity(p))
   for p in r['positions']:
    if not equity(p):continue
    t,note=mapped(p);key=t or p['cusip']
    bio=any(w in p['name'].upper() for w in ['PHARMA','THERAPEUT','BIOSCIEN','BIOTECH','BIOLOG','ONCOLOGY','MEDICINES','BIOPHARM','IMMUNO','GENETIC']) or t in {'KOD','CYTK','GMAB','BLTE','ABVX','TSHA','GHRS','SVRA','NGNE','BIOA','PHVS','CABA','ANRO','DBVT','SRRK','ABSI','ANNX','RGNX','STTK','QURE','REPL','QTTB','IVA','HROW','IRON','MGTX','SLGL','RZLT','NUVB','UPB','EQ','BYSI','CMPS','INCY','ONC','BEIGENE','BPMC','AXSM','FOLD','HALO','NBIX','IONS','UTHR','VRTX','AMGN','BMRN','ACAD','ALNY','ARWR','BCRX','LGND','VCEL','ITCI','CORT','INSM','INVA','PCRX','RPRX','SGRY','ELAN','ZTS','SWTX','AKRO','AKBA','SGMO','IOVA','PTLA','SRPT','KPTI','RARE','BLUE','EDIT','NTLA','BEAM','DNLI','FULC','PRTA','PRAX','SEPN','LQDA','ASND','ARGX','ZYME','ANAB','PCVX','CELC','XOMA','EXEL','CRNX','CRSP','ALKS','NAMS','VIR','ROIV','ERAS','XNCR','NUVL','NKTR','AKTS','KARD','SNDX','AGIO','ZLAB','EYPT','TRAX','ALMS','COAG','MANE','SAGE','MRNA','BNTX','GILD','REGN','BIIB','ABBV','LLY','PFE','BMY','MRK','NVO','AZN','NVS','SNY'}
    if key not in merged:merged[key]={'key':key,'ticker':t,'name':p['name'].title(),'value':0,'shares':0,'cusips':[],'mappingNote':note,'category':'Adjacent healthcare' if t in ADJACENT else 'Biotech / biopharma' if bio else 'Unclassified equity','therapeuticArea':area_of(t,p['name'])}
    a=merged[key];a['value']+=p['value'];a['shares']+=(p['shares'] or 0);a['cusips'].append(p['cusip'])
   positions=sorted(merged.values(),key=lambda p:-p['value'])
   for i,p in enumerate(positions):p.update(rank=i+1,weight=p['value']/r['reportedTotal']*100,equityWeight=p['value']/equity_total*100 if equity_total else None)
   histories.append({**{k:v for k,v in r.items() if k!='positions'},'positions':positions,'equityTotal':equity_total,'excludedValue':r['reportedTotal']-equity_total})
  funds.append({**f,'filings':histories})
 market=json.loads((BASE/'data/market.json').read_text()) if (BASE/'data/market.json').exists() else {}
 owners=json.loads((BASE/'data/holders.json').read_text()) if (BASE/'data/holders.json').exists() else {}
 selection=json.loads((BASE/'data/universe-selection.json').read_text()) if (BASE/'data/universe-selection.json').exists() else None
 # Rebuild equal-weight healthcare proxy baskets from the latest daily series before packaging the snapshot.
 try:
  import importlib.util
  spec=importlib.util.spec_from_file_location('proxies',BASE/'scripts'/'proxies.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.build()
 except Exception as e:print('proxy build skipped:',e)
 proxies=json.loads((BASE/'data/proxies.json').read_text()) if (BASE/'data/proxies.json').exists() else None
 log=json.loads((BASE/'data/refresh-log.json').read_text()) if (BASE/'data/refresh-log.json').exists() else []
 built=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
 # Hash UI assets so open tabs can full-reload when app.js or style.css changes, not only when holdings data changes.
 def asset(name):
  p=BASE/'dist'/name
  return hashlib.sha1(p.read_bytes()).hexdigest()[:12] if p.exists() else None
 appHash=asset('app.js');styleHash=asset('style.css')
 payload={'retrieved':d['retrieved'],'built':built,'build':built,'app':appHash,'style':styleHash,'funds':funds,'market':market,'owners':owners,'selection':selection,'therapeuticAreas':{'note':areas_src.get('note'),'areas':areas_src.get('areas',[])},'proxies':proxies,'errors':d['errors'],'refreshLog':log[-30:],'expectedFunds':len(funds),'version':2}
 # The browser polls version.json every second, so it is written last and every file is replaced atomically.
 def write(name,text):
  tmp=BASE/'dist'/(name+'.tmp');tmp.write_text(text);os.replace(tmp,BASE/'dist'/name)
 write('data.js','window.DASHBOARD_DATA='+json.dumps(payload,separators=(',',':'))+';\n')
 write('snapshot.json',json.dumps(payload))
 write('version.json',json.dumps({'version':built,'built':built,'app':appHash,'style':styleHash,'holdingsPeriod':max((f['filings'][0]['period'] for f in funds if f['filings']),default=None),'pricesThrough':max((m.get('technical',{}).get('date') or '' for m in market.values()),default='') or None}))
 candidates={p['key']:p for f in funds if f['filings'] for p in f['filings'][0]['positions'][:CANDIDATE_DEPTH]}
 (BASE/'data/candidates.json').write_text(json.dumps(list(candidates.values()),indent=2))
 print(f'{len(funds)} funds; {len(candidates)} top-{CANDIDATE_DEPTH} candidates')
if __name__=='__main__':prepare()
