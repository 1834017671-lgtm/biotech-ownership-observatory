"""Build equal-weight healthcare subsector proxy stats from market.json daily series."""
import json, pathlib, datetime, math, statistics
BASE=pathlib.Path(__file__).resolve().parents[1]
def ret(series, n):
 """Total return over n completed sessions using adjusted-like closes in series."""
 if not series or len(series)<=n:return None
 a,b=series[-1]['close'],series[-1-n]['close']
 return None if not a or not b else (a/b-1)*100
def ytd(series):
 if not series:return None
 year=series[-1]['date'][:4]
 base=next((p for p in series if p['date'][:4]==year),None)
 if not base or not base['close'] or not series[-1]['close']:return None
 return (series[-1]['close']/base['close']-1)*100
def member_stats(t, market):
 m=market.get(t) or {};tech=m.get('technical') or {};series=tech.get('series') or []
 st=m.get('statistics') or {}
 # Prefer full series returns; fall back to precomputed technical fields.
 out={
  'ticker':t,'date':tech.get('date'),'close':tech.get('close'),
  'return1d':ret(series,1),'return5d':ret(series,5),'return1m':tech.get('return1m') if tech.get('return1m') is not None else ret(series,21),
  'return3m':tech.get('return3m') if tech.get('return3m') is not None else ret(series,63),
  'returnYtd':ytd(series),'fromHigh':tech.get('fromHigh'),'advDollar':tech.get('advDollar'),
  'marketCap':st.get('Market Cap') or st.get('Market Cap ') or None,
  'priceError':m.get('priceError'),'available':bool(tech.get('date') and series)
 }
 return out
def mean(vals):
 vals=[v for v in vals if v is not None and not (isinstance(v,float) and math.isnan(v))]
 return statistics.mean(vals) if vals else None
def build():
 spec=json.loads((BASE/'data/healthcare-proxies.json').read_text())
 market=json.loads((BASE/'data/market.json').read_text()) if (BASE/'data/market.json').exists() else {}
 baskets=[]; all_ticks=set()
 for b in spec['baskets']:
  members=[]; 
  for c in b['constituents']:
   s=member_stats(c['ticker'],market);s.update(name=c['name'],rationale=c['rationale']);members.append(s);all_ticks.add(c['ticker'])
  avail=[m for m in members if m['available']]
  def basket_ret(key):return mean([m[key] for m in avail])
  winners=sorted([m for m in avail if m['return1d'] is not None],key=lambda m:m['return1d'],reverse=True)
  stats={
   'id':b['id'],'label':b['label'],'group':b['group'],'definition':b['definition'],'rules':b['rules'],
   'constituentCount':len(members),'availableCount':len(avail),
   'missing':[m['ticker'] for m in members if not m['available']],
   'priceDate':max((m['date'] for m in avail if m['date']),default=None),
   'return1d':basket_ret('return1d'),'return5d':basket_ret('return5d'),'return1m':basket_ret('return1m'),
   'return3m':basket_ret('return3m'),'returnYtd':basket_ret('returnYtd'),'fromHigh':basket_ret('fromHigh'),
   'breadth1d':None if not avail else sum(1 for m in avail if (m['return1d'] or 0)>0)/len([m for m in avail if m['return1d'] is not None]) if any(m['return1d'] is not None for m in avail) else None,
   'topWinners':[{'ticker':m['ticker'],'return1d':m['return1d']} for m in winners[:3]],
   'topLosers':[{'ticker':m['ticker'],'return1d':m['return1d']} for m in sorted(winners,key=lambda m:m['return1d'])[:3]],
   'members':members
  }
  baskets.append(stats)
 # Relative return matrix (row minus column) for rotation reads.
 ids=[b['id'] for b in baskets]; matrix={}
 for window in ['return1d','return1m','return3m','returnYtd']:
  matrix[window]={a['id']:{b['id']:(None if a[window] is None or b[window] is None else a[window]-b[window]) for b in baskets} for a in baskets}
 out={
  'built':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
  'methodology':{k:spec[k] for k in ['version','asOfNote','weighting','rebalance','currency','limitations'] if k in spec},
  'baskets':baskets,'relative':matrix,'tickers':sorted(all_ticks)
 }
 (BASE/'data/proxies.json').write_text(json.dumps(out,indent=2))
 print(json.dumps({b['id']:{'n':b['availableCount'],'missing':b['missing'],'d1':b['return1d'],'m1':b['return1m']} for b in baskets}))
 return out
if __name__=='__main__':build()
