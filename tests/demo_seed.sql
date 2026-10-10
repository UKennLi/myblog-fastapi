-- Disposable demo database only. Original public seed data.
INSERT INTO `t_user` (`username`, `password`, `nickname`, `avatar`, `created`) VALUES 
('riuken', '$2a$10$13qonQ73g1Mrs4s2QGCbM.aBNRmfaRIG9qU1YD1omCTXS/sbEK3nC', 'Riuken', '/butterfly/img/avatar.jpg', NOW());

-- 3.2 初始化分类
INSERT INTO `t_category` (`id`, `name`, `slug`) VALUES 
(1, '默认分类', 'default'),
(2, '编程随想', 'dev-think'),
(3, '生活随笔', 'life');

-- 3.3 初始化系统配置
INSERT INTO `t_option` (`option_key`, `option_value`) VALUES
('site_title', '我的 Spring Boot 博客'),
('site_description', '这是一个从零开发的 Java 全栈博客'),
('site_logo', '/butterfly/img/logo.png'),
('author_name', 'Riuken'),
('author_avatar', '/butterfly/img/avatar.jpg'),
('author_description', '热爱技术，热爱生活'),
('icp_beian', '');

-- 3.4 初始化独立页面 (关于我)
INSERT INTO `t_post` (`title`, `slug`, `content`, `type`, `status`, `created`) VALUES 
('关于我', 'about', '## 大家好\n我是个热爱 Java 的全栈开发者。', 'PAGE', 'PUBLISHED', NOW());

-- 3.5 初始化测试文章
INSERT INTO `t_post` (`title`, `slug`, `summary`, `content`, `thumbnail`, `category_id`, `created`) VALUES
('第一篇来自数据库的文章', 'hello-world', '这是我的第一篇真实文章，它现在存储在 MySQL 数据库中！', '# 你好，世界！\n这是正文内容。', 'https://s2.loli.net/2023/01/18/bIJTVaR3MLPzcZ7.jpg', 1, NOW()),
('Spring Boot 真好用', 'springboot-is-good', 'Spring Boot 极大地简化了 Java Web 开发。', '## 为什么选择 Spring Boot\n因为它快。', NULL, 2, NOW());

-- 3.6 初始化友情链接
INSERT INTO `t_link` (`name`, `url`, `logo`, `description`, `team`, `sort`) VALUES
('Typecho', 'http://typecho.org', 'https://typecho.org/usr/themes/default/img/logo.png', 'Typecho官方网站', 'Official', 100),
('Spring Boot', 'https://spring.io/projects/spring-boot', 'https://spring.io/images/spring-logo-9146a4d3298760c2e7e4cd59a5a8bd84.svg', 'Spring Boot官方文档', 'Official', 90),
('WeHao', 'https://github.com/wehaox', 'https://avatars.githubusercontent.com/u/1?v=4', '本主题原作者', 'Friends', 0);