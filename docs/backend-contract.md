# HTTP 与数据契约

> 本文保留第一阶段迁移基线。第二阶段已修复的状态码、摘要、JS、图标与SEO行为以 [optimization-report.md](optimization-report.md) 为准。生产更新见 [production-maintenance.md](production-maintenance.md)。

完整路径清单见 `routes.md`，以下参数和规则来自实际 Controller/Service/Mapper。GET 支持 HEAD：相同状态和响应头，空响应体。模板错误返回 500；参数绑定失败 400，SQL 非空/唯一/长度约束错误 500。错误 JSON 含 timestamp/status/error/path，HTML Accept 返回原 Whitelabel 结构；框架措辞、时间和序列化细节见兼容风险。

## 公共查询

| 路径 | 参数 | 数据与响应 |
|---|---|---|
| `/`、`/category/{slug}`、`/tag/{slug}` | page=1,size=10 | 已发布 POST，created DESC；缺类别/标签返回404模板HTTP200 |
| `/search` | 必需 keyword，page=1,size=10 | 标题或正文 SQL LIKE；保留 `%`、`_` 通配符；缺keyword400 |
| `/archive` | page=1,size=30 | 已发布 POST 部分字段、分页 |
| `/post/{slug}` | 路径字符串 | PUBLISHED+POST，实时CommonMark+GFM table；缺失404模板HTTP200 |
| `/{slug}` | 路径字符串 | PAGE；不限制status；缺失404模板HTTP200 |
| `/links` | 无 | 按团队MAX(sort)排序，组内sort DESC/id ASC |

page<=0或size<=0显示空列表；超出最后页为空。导航最多8页。相同created时间没有新增id排序，保留原 SQL 对并列记录的行为。

## 登录与会话

GET `/login` 和 `?error` 显示框架风格登录页。POST `/login` 使用 `username/password/_csrf`；缺/错CSRF403，密码不匹配302绝对`/login?error`，成功固定302绝对`/admin`。用户名按原表查询，不自动注册；所有合法用户具有后台权限。Cookie 名 JSESSIONID，Path=/，HttpOnly，默认未设置SameSite；生产HTTPS设置Secure。

Session 30分钟滑动过期，成功登录旋转令牌、注销使令牌失效。服务端SQLite存储仅用于Session，不改变博客MySQL。GET `/logout` 是确认页；POST `/logout` 成功302绝对`/`。`/login?logout` 原服务forward失败500，本次保留。原JavaSession不能转移。

CSRF 表单 `_csrf` 是 Spring XOR masking；`X-CSRF-TOKEN` 支持原始或masked令牌。安全过滤先验证CSRF，再判断是否登录。公开 `/comment/**`、后台 `/admin/api/**` 按原配置免CSRF，但后台上传仍要求登录。

## 后台写入

所有成功写入返回302绝对URL，接受原HTML表单字段，不新增JSON API。

| 方法/路径 | 表单 | 结果 |
|---|---|---|
| POST `/admin/posts/save` | id?,title,slug?,content,summary?,thumbnail?,categoryId?,status?,type?,tagsStr? | 保存正文+标签同事务；DRAFT→/admin/drafts，否则/admin/posts |
| POST `/admin/posts/delete/{id}` | _csrf | 移到DRAFT，→/admin/posts |
| POST `/admin/drafts/delete/{id}` | _csrf | 删除文章和标签关联，不删除评论/文件，→/admin/drafts |
| POST `/admin/about/save` | 同文章字段 | 强制PAGE/about/PUBLISHED，→/admin/about?success=true |
| POST `/admin/comments/delete/{id}` | _csrf | 删除一条，不递归删子评论，→/admin/comments |
| POST `/admin/links/save` | id?,name,url,logo?,description?,team?,sort? | 新记录默认sort0/teamFriends；更新不套默认，→/admin/links |
| POST `/admin/links/delete/{id}` | _csrf | 删除一条，→/admin/links |
| POST `/admin/options/save` | 任意设置键 | t_option upsert，刷新缓存，→/admin/options；_csrf不作为业务设置保存 |
| POST `/admin/profile/save` | id,username,nickname?,email?,avatar? | 只允许本人id；→/admin/profile?success=profile |
| POST `/admin/profile/password` | userId,oldPassword,newPassword | 只允许本人id；旧密码错→/admin/profile?error=password，成功→/logout确认页 |

编辑不更新 `type/content_html`，正文不为空时缺摘要使用 Java UTF-16 150字符规则；缺slug用毫秒；封面空时取首个Markdown/HTML图片；缺categoryId写NULL。tagsStr缺失不改关联，空串清空，逗号/中文逗号分割，重复关系忽略，孤立tag保留。关于页尚无记录时返回空PAGE模型但不写库。后台编辑不存在id原模板500，本次同状态。

原应用没有分类维护提交路由、标签维护页面或评论审核路由。分类Service CRUD继续映射供内部使用。原GET `/admin/categories`缺模板500，不把缺失功能冒充新实现。

## 评论

POST `/comment/submit`：`postId,parentId?,author,email,url?,content,status?,isAdmin?`。默认APPROVED、false。邮箱缺失触发原NOT NULL错误500，空串允许。APPROVED评论按时间ASC组树；孤儿不作根展示；status其他值保留并在后台可见。

成功302同源Referer，缺失或恶意外源退回首页。访客isAdmin=true及主动javascript/data/vbscript URL403。历史主动URL只在渲染时清空，不改数据库；评论正文/作者HTML转义，Markdown作者HTML继续兼容原行为。

## 图片上传与下载

POST `/admin/api/upload` 使用 multipart 字段 `editormd-image-file`。有效 jpg/jpeg/png/gif/bmp/webp 图片验证内容、后缀并采用UUID+原扩展名存入uploads，返回 `{success:1,message:"上传成功",url:"/upload/UUID.ext"}`。缺/空文件或无效图片返回success0消息，超过原10MiB请求上限413。拒绝主动内容是授权安全修复；旧上传仍可读取，但HTML/SVG/XML/JS附件加sandbox。

GET `/admin/posts/download/{id}` 为ZIP，`Content-Disposition` 使用Java URLEncoder风格（空格+）的 `id_标题.zip`，清理路径保留字符。包含YAML前言和Markdown，标签来自真实关联；原findById不加载category，所以前言不凭空新增分类。仅处理Markdown中的`/upload/`图片，存在的文件写入images目录并替换相对路径，缺失图片不阻断；不存在id空200。ZIP内部时间/压缩字节不要求与Java编码器相同，解压正文和路径应兼容。

静态路径保留 butterfly/plugins/upload/default-ui.css/webjars；原错误icons1.11.3请求404，实际1.13.1资源可用。匿名webjars路径仍走认证，与原Spring配置相同。
