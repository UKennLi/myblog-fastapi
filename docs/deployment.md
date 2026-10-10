# 部署、切换与回滚

## 上线配置

应用只连接原有 MySQL，默认不做 DDL。使用独立的 DML 权限应用账号，保留 `myblog_db`、8 张表、字段和索引。替换 `.env.example` 中的密码和 Session 密钥；配置文件权限建议 600，备份同样限制访问。

启动入口是项目根目录下 `uvicorn app.main:app`。Docker 内仅含 Python 应用、Jinja2 和静态资源，无 Java、无原仓库、无 Spring 网络依赖。Compose 默认一个 worker，配置缓存和单机 SQLite Session 符合原单实例部署行为。Session 密钥变更或应用重启会使已有登录失效，匹配原Java进程内会话。

上传文件必须把原 `uploads/` **全部复制**到新持久目录，不能只用交付包中的仓库样例。保持 UUID 文件名和路径，检查挂载 UID 1000 的写入权限；避免容器删除时丢文件。已有 HTML/SVG 等主动内容按附件和 sandbox 提供，正常图片访问不变。

## HTTPS 与反向代理

下面是可按真实域名调整的 nginx 示例。证书由现有 TLS 管理工具维护，不随代码提交：

```nginx
server {
    listen 443 ssl;
    server_name blog.example.com;
    ssl_certificate /etc/letsencrypt/live/blog.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/blog.example.com/privkey.pem;
    client_max_body_size 10m;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

HTTPS 部署设置 `COOKIE_SECURE=true`。Uvicorn 只信任明确的反向代理 IP；默认信任本机 127.0.0.1。跨 Docker 网络时启动加 `--proxy-headers --forwarded-allow-ips=代理实际IP`，不要让外部用户直接访问这个可信上游端口。可信代理提供正确 scheme/host 后，绝对重定向、Secure Cookie、HSTS 才对应外部 HTTPS。HTTP 入口转到 HTTPS。

生产代理配置未在当前无域名/证书环境部署；这是明确需要现场验证的项目。

## 备份

使用 MySQL 客户端受限配置文件，避免密码出现在命令行或日志。例如私有 `backup.cnf` 保存 `[client]` 的 host/port/user/password，文件权限 600。备份账号需要对应 mysqldump 权限：

```bash
umask 077
mysqldump --defaults-extra-file=/secure/backup.cnf \
  --single-transaction --skip-lock-tables --no-tablespaces \
  --set-gtid-purged=OFF myblog_db > myblog-db-before-switch.sql
tar -czf myblog-uploads-before-switch.tar.gz -C /path/to/old-project uploads
sha256sum myblog-db-before-switch.sql myblog-uploads-before-switch.tar.gz > backup.sha256
```

对数据库与上传的严格一致快照，应先暂停后台和评论写入，再执行以上备份。不能从两个仍在写入的目录拼出保证一致的备份。先在隔离 MySQL 上演练恢复并核对数据，再安排生产窗口。

## 生产切换

1. 在测试副本验证：相同时区、历史 BCrypt 用户、所有页面、已有图片、文章保存/评论/备份下载、代理与 Cookie。阅读验收中未覆盖的条件。
2. 暂停旧服务写入入口，备份原库和上传目录，保存旧镜像/JAR、配置和代理配置。不要删除旧服务。
3. 复制上传历史到新挂载目录，检查所有权；新应用连接原库，使用仅 DML 的用户。不要执行测试初始化 CLI 或 `blog_init.sql`。
4. 用只读 schema 审计核对 8 表定义；启动新应用，在内部端口完成只读烟测。生产写入验收使用预先约定的测试记录，确认后清理。
5. 切换反向代理 upstream 到新应用并恢复写入。Java 内存 Session 不能迁移，管理员需重新登录；用户密码不变。
6. 观察错误率、连接池、图片和写入；记录切换时间。保留旧部署和备份，避免两个服务同时运营造成配置缓存/写入冲突。

此交付没有替用户操作生产服务、生产库或 DNS；上线应在上述验证后按自己的维护窗口执行。

## 回滚

应用仍使用旧 schema 和 BCrypt 格式。通常可暂停写入，把代理 upstream 切回旧 Spring Boot，确认其指向同一数据库和包含新上传文件的目录，重新启动旧进程刷新设置缓存。**不需要先恢复旧数据库备份**；这样可保留切换后新增文章与评论。

回滚前把新目录中新上传文件同步回旧服务可见目录，保留原文件名，不删除历史文件。新 Python Session 不兼容 Java Session，需要重新登录。数据库和文件是否能完整保留，应以回滚窗口的只读核对为准。

只有发现数据被损坏才考虑恢复数据库备份。先保存当前数据库和上传副本，停止全部写入，在隔离实例演练，再经运维明确授权恢复；恢复较早快照会丢失之后的写入。恢复命令示例（仅在目标实例已明确确认后执行）：

```bash
mysql --defaults-extra-file=/secure/restore-target.cnf myblog_db < reviewed-backup.sql
```

备份可能含 DROP/CREATE，因此该命令绝不能作为应用启动步骤或自动回滚钩子。

## 升级与日常检查

依赖升级先修改版本锁，运行真实 MySQL 测试、浏览器比较和性能比较。检查 `/` 健康、后台登录、日志及 MySQL 连接；备份 uploads 和数据库，SQLite Session 可备份但恢复后建议要求重新登录。所有真实秘密、Session 文件和生产数据备份不进入源码包。
