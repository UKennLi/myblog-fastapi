# 原架构与目标架构审计

原项目：Java 17、Spring Boot 3.5.7、MyBatis 3.0.3、PageHelper 2.1.0、Thymeleaf、Spring Security BCrypt、CommonMark 0.21.0/GFM tables、MySQL Connector/J。31 个 Java 源文件，4 个 Controller、7 个 Service、7 个 Mapper、7 个 Entity、1 个 DTO、3 个 Config、入口和密码工具；无 Mapper XML、无独立前端构建、无原有部署定义。原测试仅 contextLoads。

Controller → Service/Mapper → MySQL；GlobalViewConfig 全局注入缓存中的 t_option；IndexController 注入分类/标签统计、最新五篇和固定导航。WebMvcConfig 以工作目录 upload 映射 /upload。SecurityConfig 使用服务端 Session、表单登录、所有已登录用户 ROLE_ADMIN、CSRF、SAMEORIGIN；没有角色表或注册接口。

Python：模块化单体，同步 SQLAlchemy 2/PyMySQL，以 FastAPI 同步路由线程池处理数据库与 BCrypt；Jinja2 复用已提取模板和所有原静态资源。Repository 参数化 SQL 保持 MyBatis 语义；Model 映射既有表，仅反映已有结构；不会 create_all/DDL/migration。Session 放在独立 SQLite 状态文件，不增加任何 MySQL 表，默认且支持单机一个worker；上传文件和Session存储文件独立持久化，启动会清除登录会话以匹配原Java重启行为。

审计包含实际 Controller/Service/Mapper/Entity/DTO/config/SQL/templates、原静态资源哈希和其 JS/CSS 引用。文件清单与 SHA-256 见 source-audit.json。基线源码保持不变，Python 项目独立。
