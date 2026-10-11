# 兼容性风险与决策

> 本文保留第一阶段迁移基线。第二阶段已修复的状态码、摘要、JS、图标与SEO行为以 [optimization-report.md](optimization-report.md) 为准。生产更新见 [production-maintenance.md](production-maintenance.md)。

1. 原源码profile/password按请求id操作存在IDOR；公开评论可绑定isAdmin；上传任何后缀可造成主动内容XSS。用户已明确批准修复恶意/越权请求，正常UI/数据结构不变；差异在契约与测试中列明。
2. MySQL既有BCrypt哈希继续可用；不更改用户密码。Java JSESSIONID内存Session不能转移；切换需重新登录，Cookie名/表单字段保持，sqlite服务端Session独立持久化。
3. Spring默认_csrf为XOR masking，需接受同等表单/头，403优先于登录跳转；成功登录旋转Session防固定攻击。框架生成的HTML登录/退出页需提取。
4. raw Markdown HTML原样支持，兼容已有可信作者HTML；不擅自sanitize改变排版。匿名评论输出仍HTML转义；主动评论URL和upload已按授权加固。
5. 原输入校验少，必须区别SQL约束错误500、数字绑定400、缺参数400、框架路由405；不让FastAPI422泄漏为默认外部行为。
6. 原模板root双重引号导致JS错误、后台图标版本路径404、缺category模板500、login?logout forward500、改密成功GET/logout不是实际注销。保留缺陷基线并记录；不得把修复混进技术迁移。已提取模板的root语法曾修正，本次将提供原渲染兼容值/明确处理。
7. JDBC serverTimezone=Asia/Shanghai解释DATETIME，JVM默认UTC导致原页面减8小时；用DB_TIMEZONE/DISPLAY_TIMEZONE显式匹配。生产需按原JVM时区配置，不可简单复制测试的UTC。
8. PageHelper page0/size0、超过页数、导航页码需跑基线；MySQL ORDER BY时间相同无稳定secondary key，保留同样SQL而非擅自增加id排序。
9. 备份ZIP保留id标题清理、URLEncoder空格+、标签顺序、图片仅MD/upload/，created前言来自JDBC显示时间；ZIP元数据时间/压缩实现差异单独记录。
10. 原OptionService保存_csrf污染设置、缓存进程间失效；业务设置仍读同表，不新增表，必要差异明确记入测试报告。
11. 原文章删除非事务，保存文章有事务；Python保证保存正文和标签同一事务，不删除额外数据。数据库启动绝不执行初始化/Schema变更。
12. 视觉比较只能对已执行数据/视口/资源可访问条件声明一致；CDN不可访问、动画帧、浏览器字体和任意历史HTML仍需部署前核验，不声称无限范围像素一致。

用户已批准：修复恶意/越权请求，不改变正常UI与数据库结构。已实施：profile/password自身ID校验；拒绝访客isAdmin=true；只接受六种真实图片并校验扩展名/内容、上传上限；历史主动内容附件+sandbox；不保存_csrf设置；匿名/admin改为登录跳转；跨源评论Referer回退首页。其他原缺陷按兼容模式保留。

追加：拒绝访客javascript/data/vbscript网址；历史主动网址只在视图中清空，不修改记录。错误页框架名称/措辞、ZIP压缩字节和Session内部格式属于框架差异；HTTP状态、主要字段及正常页面维持契约。当前单worker配置避免原进程缓存跨worker失效，SQLite Session要求本机持久文件，不作为多机共享存储。
