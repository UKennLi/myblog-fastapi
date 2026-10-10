# 模块对应

| Java | Python |
|---|---|
| MyBlogButterflyApplication | app.main.create_app |
| IndexController | app.routers.public |
| AdminController | app.routers.admin |
| CommentController | app.routers.public.submit_comment |
| UploadController | app.routers.admin.upload |
| SecurityConfig/UserDetailsServiceImpl | app.core.security / app.services.users |
| GlobalViewConfig/OptionService | app.services.options / app.services.views |
| WebMvcConfig | app.main静态挂载及上传响应 |
| PostService | app.services.posts |
| CommentService | app.services.comments |
| LinkService/CategoryService/UserService | app.services.catalog / app.services.users |
| 所有7个Mapper | app.repositories.blog（按参数化原SQL），公开相应操作 |
| Entity/CategoryDto | app.models.tables映射与app.services.views字典 |
| PasswordGenerator | scripts.password_hash CLI(交互输入，不打印明文) |
| Thymeleaf | templates的Jinja继承/宏；保持原资源字节和DOM |
| contextLoads测试 | tests真实MySQL功能、路由、安全与Schema回归 |
