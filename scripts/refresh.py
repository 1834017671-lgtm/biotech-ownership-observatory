"""Refresh public data and rebuild the local dashboard. Publication is a separate step."""
import pathlib,datetime,shutil,subprocess,sys,os,json
BASE=pathlib.Path(__file__).resolve().parents[1]
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')
archive=BASE/'data'/'snapshots'/stamp;archive.mkdir(parents=True,exist_ok=True)
for file in ['holdings.json','market.json','holders.json']:
 p=BASE/'data'/file
 if p.exists():shutil.copy2(p,archive/file)
env=dict(os.environ,FORCE_REFRESH='1')
try:
 for script in ['collect.py','verify_primary.py','prepare.py','market.py','holders.py','prepare.py']:
  subprocess.run([sys.executable,str(BASE/'scripts'/script)],cwd=BASE,env=env,check=True)
  if script=='collect.py':
   d=json.loads((BASE/'data/holdings.json').read_text())
   expected=len(json.loads((BASE/'data/universe.json').read_text())) if (BASE/'data/universe.json').exists() else 50
   if len(d['funds'])!=expected or any(not f['filings'] for f in d['funds']):raise RuntimeError('Incomplete fund coverage; previous data retained')
 print('Local snapshot updated. Publish the Site to update the hosted dashboard.')
except Exception:
 for file in ['holdings.json','market.json','holders.json']:
  if (archive/file).exists():shutil.copy2(archive/file,BASE/'data'/file)
 subprocess.run([sys.executable,str(BASE/'scripts/prepare.py')],cwd=BASE,check=True)
 raise
