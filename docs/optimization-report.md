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
