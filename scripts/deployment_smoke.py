"""Exercise the deployed image against an explicitly disposable database only."""
import argparse,os,json,re,io,zipfile,subprocess,time,shutil
from pathlib import Path
import httpx,pymysql
from PIL import Image
from dotenv import load_dotenv


def main():
 p=argparse.ArgumentParser();p.add_argument('--env-file',required=True);p.add_argument('--uuid',required=True);p.add_argument('--disposable',action='store_true',required=True);p.add_argument('--base',default='http://127.0.0.1:8000');p.add_argument('--container',default='myblog-fastapi-validation-blog-1');a=p.parse_args();load_dotenv(a.env_file,override=True)
 db=pymysql.connect(host=os.environ['DB_HOST'],port=int(os.environ['DB_PORT']),user=os.environ['DB_USER'],password=os.environ['DB_PASSWORD'],database=os.environ.get('DB_NAME','myblog_db'),autocommit=True)
 with db.cursor() as c:
  c.execute('SELECT @@server_uuid');assert c.fetchone()[0]==a.uuid
  c.execute("SELECT COUNT(*) FROM t_post WHERE slug='deployment-smoke'");assert c.fetchone()[0]==0,'Refusing existing smoke article'
  c.execute("SELECT COUNT(*) FROM t_tag WHERE name='Docker验收'");assert c.fetchone()[0]==0,'Refusing existing smoke tag'
 checks=[];completed=False;id=None;uploaded=None
 def check(name,value):checks.append(dict(name=name,passed=bool(value)));assert value,name
 with httpx.Client(base_url=a.base,timeout=20,follow_redirects=False) as client:
  def csrf(path):return re.search(r'name="_csrf"[^>]*value="([^"]+)"',client.get(path).text)[1]
  try:
   for path in ['/','/about','/archive','/links','/post/hello-world','/login','/butterfly/css/index.css']:
    check('GET '+path,client.get(path).status_code==200)
   check('anonymous admin login redirect',client.get('/admin/posts').status_code==302)
   r=client.post('/login',data={'username':os.environ.get('TEST_ADMIN_USERNAME','riuken'),'password':os.environ.get('TEST_ADMIN_PASSWORD','123456'),'_csrf':csrf('/login')});check('existing BCrypt login',r.status_code==302 and r.headers['location'].endswith('/admin'))
   image=io.BytesIO();Image.new('RGB',(12,12),'blue').save(image,format='PNG')
   r=client.post('/admin/api/upload',files={'editormd-image-file':('deployment.png',image.getvalue(),'image/png')});uploaded=r.json().get('url');check('real multipart image write',r.status_code==200 and r.json()['success']==1)
   check('persisted image access',client.get(uploaded).content==image.getvalue())
   content='# 独立Docker部署\n\n![图片]('+uploaded+')\n'
   r=client.post('/admin/posts/save',data=dict(title='独立Docker验收',slug='deployment-smoke',content=content,categoryId=1,tagsStr='Docker验收',_csrf=csrf('/admin/profile')));check('database article+tag write',r.status_code==302)
   with db.cursor() as c:c.execute("SELECT id FROM t_post WHERE slug='deployment-smoke'");id=c.fetchone()[0]
   check('render saved article', '<h1>独立Docker部署</h1>' in client.get('/post/deployment-smoke').text)
   r=client.get('/admin/posts/download/'+str(id));check('ZIP response',r.status_code==200 and r.headers['content-type']=='application/zip')
   with zipfile.ZipFile(io.BytesIO(r.content)) as archive:check('ZIP real uploaded image',archive.read('images/'+uploaded.rsplit('/',1)[1])==image.getvalue())
   subprocess.run(['docker','restart',a.container],capture_output=True,check=True)
   for attempt in range(40):
    try:
     if client.get('/').status_code==200:break
    except httpx.HTTPError:pass
    time.sleep(.25)
   check('restart invalidates session like original Java',client.get('/admin/posts').status_code==302)
   check('persistent uploads after restart',client.get(uploaded).content==image.getvalue())
   r=client.post('/login',data={'username':os.environ.get('TEST_ADMIN_USERNAME','riuken'),'password':os.environ.get('TEST_ADMIN_PASSWORD','123456'),'_csrf':csrf('/login')})
   check('relogin after restart',r.status_code==302 and client.get('/admin/posts').status_code==200)
   r=client.post('/logout',data={'_csrf':csrf('/logout')});check('logout and revocation',r.status_code==302 and client.get('/admin/posts').status_code==302)
   evidence=json.loads(subprocess.run(['docker','exec',a.container,'python','-c',"import json,shutil,pathlib;print(json.dumps({'java':shutil.which('java'),'original_repository':pathlib.Path('/workspace/MyBlog-butterfly').exists()}))"],capture_output=True,text=True,check=True).stdout)
   check('image has no Java or original checkout',evidence==dict(java=None,original_repository=False))
   completed=True
  finally:
   with db.cursor() as c:
    if id is not None:
     c.execute('DELETE FROM t_post_tag WHERE post_id=%s',(id,));c.execute('DELETE FROM t_post WHERE id=%s',(id,))
    c.execute("DELETE FROM t_tag WHERE name='Docker验收'")
   if uploaded:
    path=Path('uploads')/uploaded.rsplit('/',1)[1]
    if path.is_file():path.unlink()
   db.close()
   Path('reports/deployment.json').write_text(json.dumps(dict(passed=completed and all(c['passed'] for c in checks),checks=checks,scope='Nonroot Docker Compose image, only isolated MySQL, persistent uploads mount and session file volume; sessions invalidated on application restart to match Java, original Java baseline stopped before smoke test, original checkout absent from image; smoke records/files cleaned.'),ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
