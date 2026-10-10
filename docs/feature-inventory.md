# 源码功能清单

| 功能 | 实际规则 | 原实现 |
|---|---|---|
| 首页/分类/标签/搜索 | POST+PUBLISHED，created DESC；搜索使用 SQL LIKE 保留通配符语义；PageHelper 分页 | IndexController/PostMapper |
| 文章详情 | slug 仅匹配已发布 POST；缺失显示404模板但 HTTP200 | PostService |
| 独立页面 | PAGE，不额外限制status；Markdown转HTML | IndexController.page |
| 归档 | 只取已发布 POST 的部分字段；默认30条 | PostMapper.findArchives |
| 侧栏统计 | 分类COUNT包含全部文章/页面/草稿；标签COUNT全部关联；最新5篇 | CategoryMapper/TagMapper |
| 前台友链 | team按MAX(sort) DESC，组内sort DESC/id ASC | LinkMapper |
| 认证 | BCrypt2a/2b/2y，全部合法用户为管理员；成功固定/admin；退出/ | UserDetailsService/SecurityConfig |
| 文章保存 | 缺失摘要删除特定Markdown字符截取150个Java UTF-16字符；缺slug毫秒；首个MD/HTML图片作封面；默认POST/PUBLISHED | PostService.saveOrUpdate |
| 文章编辑 | UPDATE不会改变type或content_html；不强制更新created | PostMapper.update |
| 标签 | 中英文逗号分割、trim，name=slug；覆盖文章关联、重复关联忽略；空串清空，缺字段不改 | PostService.updateTagsForPost |
| 草稿 | 删除已发布文章是移入DRAFT；草稿删除同时删除标签关联，不删除评论或图片 | AdminController/PostService |
| 文章下载 | ZIP含YAML前言Markdown；仅重写MD中/upload/图片；带入存在的图片；不存在id返回空200；按id查询不加载category，所以原下载无分类前言 | PostService.downloadPost |
| 关于管理 | 找不到返回未保存空PAGE模型；保存强制PAGE/about/PUBLISHED；已有记录UPDATE不改type | PostService.getAboutPage |
| 评论 | 默认APPROVED/非博主；支持传入status；邮箱NOT NULL；构建树、孤儿评论不作根显示；删除父评论不删子评论；空邮箱Gravatar值为空串 | CommentService/CommentMapper |
| 评论审核 | 没有HTTP审核接口，仅数据库status字段和提交绑定；不得编造新管理页面 | 实际源码 |
| 分类维护 | Service/Mapper有增改删方法，唯一GET/admin/categories引用缺失模板；没有维护HTTP提交接口 | CategoryService/AdminController |
| 友链维护 | 新记录缺sort=0，空team=Friends；更新不套用默认值 | LinkService |
| 配置 | 原来接受所有表单键，包括_csrf；upsert，缓存刷新 | OptionService |
| 个人资料/密码 | 基于id更新，不增加用户/注册；密码使用BCrypt10；成功改密redirect:/logout | UserService |
| 上传 | editormd-image-file，UUID+原后缀，不检查内容/扩展名；空文件success0；10MiB限制 | UploadController |
| 静态 | butterfly/plugins/upload/default-ui/webjars；图标1.11.3路径原404，实际库1.13.1 | WebMvcConfig/SecurityConfig |

不存在独立分类/标签管理CRUD路由、评论审核按钮、注册、角色管理、RSS、站点地图、额外REST API。不要把README愿景作为现有功能。底层类别与用户查询方法仍提供Python对应实现供原有服务使用。
