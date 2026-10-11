# 第二阶段修复与生产优化

日期：2026-10-11。基线提交：0c9128b。只操作云环境专用 MySQL 3308；运行前核对容器 auto.cnf UUID 与服务 UUID。生产 riuken.com、/home/riuken/Blog 和生产数据库均未连接、写入或重启。

## 审计与方案

架构：FastAPI 同步查询通过线程池执行；SQLAlchemy/PyMySQL 原八表参数化 SQL；Jinja2/Butterfly；SQLite 服务端 Session；RLock OptionCache；单 Uvicorn Worker。启动只读取设置，不执行业务 DDL。测试保存/恢复专用库记录，使用 DML 账号。

| 优先级/组 | 问题、证据或待验证假设 | 文件 | 风险与验收 |
|---|---|---|---|
| P0/A | siteUrl 从 t_option→OptionCache→context；缺失时显式拼接 null。后台设置表单没有站点地址字段，现有界面不能直接配置 | post.html、views.py、options.py、config.py | 低；配置 HTTPS 完整链接，缺失退回相对路径，不使用 Host/Forwarded |
| P0/A | Spring Boot 页脚署名 | fragments/footer.html | 低；只改文字/官方链接，保留主题与布局 |
| P0/A | 同一评论宏在 vlist 内及 post 容器末尾调用两次 | post.html | 低；每层评论一次，表单/回复保留，不改记录 |
| P1/B | 首页横向溢出，具体元素待四视口 Chromium 测量 | Butterfly CSS、首页、侧栏 | 中；定位元素后局部修复，禁止全页隐藏溢出 |
| P1/B | java_summary 仅替换几个字符，留下图片/链接；历史摘要直出 | posts.py、index.html | 中；自动摘要纯文本，手动摘要原值保留，历史仅展示处理 |
| P1/A | LEGACY_TEMPLATE_JS 默认 true，root 输出异常双引号 | config.py、head/footer | 低；修复默认值并测 JS，旧显式环境配置需同步关闭 |
| P1/A | 图标引用1.11.3，而文件实际1.13.1 | admin/layout/admin.html | 低；正确路径200，后台图标恢复 |
| P1/A | 缺失文章/分类/标签/PAGE HTML404但HTTP200 | public.py | 低；状态404，原404模板保留 |
| P1/A | login?logout 人工抛500 | auth.py | 低；恢复现有登录页与已存在退出提示，不改变登录/退出流程 |
| C/待批准 | 分类管理模板与写入路由从未存在 | admin.py | 新功能；建议单独设计CRUD/CSRF/引用分类处理；本轮不新增 |
| C/待批准 | 改密成功GET/logout只确认，未实际注销 | admin.py、auth.py | 认证流程变更；建议明确批准后撤销会话并跳登录；本轮保留 |
| P2/B | 首页每篇额外分类/标签查询，侧栏重复计数；Markdown每次渲染 | blog.py、views.py、posts.py | 中；先测查询数和延迟，再批量加载/有界正文缓存，不缓存整页 |
| P2/B | CDN重复FontAwesome、图片加载与CWV | head.html、index.html | 中；测本地浏览器与资源可用性，不伪称生产CWV |
| P2/A | 缺canonical/description/OG、robots/sitemap | head.html、public.py | 使用配置URL；未配置不输出假公网URL；不含后台/登录/草稿；无新表 |

顺序：P0→回归测试/视觉证据→单独提交→P1→性能/SEO→维护文档。所有低风险缺陷修复独立记录兼容行为差异；新增分类管理、改密流程等待用户批准。Schema、URL路径、单Worker、安全约束和锁定依赖保持。

## P0 实施

统一解析 PUBLIC_SITE_URL，其次已存在的 t_option.siteUrl；只允许无凭据、无query/fragment的HTTP(S)公开地址，拒绝本机/私网与非法端口。配置缺失使用 /post/{slug}，不从请求头推导公网域名。生产应显式配置 PUBLIC_SITE_URL=https://riuken.com。href与显示使用同一函数。不新增后台字段或写入数据库。

移除评论列表外的第二次宏调用，保留递归子评论、表单及回复JS。页脚只改 FastAPI 文字和官方链接；文字宽度自然变化是预期视觉差异。

实际修改：app/services/site_url.py、app/core/config.py、app/services/views.py、templates/post.html、templates/fragments/footer.html、.env.example、tests/test_optimization.py。

测试与视觉数据在 reports/optimization/；结果待执行完成后追加。回滚：对本阶段提交 git revert，恢复配置后按维护流程由运维重启。没有数据库迁移或数据回写。

P0 验证：`/workspace/.venvs/myblog-fastapi/bin/python /workspace/.myblog/phase2-run.py test -q --junitxml=reports/optimization/p0-pytest.xml` 实际 **34 passed, 1 warning**（原 Starlette/httpx 弃用警告）。全套原功能、安全/上传/历史图片/Schema检查均执行。`python scripts/optimization_visual.py` 保存四视口×五页面×新旧共40张截图及资源/溢出/JS数据；新旧都有原 root SyntaxError。当前静态首页 document.scrollWidth 等于视口宽，但 scroll-down 和右侧按钮几何越界，需继续滚动/交互定位，不把几何越界直接等同于已复现滚动条。P0 不更改CSS。公网/生产网络条件未执行。

基线 SQL 首页15、文章13、归档11、搜索13。P0性能共1200 localhost请求/并发4/两轮反序，无错误；该批仅用于检查P0没有大幅退化，不代表生产容量。详见p0-performance.json。

## P1 实施与兼容变化

- 自动摘要由原“删几个符号/UTF16截断”改为Markdown→可见纯文本，去除图片/目标地址/HTML标签，保留多语言正文，150个Unicode码点不截断Emoji。手动摘要仍按输入保存；历史摘要只在首页展示清理，不回写。原UTF16边界测试改为验证完整Emoji，这属于明确批准的摘要优化行为变化，不降低校验。
- 默认 LEGACY_TEMPLATE_JS=false；显式旧 .env=true 仍保持兼容，生产必须更新为false。不存在页面的原404模板改为HTTP404；login?logout恢复模板中已有提示，GET只显示提示不执行注销；认证和改密流程不改。
- 后台图标引用改为现有1.13.1。1.11.3旧URL仍404，未重命名公开路径或资产。
- 首页四视口当前数据未复现整页横向滚动：scrollWidth=viewport。几何越界属于原header/固定隐藏按钮，尚无证明会增加根滚动宽度，不盲目增加CSS。记录为未解决/需真实溢出内容复现。
- 新发现原footer请求 /butterfly/js/main.js，但仓库没有此文件。已有 custom.main.js 为混淆脚本，并含依赖jQuery和主题署名检查；不能直接当作同等main.js替换。本轮不引入来源不明脚本，记录待单独交互设计/确认。

P1实际文件：config.py、public.py、auth.py、posts.py、views.py、index.html、admin/layout/admin.html、.env.example、test_application.py、test_optimization.py。全套测试实际36 passed,1 warning；包含保存/手动摘要/历史摘要不回写/Emoji/404/图标/JS配置。P1不改Schema，不批量改历史数据；预期视觉差异是摘要文字清理与后台图标恢复。截图p1-visual保留四视口证据。回滚本阶段提交即可恢复旧行为；新生成的纯文本摘要保持可读，不需要恢复DB。Ubuntu仍单Worker，仅新增/调整环境变量，生产服务本轮未重启。

## P2 后端性能

批量加载列表分类/标签（保留筛选/排序/关联），侧栏只读实际使用字段，取消无用COUNT及关联查询。Markdown最多64条、单条输入不超过65536字符；摘要最多256条、4096字符，超大输入绕过缓存。缓存键是内容，不是post ID；更新即命中新内容，无TTL等待；不缓存整页/Option/评论。作者HTML安全契约不改。SQL连接池保持5+10，未提高worker/引入重型服务；线程池上限/连接等待在更高并发生产负载下仍需测量。

基线6批算术平均P95 32.95ms；吞吐 157.0req/s；最终应用RSS 98.3MiB。

优化6批算术平均P95 26.06ms；吞吐 205.7req/s；最终应用RSS 94.2MiB。

同机同隔离库/数据，单worker，并发4，每路由200请求，两轮反序共2400，无错误；包含首页、文章、搜索。归档以查询数及功能测试验证。已预热，缓存热状态收益不能推为冷启动收益；不是生产容量预测。原Java服务不参与本阶段比较。原八表DDL校验通过；38 passed,1 warning。

SQL：首页15→8，文章13→8，归档11→6，搜索13→8；列表篇数增长不会线性增加关系查询。实际文件blog.py、views.py、posts.py、test_optimization.py。回滚本阶段提交，重启由运维执行，内存缓存自动清空，不涉及数据恢复。证据before/after-queries.json、p2-performance.json、p2-performance-pytest.xml。

## P2 SEO 与前端资源

新增用户本轮明确要求的GET /robots.txt、/sitemap.xml，位于PAGE catch-all前，不重命名原URL；reserved PAGE slug避免把后台等错误纳入sitemap。sitemap直接查发布POST/PAGE的slug/modified，每次读取新数据；缺公开地址503，无null/本机/客户端Host回退；超过50000 URL显式503并要求sitemap index，当前博客规模内不需要重型插件。草稿PAGE仍沿用原可访问行为，但noindex且不入站点图；隐藏草稿PAGE属于额外权限语义调整，本轮不改。

head增加纯文本description、canonical和OG；分类/标签/搜索title更准确；分页canonical包含page；搜索noindex；登录/后台noindex。Markdown已有图片alt按原作者文本保留，评论头像补作者alt。只改head/文字属性，不重排主题。

静态资源从Security原统一no-store改为成功GET/HEAD静态路径private max-age=300 must-revalidate，移除冲突Pragma/Expires；404、HTML、后台、API仍原no-store；不public缓存含Session Cookie的响应。原ETag/Last-Modified继续生效（实际304回归）。未采用immutable一年缓存以免同路径升级长期过期。首页第一张卡片图保留eager，其余native lazy，所有卡片async解码；不改变CSS比例/尺寸、原动画及onerror。

仓库全部CSS约4,278,469字节、JS约4,286,927字节，包括后台编辑器和未在前台加载的示例，不是首页实际传输量。默认封面1,006,389字节、归档背景1,444,853字节、logo2,373,417字节。未压缩/替换原图，避免未验证视觉变化；后续可独立评估保留原图的派生WebP。FontAwesome两份CDN是重复依赖，但当前云环境两者均不可用，不能据此选一个并删除另一个。四项外部资源失败详见visual JSON；生产CDN成功路径、真实CWV/INP未执行。local Chromium LCP/CLS只作为合成观测，不能替代线上用户指标。

测试：SEO增量后39 passed；静态/维护脚本后41 passed。初次新缓存测试误假设HTML没有Cache-Control，实际Security原来已设置no-store；修正为严格断言HTML/404保持no-store，未删测试/跳断言。维护备份测试只使用临时目录/假mysqldump，默认预览无输出写入、拒绝仓库内备份、8表data-only导出选项/权限/校验和/上传保留均验证；真实生产mysqldump和恢复未执行。systemd-analyze verify参考单元因云环境不存在/home/riuken/Blog/.venv/bin/uvicorn退出1，未宣称生产单元验证成功；Ubuntu目标机需按手册验证。

实际SEO/资源文件：public.py、views.py、site_url.py、main.py、static_cache.py、head.html、index.html、login.html、admin/layout/admin.html、post_comments.html、page_comments.html、test_optimization.py。无Schema/批量历史数据变更；预期视觉差异仅已有缺陷文字/重复评论/图标，lazy图滚动后布局保持。回滚对应阶段提交，浏览器旧静态缓存最多5分钟或强制刷新。

## 生产维护交付

新增docs/production-maintenance.md、scripts/production_backup.sh、deploy/myblog.service.example。包含更新前检查、版本记录、私有配置/Session保护、MySQL data-only备份及受控恢复、uploads备份、日志排查、更新后只读/人工授权写入验收、按阶段revert回滚。脚本默认预览、禁止备份到源码目录、限制客户端配置权限、输出目录700；密码不进入命令参数/日志。不含自动生产重启/恢复/清理。依赖锁不改，部署仍systemctl restart myblog（仅运维授权后手动），不改变单Worker/Tunnel。旧ZIP明确标为第一阶段归档，第二阶段以分支源码为准。

## 待批准设计与未完成项

1. 分类管理：现有GET/admin/categories会500且没有维护POST。本轮保留。建议另开独立提交：补现有GET模板、新增POST/admin/categories/save和POST/admin/categories/delete/{id}；沿用CSRF/admin校验；slug唯一校验；删除被文章引用的分类拒绝409，不擅自清空category_id。需批准新增后台功能与删除策略后实现。
2. 改密后注销：当前成功302/logout确认页，密码更新并不自动撤销Session。本轮保留；建议另开认证提交，撤销当前会话、清Cookie、跳现有login并显示改密提示；是否撤销全部该用户Session需明确产品决策。没有修改真实账户密码。
3. 首页横向滚动未在现有/合成长文本四视口数据确认复现，保留CSS。应提供实际溢出文章/公告/浏览器条件，再局部修复。绝不以overflow-x:hidden掩盖。
4. main.js原文件缺失；完整恢复暗色/侧栏/回顶等原本失效交互需要确认可靠原脚本及依赖，不直接引入混淆署名校验脚本。当前搜索与文章回复仍使用已有独立JS。
5. 云环境外部CDN/字体/部分外图不可访问，生产HTTPS/Cloudflare成功资源路径/真实CWV(INP)/大历史库/高并发/真实备份恢复未执行。慢查询只做本地SQL计数及现有查询审计，未修改生产MySQL日志或索引。

## 复现命令

先准备专用隔离MySQL、DML用户和已验证server UUID；环境文件不入Git。普通测试：

```bash
MIGRATION_ENV_FILE=/secure/disposable.env TEST_DATABASE_IS_DISPOSABLE=1 TEST_MYSQL_SERVER_UUID='verified-disposable-uuid' python -m pytest -q --junitxml=reports/optimization/final-pytest.xml
```

本云实例通过私有phase2-run.py启动/运行，先校验127.0.0.1:3308及目标容器auto.cnf UUID，再设置测试保护变量；该私有启动器不包含交付内秘密。baseline为git archive 0c9128b的只读本地快照（不是重新迁移/Java基线），8081；after8082，PUBLIC_SITE_URL=https://riuken.com、LEGACY_TEMPLATE_JS=false，两边Session文件各自独立。

```bash
python scripts/optimization_visual.py --before http://127.0.0.1:8081 --after http://127.0.0.1:8082
# 下列fixture脚本只允许显式Disposable+匹配UUID，创建合成数据并finally删除自身ID：
python scripts/optimization_fixture.py
python scripts/benchmark.py --old http://127.0.0.1:8081 --new http://127.0.0.1:8082 --requests 200 --concurrency 4 --output reports/optimization/final-performance.json
bash -n scripts/production_backup.sh
```

Playwright/Chromium使用云环境已安装的工具，未加入生产依赖。BROWSER_PYTHON可指定浏览器Python。初次真实回复点击因按钮默认hover隐藏而超时；保留测试要求，改为实际hover后click，未用force click绕过可见性。最终结果及截图索引在报告后续追加。

### 浏览器补充发现：评论CSS联动

真实三层评论场景暴露P0 DOM测试覆盖不足：原index.css规则 `#post-comment .comment-wrap>div:nth-child(2){display:none}` 用于双评论插件切换，却把原生vlist隐藏。基线post/page的第二份宏在容器外可见，第一份隐藏，所以存在重复DOM/ID，但默认并非两份都可见。只删除外部副本会导致评论不可见；P0初版有此回归，浏览器阶段发现后补正。

最小修复：comment.css增加单条 `#post #post-comment .comment-wrap > .vlist {display:block}`，并删除page.html同样的外部副本。保留原递归树/表单/原图片旋转与回复hover。未改index.css/布局/全局overflow。原静态全资源哈希断言没有删除：comment.css用optimization-assets.json记录原哈希与新哈希，分别严格校验；其余资产仍要求原SHA256。新增PAGE唯一评论ID测试。真实浏览器必须验证3条评论全可见、ID无重复、hover后click设置parentId。这一补正应与P0一起部署，不能只部署删除宏的提交。

## 最终回归与视觉验收

最终完整pytest：**45 passed,1 warning**，4.85s；原20项功能测试仍执行，保留CSRF/Session旋转与撤销、未登录权限、真实图片/历史文件/路径越界、SQL注入、事务回滚、ZIP、资料/改密本人校验、8表结构/DDL权限拒绝、CommonMark10组；新增链接安全回退、正文摘要/历史不回写、缺失404/退出提示、SQL批量关系等价、内容缓存更新、SEO草稿排除/删除后站点图刷新、静态304与HTML no-store、备份预览/模拟导出、文章/PAGE评论唯一性。实际命令和JUnit见final-pytest.xml。未升级httpx以消除原弃用警告。

`PYTHONPATH=. python scripts/inspect_database.py --env-file /secure/disposable.env --output reports/optimization/final-database.json`：实际8张完整SHOW CREATE TABLE与第一阶段记录逐字一致，仅归一自然增长AUTO_INCREMENT计数；包含字段类型、NULL/default、索引、collation，非只检查表数。应用无create_all/migration/DDL。fixture finally删除自身生成ID并保留原记录。

视觉：主场景四视口×9页面×前后共72张，加独立页面评论四视口×前后8张，总80张最终截图；另保留P0/P1各40张定位证据。主场景12篇合成长标题/多语言/Markdown图片摘要文章、三层评论；无真实生产数据或浏览器storage_state文件。覆盖首页、文章、about、归档、搜索、后台dashboard/options/posts-new/profile，全部预期200。基线文章有6个节点/重复ID但仅3个可见；修复后3个唯一节点且全可见，实际hover/click设置parentId；独立页同样通过。最终新页面捕获JS异常0，基线前台捕获原SyntaxError；不包括缺失main.js造成但不抛pageerror的功能缺失。

所有72页含四视口长内容的根scrollWidth等于viewport，滚动后也无横向根溢出。故本轮不“修复”尚未复现的首页横向滚动，也不添加全局overflow-x:hidden。截图包含正常hover/图片fallback与CSS动画抑制条件，不宣称所有生产资源/动画/浏览器像素完全一致。生产CDN成功资源、真实用户INP和外部图不可用问题保留限制。

视觉对比HTML索引：reports/optimization/final-visual/index.html、page-comments-visual/index.html；下载对应报告目录后在浏览器打开。阶段提交和文件列表见最后交付记录。

### 最终性能复测（包括归档）

实际单Worker、相同宿主/隔离库/原seed，4路由×200请求×新旧×两轮反序=3200请求，并发4，错误0。新服务包含最终SEO/缓存/摘要/评论修复。

| 路由 | 基线平均P95 ms | 优化平均P95 ms | 基线平均req/s | 优化平均req/s |
|---|---:|---:|---:|---:|
| / | 34.10 | 27.22 | 150.7 | 203.7 |
| /post/hello-world | 33.49 | 27.68 | 156.7 | 207.2 |
| /archive | 30.06 | 21.11 | 181.2 | 245.7 |
| /search?keyword=Spring | 32.37 | 23.71 | 164.2 | 222.1 |

old八批算术平均P95 32.50ms，吞吐 163.2req/s，最终RSS 101.0MiB。

new八批算术平均P95 24.93ms，吞吐 219.7req/s，最终RSS 96.8MiB。

测量期间未跑浏览器/业务写入测试，但后台基础容器仍存在；未改MySQL全局设置。只读计数已验证减少查询，未假称完成生产慢查询日志分析。冷缓存、真实大内容、生产Tunnel延迟和任意高并发容量仍需单独测量。原benchmark增强为仅允许localhost目标，支持归档路由；不支持直接对公网压测。

### 部署与回滚依赖

部署应使用本分支最终完整提交，不单独部署P0初版：评论CSS补正与宏去重必须一起；SEO依赖P0公开地址helper。回滚整体优化应在隔离副本从最新到最旧逆序revert整组提交，跑完整回归，再发布已验证回滚版本。不能任意单独revert c0338b1（将隐藏去重后的列表），也不能在SEO仍在时删除site_url.py。若只退某功能，创建有针对性的补丁并验证其依赖，不能把小提交误作互不依赖的部署单元。所有代码回滚保留生产现有DB/uploads/密码。

### 设置渲染补充

复查Option设置路径确认site_favicon保存和缓存刷新正常，但head错误读取site_logo，导致已有Favicon设置无效。最小修改优先site_favicon，未设置时保留site_logo/原favicon.ico回退。后台字段/DB语义不变，新增真实后台保存→数据库值→下一次页面link rel=icon的回归。该变化只影响浏览器标签图标，不改变页面布局；代码前后href来源差异及测试断言是对比证据。现有OptionCache单Worker刷新机制保留，未增加跨进程缓存服务。

## 交付与阶段记录

远端main核对仍为0c9128b，当前优化基于它；新分支optimization/phase2，不修改生产或自动合并main。

| 提交 | 范围 | 主要修改文件 |
|---|---|---|
| c029c00 | P0地址/页脚/评论DOM | config.py、site_url.py、views.py、post.html、footer.html、env样例、回归测试/P0证据 |
| 7e8dc23 | P1遗留缺陷与摘要 | public.py、auth.py、posts.py、views.py、index.html、admin/layout、config/env、兼容断言与P1证据 |
| e21331d | 查询/内容缓存 | blog.py、views.py、posts.py、批量等价及缓存测试、查询/性能证据 |
| c0338b1 | 原生评论CSS补正/PAGE去重 | comment.css、page.html、资产新旧哈希、文章/PAGE回归 |
| 70d504f | 用户要求SEO/资源策略 | public.py、views.py、site_url.py、static_cache.py、main.py、head/index/admin/login/评论头像、SEO/缓存回归 |
| 1958093 | 已有Favicon设置恢复 | head.html、设置保存/缓存到模板回归 |
| 后续维护交付提交 | 生产维护与最终证据 | production-maintenance.md、production_backup.sh、systemd示例、测试/浏览器/性能脚本、80图索引、完整报告、Git隐私忽略和交付manifest |

这些小提交用于代码审查，最终依赖组合已经验证。部署/回滚遵循上节依赖说明。完整测试仍有1条原Starlette/httpx弃用警告；没有隐藏失败、跳过原测试、修改依赖锁或MySQL Schema。生产自动测试、部署、restart和数据恢复均未执行。高风险方案需另行批准，未把全部待办冒充已完成。
