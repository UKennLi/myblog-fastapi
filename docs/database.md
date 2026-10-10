# 既有数据库结构

数据库 myblog_db，MySQL8/InnoDB、utf8mb4_general_ci，8表。schema.sql 为原blog_init.sql中仅CREATE TABLE定义的审计副本，不会在应用启动执行。

| 表 | 关键字段/索引 |
|---|---|
| t_user | bigint自增id；username50 NOT NULL UNIQUE；password100 NOT NULL；nickname50/email100/avatar255；created DATETIME默认CURRENT_TIMESTAMP |
| t_category | bigint自增id；name50 NOT NULL；slug50 NOT NULL UNIQUE |
| t_post | bigint自增id；title255 NOT NULL；slug255 UNIQUE nullable；content/content_html LONGTEXT；summary500；thumbnail255；category_id bigint DEFAULT1 nullable；status20 DEFAULT PUBLISHED；type20 DEFAULT POST；created默认CURRENT_TIMESTAMP；modified同默认且ON UPDATE |
| t_tag | bigint自增id；name50 NOT NULL UNIQUE；slug50 NOT NULL UNIQUE |
| t_post_tag | 联合PK(post_id,tag_id)，bigint NOT NULL，没有外键 |
| t_comment | bigint自增id；post_id bigint NOT NULL索引；parent_id nullable索引；author50/email100/content TEXT NOT NULL；url200/ip50/user_agent500；status20默认APPROVED；is_admin tinyint1默认0；created默认时间 |
| t_option | option_key50 NOT NULL PK；option_value LONGTEXT nullable |
| t_link | bigint自增id；name50/url1024 NOT NULL；logo/description1024 nullable；team50默认Friends；sort INT默认0；created默认时间 |

SQL文件没有外键；保留软删除、孤儿评论/标签、category NULL等实际可能的数据。绝不自动补外键或关系约束。模型映射使用MySQL LONGTEXT/BIGINT/TINYINT及原列名，ORM声明不执行DDL。content_html虽然原Java未使用，Python仍映射且保存文章不覆盖它。数据库账号使用环境配置；生产只授予SELECT/INSERT/UPDATE/DELETE。

测试将在另两个本地MySQL容器的同名数据库上执行。既有开发数据库作为只读样本；对Schema指纹前后对比忽略AUTO_INCREMENT当前计数，保留所有类型、默认值、约束、索引、排序规则。正式切换不执行SQL初始化文件。
