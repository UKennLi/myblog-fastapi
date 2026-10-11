"""Read-only localhost comparison. No production URLs or saved login state."""
import argparse,json,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--before',default='http://127.0.0.1:8081');p.add_argument('--after',default='http://127.0.0.1:8082');p.add_argument('--routes',nargs='+',default=['/','/post/hello-world','/about','/archive','/search?keyword=Spring']);p.add_argument('--output',default='reports/optimization/p0-visual');a=p.parse_args()
from urllib.parse import urlsplit
assert all(urlsplit(u).hostname in ('127.0.0.1','localhost') for u in (a.before,a.after))
out=Path(a.output);out.mkdir(parents=True,exist_ok=True);cache={};external=[];results=[]
def remote(route):
 url=route.request.url
 if any(url.startswith(base+'/') for base in (a.before,a.after)):route.continue_();return
 if url not in cache:
  try:
   with urllib.request.urlopen(url,timeout=3) as r:cache[url]=(r.status,r.headers.get('Content-Type','application/octet-stream'),r.read())
  except Exception as e:cache[url]=(404,'text/plain',b'');external.append({'url':url,'error':type(e).__name__})
 route.fulfill(status=cache[url][0],content_type=cache[url][1],body=cache[url][2])
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for width,height in [(390,844),(768,1024),(1366,768),(1920,1080)]:
  for label,base in [('before',a.before),('after',a.after)]:
   context=browser.new_context(viewport={'width':width,'height':height});context.route('**/*',remote)
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.add_init_script("window.vitals={};new PerformanceObserver(l=>{window.vitals.lcp=l.getEntries().at(-1).startTime}).observe({type:'largest-contentful-paint',buffered:true});new PerformanceObserver(l=>{window.vitals.cls=(window.vitals.cls||0)+l.getEntries().filter(e=>!e.hadRecentInput).reduce((s,e)=>s+e.value,0)}).observe({type:'layout-shift',buffered:true});")
   for path in a.routes:
    errors.clear();response=page.goto(base+path,wait_until='networkidle');page.wait_for_timeout(100)
    name=f'{width}-{label}-'+('home' if path=='/' else path.strip('/').replace('/','-').replace('?','-').replace('=','-'))
    page.screenshot(path=str(out/(name+'.png')),full_page=True,animations='disabled')
    metrics=page.evaluate('''() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('body *')].filter(e=>{let r=e.getBoundingClientRect();return r.width&& (r.right>innerWidth+1||r.left < -1)}).map(e=>({tag:e.tagName,id:e.id,cls:e.className,left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right})).slice(0,30),vitals:window.vitals,resources:performance.getEntriesByType('resource').map(e=>({url:e.name,duration:e.duration,bytes:e.transferSize}))})''')
    results.append({'label':label,'viewport':[width,height],'route':path,'status':response.status,'errors':list(errors),**metrics})
   context.close()
 browser.close()
(out/'results.json').write_text(json.dumps({'pages':results,'external_failures':external},ensure_ascii=False,indent=2))
print(json.dumps([{'label':x['label'],'width':x['width'],'route':x['route'],'scrollWidth':x['scrollWidth'],'overflow':x['overflow'][:3]} for x in results if x['route']=='/'],ensure_ascii=False))
