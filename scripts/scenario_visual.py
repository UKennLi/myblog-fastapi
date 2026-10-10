"""Visual fixtures on explicitly identified disposable databases; restore all rows."""
import argparse,os,json,subprocess,sys
from pathlib import Path
import pymysql
from dotenv import load_dotenv

NAMES=['t_post_tag','t_comment','t_post','t_tag','t_category','t_link','t_option','t_user']
def main():
 p=argparse.ArgumentParser();p.add_argument('--env-file',required=True);p.add_argument('--old-uuid',required=True);p.add_argument('--new-uuid',required=True);p.add_argument('--disposable',action='store_true',required=True);p.add_argument('--browser-python',default=sys.executable);a=p.parse_args();load_dotenv(a.env_file,override=True)
 connections=[pymysql.connect(host=os.environ['DB_HOST'],port=port,user=os.environ['DB_USER'],password=os.environ['DB_PASSWORD'],database=os.environ.get('DB_NAME','myblog_db'),cursorclass=pymysql.cursors.DictCursor,autocommit=True) for port in [3307,3308]]
 snapshots=[]
 for c,u in zip(connections,[a.old_uuid,a.new_uuid]):
  with c.cursor() as cur:
   cur.execute('SELECT @@server_uuid AS uuid');assert cur.fetchone()['uuid']==u,'Refusing unexpected instance'
   data={}
   for n in NAMES:cur.execute('SELECT * FROM '+n);data[n]=cur.fetchall()
   snapshots.append(data)
 def browser(prefix,routes,width=1440,height=900):
  env=dict(os.environ,VISUAL_PREFIX=prefix,VISUAL_ROUTES=json.dumps(routes),VISUAL_WIDTH=str(width),VISUAL_HEIGHT=str(height))
  with open('reports/'+prefix+'-run.txt','w') as f:subprocess.run([a.browser_python,'scripts/browser_compare.py'],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 try:
  for c in connections:
   with c.cursor() as cur:
    for i in range(15):
     cur.execute('INSERT INTO t_post(id,title,slug,content,summary,thumbnail,category_id,created) VALUES(%s,%s,%s,%s,%s,%s,1,%s)',(650001+i,('长标题 中文 English <>& 😀 '*10)[:230] if i==0 else '分页文章 '+str(i),'visual-probe-'+str(i),'# 标题\n\n**粗体** 与 `<>&`\n\n![本地图片](/butterfly/img/avatar.jpg)\n\n| A | B |\n| :--- | ---: |\n| 左 | 右 |\n','长摘要 <>& 中文 '+('正文 '*50),'/butterfly/img/DefualtThumbnail.jpg','2025-02-%02d 12:00:00'%(i+1)))
    cur.execute("INSERT INTO t_tag(id,name,slug) VALUES(600001,'中文 标签','visual-tag')")
    cur.execute('INSERT INTO t_post_tag(post_id,tag_id) VALUES(650001,600001)')
    for id,parent,name,content in [(610001,None,'访客中文','文本 <b>转义</b> & 😀'),(610002,610001,'回复中文','嵌套回复'),(610003,None,'管理员','管理员徽章')]:
     cur.execute('INSERT INTO t_comment(id,post_id,parent_id,author,email,url,content,is_admin,created) VALUES(%s,2,%s,%s,%s,%s,%s,%s,%s)',(id,parent,name,'visual@example.com','https://example.com',content,id==610003,'2025-02-01 12:00:00'))
  browser('fixture-desktop',['/','/?page=2','/category/default?page=2','/tag/visual-tag','/post/visual-probe-0','/post/hello-world','/admin/posts?page=2','/admin/posts/edit/650001','/admin/comments'])
  browser('fixture-mobile',['/','/?page=2','/post/visual-probe-0','/post/hello-world','/admin/posts?page=2'],390,844)
  for c in connections:
   with c.cursor() as cur:
    for n in ['t_post_tag','t_comment','t_post','t_tag','t_link']:cur.execute('DELETE FROM '+n)
  browser('empty-desktop',['/','/archive','/links','/admin/posts','/admin/drafts','/admin/comments','/admin/links','/admin/about'])
 finally:
  for c,snapshot in zip(connections,snapshots):
   with c.cursor() as cur:
    c.begin()
    for n in NAMES:cur.execute('DELETE FROM '+n)
    for n in reversed(NAMES):
     for row in snapshot[n]:cur.execute('INSERT INTO '+n+' ('+','.join('`'+k+'`' for k in row)+') VALUES ('+','.join(['%s']*len(row))+')',tuple(row.values()))
    c.commit()
   c.close()
if __name__=='__main__':main()
