# Ubuntu 24.04 + systemd 维护操作手册

本轮没有操作生产服务器。本手册命令由运维审核、备份和授权后手工执行；不把生产作为测试库。保持 /home/riuken/Blog、.venv、MySQL8原八表、myblog服务和127.0.0.1:8000单Worker，Cloudflare Tunnel保持本机上游。参考单元deploy/myblog.service.example；现有单元先用systemctl cat myblog检查，不能盲目覆盖。

## 更新前

1. 维护窗口、操作者、目标提交和回滚提交写入变更记录；阅读optimization-report.md，分类管理/改密认证流程不在本轮范围。
2. 在隔离副本运行pytest、浏览器/Markdown、Schema校验；禁止生产运行pytest、demo_seed、init_test_database或任何DDL。当前测试库安全UUID机制必须保留。
3. 在生产只做运维检查：`git -C /home/riuken/Blog status --short`、`git ... rev-parse HEAD`、`systemctl status myblog --no-pager`、`journalctl -u myblog -n 100 --no-pager`、磁盘容量和内存/Swap、uploads可写、数据库DML账号/连接池是否正常。不要把.env或日志中的个人数据贴到公开位置。
4. 保存现有提交、虚拟环境版本清单、systemd单元、Cloudflare配置；保护.env 600、目录700/750。保持密码和SESSION_SECRET，不将它们写入命令行、脚本、截图、Git或公开日志。
5. 暂停全部写入口，确认评论/上传/后台没有并发写入。不能只关闭后台却允许评论继续写。如何暂停入口由现有代理/运维流程决定；脚本不会自动更改Tunnel或停止服务。

## 备份与恢复

私有MySQL配置如 `/home/riuken/.config/myblog-backup.cnf`（600）包含 `[client]` 和准确host/port/user/password。备份账号需SELECT及mysqldump需要的权限；不要提高应用DML账号到DDL。先预览：

```bash
bash scripts/production_backup.sh /home/riuken/Blog /home/riuken/backups/myblog /home/riuken/.config/myblog-backup.cnf
# 确认目标和暂停写入后，由运维执行：
bash scripts/production_backup.sh --execute /home/riuken/Blog /home/riuken/backups/myblog /home/riuken/.config/myblog-backup.cnf
```

脚本仅导出八业务表的数据、uploads、提交ID和可选私有.env；不包含CREATE/DROP/ALTER/TRUNCATE、不清空数据库或uploads。SQL中mysqldump的会话SET/LOCK格式需在恢复前审查；不直接把任何dump喂给生产。每份备份独立目录/权限700，包含SHA256SUMS；复制到异地加密存储并演练恢复。环境备份含密码，绝不能跟报告一起上传GitHub。

数据恢复先在已有相同Schema的全新隔离库导入data.sql，核对8表数量/业务数据、文章/评论/标签关联及图片。Schema需要来自审计定义；只允许在已确认专用隔离实例初始化。data.sql是完整INSERT，并非幂等恢复脚本，直接导入现有库会冲突；不要用REPLACE/INSERT IGNORE掩盖差异。生产数据损坏恢复需另行批准，先保存当前数据库和文件，再人工规划按ID补回/事务校验，避免重复或丢失新写入。本轮无自动生产恢复或删除脚本。

uploads恢复先解压到临时隔离目录，核对校验和及tar条目，不覆盖源目录。恢复缺失文件要保持UUID名称；保留更新后新增文件，禁止删除历史uploads。Session SQLite属于登录状态，通常无需恢复；若备份它，需停应用或用SQLite online backup，不能只复制活跃的主文件漏掉WAL。重启会清空Session，管理员重新登录，BCrypt密码不变。

## 更新

建议先在工作副本核验目标提交，再维护窗口更新。不要git clean、reset --hard或覆盖未知本地改动。确认工作区干净：

```bash
cd /home/riuken/Blog
git fetch origin
git diff --stat CURRENT_COMMIT TARGET_COMMIT
git merge --ff-only TARGET_COMMIT
```

若分支不能快进，停止并审查本地提交/配置，不能强推生产分支。依赖锁本轮没有整体升级；正常无需更新所有依赖。需重新安装时在隔离虚拟环境使用requirements.lock并pip check，先验证后切换，保留旧环境供回滚。

.env增加 `PUBLIC_SITE_URL=https://riuken.com`，把 `LEGACY_TEMPLATE_JS=false` 显式写入；保留其他现有设置，HTTPS推荐COOKIE_SECURE=true。此域名只用于生成链接，不依赖客户端Host/Forwarded。配置没有公开地址时文章链接退回相对路径，sitemap503，不能上线后忽略这一检查。

配置权限保持600，服务通过WorkingDirectory读取.env；不要直接把.env当shell脚本source，避免特殊字符和命令执行。Uvicorn仍1 worker，代理头只信任本机Tunnel，不能用forwarded-allow-ips='*'。原GET/logout确认/POST注销及改密跳确认页流程保留。

只有完成审核和维护窗口授权后执行：

```bash
sudo systemctl restart myblog
sudo systemctl status myblog --no-pager
sudo journalctl -u myblog -n 100 --no-pager
```

若更改单元，先systemd-analyze verify审核，再daemon-reload；仅代码和.env更新不需要改unit。首次启动失败检查工作目录、ExecStart/.venv、依赖、.env变量/权限、uploads/state权限、DB地址/权限、8000端口占用，避免不断重启或修改数据库结构。

## 部署后验收

低频GET检查首页、已知文章、about、archive、search、robots.txt、sitemap.xml、缺失页面404；文章版权URL及canonical必须https://riuken.com，无null/127.0.0.1。检查历史图片、后台图标、四视口首页与文章，不对公网压测。

管理员手动检查登录、CSRF、后台文章/设置加载。数据库连通性用只读SELECT 1、SHOW CREATE TABLE检查八表，与更新前比对；应用/测试不执行DDL。后台发布/编辑/上传/评论等写入验收只使用运维事先批准的测试记录和文件，约定保留/清理方式，不能擅自修改真实文章和账户密码。监控journalctl错误率、MySQL连接/慢查询（只读取现有日志，不擅自改全局日志参数）、内存/Swap和Tunnel状态。Session重启失效是预期。

## 回滚

记录每阶段提交；对问题阶段做git revert并在隔离副本验证，发布明确回滚提交，生产通过上述快进/审核流程更新。不用git reset覆盖本地文件。不回退MySQL数据、不恢复旧数据库快照，不删除新uploads。保持现有.env和密码；代码回退会恢复相应旧兼容缺陷，若恢复原JS行为需明确配置true。回滚后由运维授权restart myblog，按同一验收清单复核。性能缓存只是内存，重启即清空。

若依赖曾独立更新，回切经过验证的旧虚拟环境。只有数据确实损坏才启动另外的数据恢复审批；备份恢复不是普通代码回滚步骤。

本轮提交存在依赖：公开URL helper被SEO复用，原生评论CSS和宏去重需成组部署/回滚。只能部署本分支最终验证的完整版本；全量回滚在隔离副本逆序revert本轮整组，再测试和发布。不要只撤销评论CSS或在SEO代码仍在时撤销URL helper。若只回退某项行为，先制作有针对性的回退补丁并验证，不能直接任选一个阶段提交撤销。
