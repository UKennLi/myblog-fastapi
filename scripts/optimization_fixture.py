"""Synthetic visual fixtures only on an explicitly UUID-bound disposable server."""
import os,subprocess,json,sys
from pathlib import Path
import pymysql
from dotenv import load_dotenv
if os.environ.get('MIGRATION_ENV_FILE'):load_dotenv(os.environ['MIGRATION_ENV_FILE'],override=True)
assert os.environ.get('TEST_DATABASE_IS_DISPOSABLE')=='1','Disposable database authorization required'
assert os.environ['DB_HOST']=='127.0.0.1','Local isolated server required'
db=pymysql.connect(host=os.environ['DB_HOST'],port=int(os.environ['DB_PORT']),user=os.environ['DB_USER'],password=os.environ['DB_PASSWORD'],database=os.environ['DB_NAME'],autocommit=True)
posts=[];comments=[]
try:
 with db.cursor() as c:
  c.execute('SELECT @@server_uuid');assert c.fetchone()[0]==os.environ.get('TEST_MYSQL_SERVER_UUID'),'Unexpected MySQL UUID'
  for i in range(12):
   c.execute("INSERT INTO t_post(title,slug,content,summary,thumbnail,status,type,category_id) VALUES(%s,%s,%s,%s,%s,'PUBLISHED','POST',1)",('合成测试 '+('Long标题😀日本語'*20 if i==0 else str(i)),f'optimization-fixture-{i}','# 正文\n中文 日本語 English\n![测试](/butterfly/img/1d.png)','正文 ![图片](/butterfly/img/1d.png) [链接](https://example.com) **摘要**','/butterfly/img/1d.png'));posts.append(c.lastrowid)
  c.execute("INSERT INTO t_comment(post_id,author,email,content) VALUES(2,'Synthetic parent','','fixture parent')");root=c.lastrowid;comments.append(root)
  c.execute("INSERT INTO t_comment(post_id,parent_id,author,email,content) VALUES(2,%s,'Synthetic child','','fixture reply')",(root,));comments.append(c.lastrowid)
  c.execute("INSERT INTO t_comment(post_id,parent_id,author,email,content) VALUES(2,%s,'Synthetic grandchild','','fixture nested')",(comments[-1],));comments.append(c.lastrowid)
  c.execute("INSERT INTO t_comment(post_id,author,email,content) VALUES(1,'Synthetic page parent','','fixture page parent')");page_root=c.lastrowid;comments.append(page_root)
  c.execute("INSERT INTO t_comment(post_id,parent_id,author,email,content) VALUES(1,%s,'Synthetic page child','','fixture page reply')",(page_root,));comments.append(c.lastrowid)
 routes=json.loads(os.environ.get('OPTIMIZATION_VISUAL_ROUTES','["/","/post/hello-world","/about","/archive","/search?keyword=Spring","/admin","/admin/options","/admin/posts/new","/admin/profile"]'))
 output=os.environ.get('OPTIMIZATION_VISUAL_OUTPUT','reports/optimization/final-visual')
 subprocess.run([os.environ.get('BROWSER_PYTHON','python'),'scripts/optimization_visual.py','--admin-fixture','--output',output,'--routes',*routes],check=True)
 (Path(output)/'fixture.json').write_text(json.dumps({'synthetic_posts':len(posts),'nested_comments':len(comments),'production_data':False,'cleanup':'finally deletes only created IDs'},indent=2))
finally:
 with db.cursor() as c:
  for id in reversed(comments):c.execute('DELETE FROM t_comment WHERE id=%s',(id,))
  for id in posts:c.execute('DELETE FROM t_post WHERE id=%s',(id,))
 db.close()
