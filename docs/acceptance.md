# 迁移验收与测试报告

> 本文保留第一阶段迁移基线。第二阶段已修复的状态码、摘要、JS、图标与SEO行为以 [optimization-report.md](optimization-report.md) 为准。生产更新见 [production-maintenance.md](production-maintenance.md)。

审计基线：`UKennLi/MyBlog-butterfly` master `5f7353824b80e68e492253dac2ef84006d911908`。新项目是独立目录，不改原有 Java/Thymeleaf/CSS/JS 文件，不操作现有部署或生产数据。本文描述已执行证据与覆盖边界，不把写完代码等同于无限条件下等价。

## 功能验收

| 项目 | 新实现 | 已执行结果 |
|---|---|---|
| 首页、文章、独立PAGE、分类、标签、搜索、归档 | public Router / Repository / Jinja2 | 真实MySQL读取与基线状态对照通过 |
| 侧栏、分类/标签统计、导航、SEO | views / 原模板 | 规范化DOM对比，元数据随DOM检查 |
| 文章新增、编辑、摘要、封面、slug、标签 | PostService + 事务 | 保存/更新/唯一与长度约束/失败回滚通过 |
| 草稿与两段删除 | 原状态规则/关系清理 | 通过，不级联删除评论或文件 |
| 关于编辑 | 原PAGE规则 | 有记录/无记录模型及保存通过 |
| Markdown、GFM tables、作者原HTML | markdown-it兼容渲染 | 10组与Java CommonMark实际输出完全一致；表格align已适配 |
| 评论提交、树、隐藏status、后台删除 | CommentService | 通过，包含嵌套、孤儿、转义和默认值 |
| 友情链接CRUD与团队排序 | catalog / Repository | 通过，缺值默认与更新规则保留 |
| 系统设置与缓存 | t_option / OptionCache | 通过，授权排除_csrf污染 |
| 登录、退出、BCrypt、CSRF、Session | auth / security | 通过，历史密码验证、会话旋转/撤销、403/302 |
| 个人资料、改密 | users | 通过，正常自身修改兼容，越权ID拒绝 |
| 上传与历史文件访问 | admin / uploaded | 通过，真实PNG、伪装HTML、后缀不符、超限、路径越界 |
| ZIP文章备份 | PostService.download | 解压正文、YAML、图片重写、文件名、缺失id通过 |
| 静态与框架错误行为 | main / middleware | 原568资源SHA256逐个一致；400/403/404/500及HEAD通过 |
| 分类/标签/审核能力边界 | 原实际源码 | 分类内部CRUD映射通过；未编造原不存在的HTTP接口；缺分类模板原500保留 |
| Emoji摘要UTF16边界 | 原Java/JDBC替代字符 | 新旧实际写入结果一致，加入真实MySQL回归测试 |

## 自动化和数据库

- `reports/pytest.txt`、`reports/pytest.xml`：**20 passed**；1条 Starlette TestClient httpx弃用提示，无测试失败。测试使用锁定httpx版本，后续依赖升级应一起验证。
- `reports/differential.json`：**35项新旧差分检查通过**，包括原服务实际状态/重定向、分页/绑定边界，以及保存前后业务字段、标签关联、评论、友链、设置、资料和错误密码。
- `reports/markdown-comparison.json`：10组原 Java CommonMark0.21/GFM 与新渲染HTML完全匹配。
- `reports/database-inspection.json`：8张表实际SHOW CREATE与记录数量；测试前后逐表定义一致（忽略自然增长的AUTO_INCREMENT计数），保留所有字段、NULL/default/index/collation，无外键新增。
- 测试账号仅具DML权限，DDL尝试被MySQL拒绝；应用不调用create_all、不运行DDL/migration。测试用UUID绑定到两个专用MySQL8.4实例，恢复原测试记录；现有端口3306数据库没有测试写入。
- 数据来源为原SQL公开seed及隔离场景数据，不是用户尚未提供的生产全量数据。任意生产历史内容/负载需上线前再核验。

## 视觉验收

实际 Chromium 渲染旧 Spring Boot8081与新FastAPI8082，桌面1440×900、移动390×844。使用真实登录会话和真实MySQL；对两边相同CDN响应、固定动画帧，截图禁用CSS动画。另比较JS关闭时的DOM（忽略SCRIPT、CSRF令牌、布尔属性及空白）。工具不修改实际页面资源。

机器可读结果和完整截图位于 `reports/visual/`。包括：

- 基线23页：主页、文章、关于、归档、友链、缺失文章、分类、搜索、后台全部实际页面、登录/失败提示和退出确认。
- 丰富数据桌面9页、移动5页：230字符标题、中文/Emoji/HTML特殊字符、本地图片、GFM对齐表格、第二页、分类/标签分页、嵌套评论/博主标识、后台编辑与评论。
- 空数据桌面8页：首页、归档、友链、文章/草稿/评论/友链后台及空关于编辑。

最终结果：**68/68规范化DOM一致，63/68组截图逐像素一致**；其余5组具体差异见 `reports/visual-summary.json`。原始GIF已确认会引入不同加载帧，比较脚本固定帧。部分长页面边缘阴影有小幅光栅化差异，不能声称所有截图逐像素完全一致。

**覆盖限制**：部分外部CDN/字体/API在云环境不可访问，脚本让两边得到同样失败响应；因此外部库成功加载时的全部动画/编辑器/鼠标悬停/弹窗交互还没有完整验证。原root JS本身错误默认保留。项目CSS/JS未改，表单业务经过真实HTTP验证，但这不能替代用户部署网络下完整交互验收。生产域名、HTTPS、任意浏览器和未提供的历史全量数据尚未验证。

## 性能实测

`reports/performance.json`：相同宿主机、原Java17单进程和新Python3.12单进程、独立同版本克隆MySQL8.4，使用相同公开小数据集和已有Session；每页面200请求/并发8，预热20，2轮反转顺序，3个典型页面，共2400请求。错误数均0。统计应用CPU/RSS、MySQL CPU/RSS及Questions/SELECT计数。

6个批次算术平均：旧服务P95 **39.3ms**、吞吐 **334.3 req/s**；新服务P95 **75.7ms**、吞吐 **149.7 req/s**。最后样本应用RSS旧 **568.1MiB**、新 **114.4MiB**。

这个实现内存占用较低，但当前小数据实测响应和吞吐弱于旧服务。没有用“Python重写”推出性能提升，也没有为跑分改变查询或业务。MySQL负载和每批CPU见JSON；种子数据、单机测试和平均值不代表生产容量或任意并发情况。

## 独立部署

- 固定Python镜像摘要；全部依赖版本锁，pip check通过。
- 当前云Docker构建的直接DNS失败，已从受信任PyPI下载锁定wheel，实际 `--network=none` 构建 `Dockerfile.offline` 成功，SHA256记录在reports。
- Docker镜像内没有Java或原仓库。实际Compose部署连接隔离原schema、持久化uploads/Session、非root启动、健康检查和真实登录/写入/上传/下载烟测，**20项容器烟测全部通过**，并在停止隔离旧Spring服务后执行；详细记录 `reports/deployment.json`。
- 普通在线Dockerfile保留正常联网安装方式；当前云环境未能完成它的直接在线安装，使用离线Dockerfile验证同一锁定依赖和应用。
- 生产HTTPS/代理配置和生产切换未执行。参见 `deployment.md` 的配置、备份、切换、保留新写入的回滚步骤。

## 已知兼容差异

1. 用户批准的恶意/越权修复：本人ID校验、拒绝isAdmin伪造/主动评论URL、图片格式内容验证、历史主动文件附件sandbox、同源评论跳转、匿名/admin登录跳转、避免_csrf写入配置。正常页面和业务数据结构不变。
2. Java与Python服务端Session内部不兼容，切换需要管理员重新登录；密码不变，Cookie字段和常规流程保留。
3. ZIP压缩字节/元数据时间、框架错误措辞和时间格式不能保证逐字节等同；HTTP状态和主要响应契约经过测试。
4. 配置缓存维持原单进程语义，默认且支持的部署为1 worker；启动清除会话以保持Java重启行为，不支持多worker滚动启动。SQLite Session只使用本机持久文件，未引入Redis或MySQL新表。
5. 原缺陷明确保留：root模板JS错误、icons1.11.3 404、缺分类模板500、login?logout 500、成功改密先到退出确认页。

代码迁移、已列功能测试和独立容器部署已完成。**严格的“所有生产数据、外部资源正常加载、所有浏览器交互和每个像素完全不变”验收尚不能宣告完成**，需要补足上述现场验证条件。本次未修改生产服务、未把实际数据库密码或会话密钥写入交付物。
