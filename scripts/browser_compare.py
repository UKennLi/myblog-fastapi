import json,re,urllib.request,urllib.error,hashlib,os
from io import BytesIO
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image,ImageChops
OUT=Path('reports/visual'); OUT.mkdir(parents=True,exist_ok=True)
cache={}; external=[]
WIDTH=int(os.getenv('VISUAL_WIDTH','1440')); HEIGHT=int(os.getenv('VISUAL_HEIGHT','900')); PREFIX=os.getenv('VISUAL_PREFIX','desktop')
def remote(route):
 url=route.request.url
 if url.startswith(('http://127.0.0.1:8081/','http://127.0.0.1:8082/')):
  if url.split('?')[0].lower().endswith('.gif'):
   response=route.fetch()
   if response.status==200:
    try:
     im=Image.open(BytesIO(response.body())); im.seek(0); frozen=BytesIO(); im.convert('RGBA').save(frozen,format='PNG')
     route.fulfill(response=response,content_type='image/png',body=frozen.getvalue()); return
    except Exception: pass
  route.continue_(); return
 if url not in cache:
  try:
   with urllib.request.urlopen(url,timeout=5) as r: cache[url]=(r.status,dict(r.headers),r.read())
   try:
    im=Image.open(BytesIO(cache[url][2]))
    if getattr(im,'is_animated',False):
     frozen=BytesIO(); im.seek(0); im.convert('RGBA').save(frozen,format='PNG')
     cache[url]=(cache[url][0],{'Content-Type':'image/png'},frozen.getvalue())
   except Exception: pass
   external.append({'url':url,'status':cache[url][0]})
  except Exception as e:
   cache[url]=(404,{},b''); external.append({'url':url,'status':'unavailable','reason':type(e).__name__})
 status,headers,body=cache[url]
 route.fulfill(status=status,content_type=headers.get('Content-Type','application/octet-stream'),body=body)

def normalized(page):
 return page.evaluate('''() => {
 const visit = n => {
  if(n.nodeType===3) { const t=n.textContent.replace(/\\s+/g,' ').trim(); return t || null; }
  if(n.nodeType!==1) return null;
  if(n.tagName==='SCRIPT') return null;
  const attrs=[...n.attributes].filter(a=>a.name!=='xmlns:th').map(a=>[a.name, a.name==='value' && n.getAttribute('name')==='_csrf' ? 'TOKEN' : a.name==='class' ? a.value.trim().split(/\\s+/).join(' ') : ['selected','required','readonly','autofocus'].includes(a.name) ? '' : a.value]).sort((a,b)=>a[0].localeCompare(b[0]));
  return [n.tagName, attrs, [...n.childNodes].map(visit).filter(x=>x!==null)];
 };return visit(document.documentElement);
}''')
def difference(a,b,path=''):
 if type(a)!=type(b): return [path,str(a)[:150],str(b)[:150]]
 if isinstance(a,list):
  if len(a)!=len(b): return [path+'/length',len(a),len(b)]
  for i,(x,y) in enumerate(zip(a,b)):
   if x!=y: return difference(x,y,path+'/'+str(i))
 elif a!=b: return [path,str(a)[:180],str(b)[:180]]
 return None
routes=['/','/post/hello-world','/about','/archive','/links','/post/nonexistent','/category/default','/search?keyword=Spring','/admin','/admin/posts','/admin/drafts','/admin/comments','/admin/links','/admin/posts/new','/admin/posts/edit/2','/admin/links/new','/admin/links/edit/1','/admin/about','/admin/options','/admin/profile','/login','/login?error','/logout']
routes=json.loads(os.environ['VISUAL_ROUTES']) if 'VISUAL_ROUTES' in os.environ else routes
results=[]
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
 original=browser.new_context(viewport={'width':WIDTH,'height':HEIGHT},timezone_id='UTC')
 extracted=browser.new_context(viewport={'width':WIDTH,'height':HEIGHT},timezone_id='UTC')
 for context in [original,extracted]: context.route('**/*',remote)
 old=original.new_page(); new=extracted.new_page()
 old.goto('http://127.0.0.1:8081/login'); old.locator('#username').fill(os.getenv('TEST_ADMIN_USERNAME','riuken')); old.locator('#password').fill(os.getenv('TEST_ADMIN_PASSWORD','123456')); old.locator('button[type=submit]').click(); old.wait_for_url('**/admin')
 new.goto('http://127.0.0.1:8082/login'); new.locator('#username').fill(os.getenv('TEST_ADMIN_USERNAME','riuken')); new.locator('#password').fill(os.getenv('TEST_ADMIN_PASSWORD','123456')); new.locator('button[type=submit]').click(); new.wait_for_url('**/admin')
 dom_original=browser.new_context(viewport={'width':WIDTH,'height':HEIGHT},java_script_enabled=False,storage_state=original.storage_state())
 dom_extracted=browser.new_context(viewport={'width':WIDTH,'height':HEIGHT},java_script_enabled=False,storage_state=extracted.storage_state())
 for context in [dom_original,dom_extracted]: context.route('**/*',remote)
 dom_old=dom_original.new_page(); dom_new=dom_extracted.new_page()
 for index,path in enumerate(routes):
  old.goto('http://127.0.0.1:8081'+path,wait_until='networkidle')
  new.goto('http://127.0.0.1:8082'+path,wait_until='networkidle')
  old.wait_for_timeout(150); new.wait_for_timeout(150)
  dom_old.goto('http://127.0.0.1:8081'+path,wait_until='networkidle')
  dom_new.goto('http://127.0.0.1:8082'+path,wait_until='networkidle')
  diff=difference(normalized(dom_old),normalized(dom_new))
  result={'route':path,'dom_match':diff is None,'difference':diff}
  if True:
   name=PREFIX+'-'+(re.sub(r'[^a-z0-9]+','-',path).strip('-') or 'home')
   files=[]
   for label,page in [('original',old),('extracted',new)]:
    output=OUT/(name+'-'+label+'.png'); page.screenshot(path=str(output),full_page=True,animations='disabled',caret='hide'); files.append(output)
   a,b=map(Image.open,files)
   result['screenshot_size_match']=a.size==b.size
   if a.size==b.size:
    delta=ImageChops.difference(a.convert('RGB'),b.convert('RGB'))
    result['different_pixels']=sum(1 for px in delta.get_flattened_data() if px!=(0,0,0))
    result['total_pixels']=a.width*a.height
  results.append(result)
  print(path,'MATCH' if not diff else diff,flush=True)
 browser.close()
(OUT/(PREFIX+'-comparison.json')).write_text(json.dumps({'viewport':[WIDTH,HEIGHT],'pages':results,'external_resources':external},ensure_ascii=False,indent=2)+'\n')
