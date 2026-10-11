"""Read-only localhost comparison; not a production capacity prediction."""
import argparse,concurrent.futures,json,math,time,os
from pathlib import Path
from urllib.parse import urlsplit
import httpx
import pymysql
from dotenv import load_dotenv


def process(pid):
    if not pid:return None
    data=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
    stat=Path('/proc/'+str(pid)+'/status').read_text()
    rss=next(int(line.split()[1]) for line in stat.splitlines() if line.startswith('VmRSS:'))
    return dict(cpu_seconds=(int(data[11])+int(data[12]))/os.sysconf('SC_CLK_TCK'),rss_mib=rss/1024)


def main():
    p=argparse.ArgumentParser();p.add_argument('--old',required=True);p.add_argument('--new',required=True);p.add_argument('--old-pid',type=int);p.add_argument('--new-pid',type=int);p.add_argument('--old-db-pid',type=int);p.add_argument('--new-db-pid',type=int);p.add_argument('--env-file');p.add_argument('--requests',type=int,default=200);p.add_argument('--concurrency',type=int,default=8);p.add_argument('--output',default='reports/performance.json');p.add_argument('--routes',nargs='+',default=['/','/post/hello-world','/archive','/search?keyword=Spring']);a=p.parse_args()
    if any(urlsplit(u).hostname not in ('127.0.0.1','localhost') for u in (a.old,a.new)):p.error('Benchmark only supports isolated localhost targets')
    if any(not route.startswith('/') or route.startswith('//') for route in a.routes):p.error('Routes must be local absolute paths')
    if a.env_file:load_dotenv(a.env_file,override=True)
    def database_status(port):
        if not a.env_file:return None
        with pymysql.connect(host=os.environ['DB_HOST'],port=port,user=os.environ['DB_USER'],password=os.environ['DB_PASSWORD']) as db:
            with db.cursor() as c:
                c.execute("SHOW GLOBAL STATUS WHERE Variable_name IN ('Questions','Com_select','Com_insert','Com_update','Threads_connected')")
                return {key:int(value) for key,value in c.fetchall()}
    results=[]
    for round in [1,2]:
        targets=[('old',a.old,a.old_pid,a.old_db_pid,3307),('new',a.new,a.new_pid,a.new_db_pid,3308)]
        if round==2:targets.reverse()
        for label,base,pid,dbpid,dbport in targets:
            with httpx.Client(base_url=base,timeout=30,limits=httpx.Limits(max_connections=a.concurrency,max_keepalive_connections=a.concurrency)) as client:
                for _ in range(20):assert client.get('/').status_code==200
                for route in a.routes:
                    before=process(pid);dbbefore=process(dbpid);statusbefore=database_status(dbport)
                    def request(_):
                        start=time.perf_counter()
                        try:r=client.get(route);return ((time.perf_counter()-start)*1000,r.status_code)
                        except httpx.HTTPError:return ((time.perf_counter()-start)*1000,0)
                    start=time.perf_counter()
                    with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrency) as pool:samples=list(pool.map(request,range(a.requests)))
                    elapsed=time.perf_counter()-start;after=process(pid);dbafter=process(dbpid);statusafter=database_status(dbport)
                    times=sorted(t for t,_ in samples)
                    result=dict(round=round,target=label,route=route,requests=a.requests,concurrency=a.concurrency,elapsed_seconds=elapsed,throughput_rps=a.requests/elapsed,p50_ms=times[len(times)//2],p95_ms=times[math.ceil(len(times)*.95)-1],errors=sum(s!=200 for _,s in samples))
                    if before:
                        cpu=after['cpu_seconds']-before['cpu_seconds'];result.update(app_cpu_seconds=cpu,app_average_cpu_percent_one_core=100*cpu/elapsed,app_rss_before_mib=before['rss_mib'],app_rss_after_mib=after['rss_mib'])
                    if dbbefore:
                        cpu=dbafter['cpu_seconds']-dbbefore['cpu_seconds'];result.update(mysql_cpu_seconds=cpu,mysql_average_cpu_percent_one_core=100*cpu/elapsed,mysql_rss_before_mib=dbbefore['rss_mib'],mysql_rss_after_mib=dbafter['rss_mib'])
                    if statusbefore:result['mysql_status_delta']={k:statusafter[k]-v for k,v in statusbefore.items()}
                    results.append(result);print(label,route,'p95=%.2fms rps=%.1f'%(result['p95_ms'],result['throughput_rps']),flush=True)
    Path(a.output).write_text(json.dumps(dict(results=results,conditions='Same host, separate cloned MySQL 8.4 instances, warmed existing session, one process each; 2 rounds reverse order; small public seed dataset; CPU/RSS samples and MySQL counters; no production sizing inference.'),indent=2)+'\n')
if __name__=='__main__':main()
