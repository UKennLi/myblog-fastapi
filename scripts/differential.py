"""Compare live old/new behavior on two explicitly disposable databases only."""
import argparse,json,re,os,hashlib
from pathlib import Path
from urllib.parse import urlsplit
import httpx,pymysql
from dotenv import load_dotenv

NAMES=['t_post_tag','t_comment','t_post','t_tag','t_category','t_link','t_option','t_user']
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--old',default='http://127.0.0.1:8081')
 parser.add_argument('--new',default='http://127.0.0.1:8082')
 parser.add_argument('--old-port',type=int,default=3307)
 parser.add_argument('--new-port',type=int,default=3308)
 parser.add_argument('--env-file',required=True)
 parser.add_argument('--old-uuid',required=True)
 parser.add_argument('--new-uuid',required=True)
 parser.add_argument('--disposable',action='store_true',required=True)
 args=parser.parse_args(); load_dotenv(args.env_file,override=True)
 conns=[pymysql.connect(host=os.environ['DB_HOST'],port=p,user=os.environ['DB_USER'],password=os.environ['DB_PASSWORD'],database=os.environ.get('DB_NAME','myblog_db'),cursorclass=pymysql.cursors.DictCursor,autocommit=True) for p in (args.old_port,args.new_port)]
 def rows(i,sql,values=()):
  with conns[i].cursor() as c: c.execute(sql,values); return c.fetchall()
 for i,expected in enumerate([args.old_uuid,args.new_uuid]):
  assert rows(i,'SELECT @@server_uuid AS uuid')[0]['uuid']==expected,'Refusing non-disposable database'
 snapshots=[{n:rows(i,'SELECT * FROM '+n) for n in NAMES} for i in range(2)]
 schemas=[{n:re.sub(r'AUTO_INCREMENT=\d+','AUTO_INCREMENT=COUNTER',rows(i,'SHOW CREATE TABLE '+n)[0]['Create Table']) for n in NAMES} for i in range(2)]
 clients=[httpx.Client(base_url=b,timeout=20,follow_redirects=False) for b in (args.old,args.new)]
 checks=[]; completed=False
 def check(name,a,b): checks.append(dict(name=name,match=a==b,old=a,new=b)); assert a==b,(name,a,b)
 def response(r):
  return dict(status=r.status_code,location=re.sub(r'^https?://[^/]+','',r.headers.get('location','')))
 def csrf(i,path='/admin/profile'):
  r=clients[i].get(path); return re.search(r'name="_csrf"[^>]*value="([^"]+)"',r.text)[1]
 def write(i,path,data=None):
  return clients[i].post(path,data={**(data or {}),'_csrf':csrf(i)})
 def pair(name,path,data=None): check(name,response(write(0,path,data)),response(write(1,path,data)))
 try:
  for i,c in enumerate(clients):
   r=c.post('/login',data={'username':os.environ.get('TEST_ADMIN_USERNAME','riuken'),'password':os.environ.get('TEST_ADMIN_PASSWORD','123456'),'_csrf':csrf(i,'/login')})
   assert response(r)==dict(status=302,location='/admin')
  paths=['/','/?page=0','/?size=0','/?page=-1','/?page=999','/archive','/search','/search?keyword=Spring','/post/missing','/tag/missing','/category/missing','/admin/categories','/admin/posts/edit/999999','/admin/links/edit/999999','/admin/posts?page=bad','/admin/posts/download/999999','/error','/login?logout']
  for path in paths: check('GET '+path,response(clients[0].get(path)),response(clients[1].get(path)))
  check('POST missing CSRF',response(clients[0].post('/admin/posts/save')),response(clients[1].post('/admin/posts/save')))
  pair('UTF16 emoji summary','/admin/posts/save',dict(title='Emoji边界',slug='emoji-probe',content='a'+'😀'*150))
  check('UTF16 persisted summary',rows(0,"SELECT summary FROM t_post WHERE slug='emoji-probe'"),rows(1,"SELECT summary FROM t_post WHERE slug='emoji-probe'"))
  pair('create article','/admin/posts/save',dict(title='兼容测试 <>& Emoji 😀',slug='migration-probe',content='# 内容\n\n![图片](/upload/probe.png)\n\n| A | B |\n| :- | -: |\n| 1 | 2 |\n',tagsStr='迁移,测试，迁移',categoryId='1'))
  ids=[rows(i,'SELECT id FROM t_post WHERE slug=%s',('migration-probe',))[0]['id'] for i in range(2)]
  fields='title,slug,content,content_html,summary,thumbnail,category_id,status,type'
  check('article fields',rows(0,'SELECT '+fields+' FROM t_post WHERE id=%s',(ids[0],)),rows(1,'SELECT '+fields+' FROM t_post WHERE id=%s',(ids[1],)))
  check('tag associations',rows(0,'SELECT t.name,t.slug FROM t_tag t JOIN t_post_tag pt ON t.id=pt.tag_id WHERE pt.post_id=%s',(ids[0],)),rows(1,'SELECT t.name,t.slug FROM t_tag t JOIN t_post_tag pt ON t.id=pt.tag_id WHERE pt.post_id=%s',(ids[1],)))
  for i in range(2):
   r=write(i,'/admin/posts/save',dict(id=ids[i],title='修改',slug='migration-probe',content='edited',tagsStr='',status='DRAFT',type='PAGE')); assert r.status_code==302
  check('edit preserves type and clears tags',rows(0,'SELECT '+fields+' FROM t_post WHERE id=%s',(ids[0],)),rows(1,'SELECT '+fields+' FROM t_post WHERE id=%s',(ids[1],)))
  for i in range(2): write(i,'/admin/drafts/delete/'+str(ids[i]))
  check('draft deletion',rows(0,'SELECT id FROM t_post WHERE slug=%s',('migration-probe',)),rows(1,'SELECT id FROM t_post WHERE slug=%s',('migration-probe',)))
  pair('create link','/admin/links/save',dict(name='兼容友链',url='https://example.com'))
  check('link defaults',rows(0,'SELECT name,url,logo,description,team,sort FROM t_link WHERE name=%s',('兼容友链',)),rows(1,'SELECT name,url,logo,description,team,sort FROM t_link WHERE name=%s',('兼容友链',)))
  for i in range(2):
   id=rows(i,'SELECT id FROM t_link WHERE name=%s',('兼容友链',))[0]['id']; write(i,'/admin/links/delete/'+str(id))
  comment_ids=[]
  for i in range(2):
   r=clients[i].post('/comment/submit',data=dict(postId='2',author='兼容评论',email='test@example.com',content='文本 <b>纯文本</b>'),headers={'Referer':str(clients[i].base_url).rstrip('/')+'/post/hello-world'})
   assert response(r)==dict(status=302,location='/post/hello-world')
   comment_ids.append(rows(i,'SELECT id FROM t_comment WHERE author=%s',('兼容评论',))[0]['id'])
  check('comment data',rows(0,'SELECT post_id,parent_id,author,email,url,content,status,is_admin FROM t_comment WHERE id=%s',(comment_ids[0],)),rows(1,'SELECT post_id,parent_id,author,email,url,content,status,is_admin FROM t_comment WHERE id=%s',(comment_ids[1],)))
  for i in range(2): write(i,'/admin/comments/delete/'+str(comment_ids[i]))
  pair('settings save','/admin/options/save',dict(site_title='兼容性测试'))
  check('settings business value',rows(0,"SELECT option_value FROM t_option WHERE option_key='site_title'"),rows(1,"SELECT option_value FROM t_option WHERE option_key='site_title'"))
  pair('own profile save','/admin/profile/save',dict(id='1',username='riuken',nickname='兼容测试',email='test@example.com',avatar='/butterfly/img/avatar.jpg'))
  check('profile fields',rows(0,'SELECT username,nickname,email,avatar FROM t_user WHERE id=1'),rows(1,'SELECT username,nickname,email,avatar FROM t_user WHERE id=1'))
  pair('wrong old password','/admin/profile/password',dict(userId='1',oldPassword='wrong',newPassword='unused'))
  for i in range(2):
   r=write(i,'/logout'); assert response(r)==dict(status=302,location='/')
   assert clients[i].get('/admin/posts').status_code==302
  checks.append(dict(name='schema unchanged for all 8 tables',match=all(schemas[i]=={n:re.sub(r'AUTO_INCREMENT=\d+','AUTO_INCREMENT=COUNTER',rows(i,'SHOW CREATE TABLE '+n)[0]['Create Table']) for n in NAMES} for i in range(2))))
  completed=True
 finally:
  for i in range(2):
   clients[i].post('/login',data={'username':os.environ.get('TEST_ADMIN_USERNAME','riuken'),'password':os.environ.get('TEST_ADMIN_PASSWORD','123456'),'_csrf':csrf(i,'/login')})
   write(i,'/admin/options/save',{r['option_key']:r['option_value'] for r in snapshots[i]['t_option']})
   with conns[i].cursor() as c:
    conns[i].begin()
    for n in NAMES: c.execute('DELETE FROM '+n)
    for n in reversed(NAMES):
     for row in snapshots[i][n]:
      c.execute('INSERT INTO '+n+' ('+','.join('`'+k+'`' for k in row)+') VALUES ('+','.join(['%s']*len(row))+')',tuple(row.values()))
    conns[i].commit()
   clients[i].close(); conns[i].close()
  Path('reports/differential.json').write_text(json.dumps(dict(checks=checks,passed=completed and all(x['match'] for x in checks),completed=completed,scope='Two isolated MySQL instances, snapshots restored with DML; auto-increment counters naturally advance.'),ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__': main()
