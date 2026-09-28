"""Fetch daily price history and displayed statistics for the candidates written by prepare.py."""
import json, pathlib, subprocess, datetime, re, html, math, statistics, concurrent.futures, os, time, random
# MARKET_DELAY seconds (plus jitter) between requests and MARKET_WORKERS threads keep vendor load polite.
DELAY=float(os.environ.get('MARKET_DELAY','0'));WORKERS=int(os.environ.get('MARKET_WORKERS','3'))
BASE=pathlib.Path(__file__).resolve().parents[1]
CACHE=BASE/'data'/'market-raw'
if os.environ.get('FORCE_REFRESH')=='1':CACHE=CACHE/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')
# MARKET_CACHE=20260928-053729 resumes a dated run: cached responses are reused and only failed tickers are downloaded.
if os.environ.get('MARKET_CACHE'):CACHE=BASE/'data'/'market-raw'/os.environ['MARKET_CACHE']
CACHE.mkdir(parents=True,exist_ok=True)
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
def get(url,key):
 p=CACHE/key
 if p.exists():return p.read_text()
 time.sleep(DELAY*(1+random.random()/2))
 args=['curl','--fail','-L','-s','--max-time','30','--retry','3','--retry-connrefused']
 if 'yahoo.com' in url:args+=['-A','Mozilla/5.0']
 r=subprocess.run(args+[url],capture_output=True,text=True)
 if r.returncode:raise RuntimeError(f'HTTP download failed ({r.returncode})')
 p.write_text(r.stdout);return r.stdout
def prices(t):
 data=json.loads(get(f'https://query2.finance.yahoo.com/v8/finance/chart/{t}?range=2y&interval=1d',t+'-prices.json'))
 r=data['chart']['result'][0];q=r['indicators']['quote'][0];adj=r['indicators'].get('adjclose',[{}])[0].get('adjclose',q['close'])
 now=datetime.datetime.now(datetime.timezone.utc);series=[]
 for i,ts in enumerate(r['timestamp']):
  day=datetime.datetime.fromtimestamp(ts,datetime.timezone.utc).date()
  # Omit the current calendar date, which could still be an unfinished US session.
  if day>=now.date() or q['close'][i] is None or not q['volume'][i]:continue
  series.append({'date':day.isoformat(),'close':q['close'][i],'adjusted':adj[i] or q['close'][i],'volume':q['volume'][i],'high':q.get('high',[None]*len(q['close']))[i],'low':q.get('low',[None]*len(q['close']))[i],'open':q.get('open',[None]*len(q['close']))[i]})
 return r['meta'],series
def compute(series):
 c=[r['close'] for r in series];a=[r['adjusted'] for r in series];vol=[r['volume'] for r in series]
 if not c:return {}
 ret=lambda n:(a[-1]/a[-n-1]-1)*100 if len(a)>n else None
 sma=lambda n:sum(c[-n:])/n if len(c)>=n else None
 sma50=sma(50);sma200=sma(200);rsi=None
 if len(c)>14:
  diff=[c[i]-c[i-1] for i in range(1,len(c))];gain=sum(max(0,x) for x in diff[:14])/14;loss=sum(max(0,-x) for x in diff[:14])/14
  for x in diff[14:]:gain=(gain*13+max(0,x))/14;loss=(loss*13+max(0,-x))/14
  rsi=100-100/(1+gain/loss) if loss else (100 if gain else 50)
 logrets=[math.log(a[i]/a[i-1]) for i in range(1,len(a))]
 peak=a[-min(252,len(a))];drawdown=0
 for x in a[-252:]:peak=max(peak,x);drawdown=min(drawdown,(x/peak-1)*100)
 trend='Insufficient history'
 if sma50 and sma200:trend='Above 50D & 200D' if c[-1]>sma50>sma200 else 'Below 200D' if c[-1]<sma200 else 'Mixed trend'
 def ema(values,n):
  out=[values[0]];alpha=2/(n+1)
  for x in values[1:]:out.append(alpha*x+(1-alpha)*out[-1])
  return out
 extras={}
 if len(c)>=35:
  macd=[x-y for x,y in zip(ema(c,12),ema(c,26))];sig=ema(macd,9)
  extras.update(macd=macd[-1],macdSignal=sig[-1],macdHistogram=macd[-1]-sig[-1],macdCross='Bullish crossover' if macd[-1]>sig[-1] and macd[-2]<=sig[-2] else 'Bearish crossover' if macd[-1]<sig[-1] and macd[-2]>=sig[-2] else 'Above signal' if macd[-1]>sig[-1] else 'Below signal')
 if len(c)>=20:
  mid=statistics.mean(c[-20:]);sd=statistics.pstdev(c[-20:]);upper=mid+2*sd;lower=mid-2*sd
  extras.update(bbUpper=upper,bbLower=lower,bbMid=mid,bbWidth=(upper-lower)/mid*100,bbPercentB=(c[-1]-lower)/(upper-lower)*100 if upper>lower else 50,sma20=mid)
 if len(c)>=15 and all(p['high'] is not None and p['low'] is not None for p in series[1:]):
  tr=[max(p['high']-p['low'],abs(p['high']-c[i-1]),abs(p['low']-c[i-1])) for i,p in enumerate(series) if i]
  atr=statistics.mean(tr[:14])
  for x in tr[14:]:atr=(atr*13+x)/14
  extras.update(atr14=atr,atrPercent=atr/c[-1]*100)
 extras['distance50']=(c[-1]/sma50-1)*100 if sma50 else None
 extras['fromLow']=(c[-1]/min(c[-252:])-1)*100 if len(c)>=252 else None
 extras['sma50Slope5']=(sma50/statistics.mean(c[-55:-5])-1)*100 if len(c)>=55 else None
 extras['smaCross']='Insufficient history'
 if len(c)>=201:
  prior50=statistics.mean(c[-51:-1]);prior200=statistics.mean(c[-201:-1])
  extras['smaCross']='Golden cross' if sma50>sma200 and prior50<=prior200 else 'Death cross' if sma50<sma200 and prior50>=prior200 else '50D above 200D' if sma50>sma200 else '50D below 200D'
 if len(c)>=21:extras['obvChange20']=sum(vol[i] if c[i]>c[i-1] else -vol[i] if c[i]<c[i-1] else 0 for i in range(len(c)-20,len(c)))
 return {'date':series[-1]['date'],'close':c[-1],'sma50':sma50,'sma200':sma200,'distance200':(c[-1]/sma200-1)*100 if sma200 else None,'rsi':rsi,'rvol':vol[-1]/statistics.mean(vol[-21:-1]) if len(vol)>20 else None,'return1m':ret(21),'return3m':ret(63),'return6m':ret(126),'return12m':ret(252),'advDollar':statistics.mean(p['close']*p['volume'] for p in series[-20:]) if len(series)>=20 else None,'volatility':statistics.stdev(logrets[-63:])*math.sqrt(252)*100 if len(logrets)>=63 else None,'maxDrawdown':drawdown if len(a)>=252 else None,'fromHigh':(c[-1]/max(c[-252:])-1)*100 if len(c)>=252 else None,'trend':trend,'series':[{'date':p['date'],'close':round(p['close'],4)} for p in series[-252:]],**extras}
def one(t):
 o={'retrieved':NOW,'priceSource':f'https://finance.yahoo.com/quote/{t}/history/'}
 try:meta,series=prices(t);o['technical']=compute(series);o['name']=meta.get('longName') or meta.get('shortName');o['exchange']=meta.get('exchangeName')
 except Exception as e:o['priceError']=str(e)
 if t not in ['XBI','XLV']:
  url=f'https://stockanalysis.com/stocks/{t.lower()}/statistics/'
  try:
   page=get(url,t+'-stats.html');stats={}
   for row in re.findall(r'<tr[^>]*>(.*?)</tr>',page,re.S):
    cells=[re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',c))).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)]
    if len(cells)>=2:stats[cells[0]]=cells[1]
   o['statistics']=stats;o['statisticsSource']=url;o['statisticsObservationDate']=None
  except Exception as e:o['statisticsError']=str(e)
 return t,o
def main():
 candidates=json.loads((BASE/'data/candidates.json').read_text());tickers=sorted({p['ticker'] for p in candidates if p['ticker']}|{'XBI','XLV'})
 previous=json.loads((BASE/'data/market.json').read_text()) if (BASE/'data/market.json').exists() else {}
 result={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
  for t,o in pool.map(one,tickers):
   # A failed download keeps the last good observation, labeled with the failure, instead of erasing it.
   old=previous.get(t,{})
   if not o.get('technical') and old.get('technical'):o={**o,'technical':old['technical'],'priceSource':old.get('priceSource',o['priceSource']),'carriedForward':True}
   if not o.get('statistics') and old.get('statistics'):o={**o,'statistics':old['statistics'],'statisticsSource':old.get('statisticsSource'),'statisticsRetrieved':old.get('statisticsRetrieved',old.get('retrieved')),'carriedForward':True}
   result[t]=o;print(t, o.get('technical',{}).get('date','no prices'),len(o.get('statistics',{})),'carried forward' if o.get('carriedForward') else '',flush=True)
   (BASE/'data/market.partial.json').write_text(json.dumps(result))
 for t,o in result.items():
  for benchmark in ['XBI','XLV']:
   a=o.get('technical',{});b=result.get(benchmark,{}).get('technical',{})
   for n in ['1m','3m','6m','12m']:
    a['relative'+benchmark+n]=a['return'+n]-b['return'+n] if a.get('return'+n) is not None and b.get('return'+n) is not None and a.get('date')==b.get('date') else None
 (BASE/'data/market.json').write_text(json.dumps(result,indent=2))
 (BASE/'data/market.partial.json').unlink(missing_ok=True)
 print('Market snapshot complete',len(result),flush=True)
if __name__=='__main__':main()
