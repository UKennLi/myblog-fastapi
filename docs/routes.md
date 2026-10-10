# 路由审计

| 方法 | 路径 | 原Controller |
|---|---|---|
| GET | `/` | IndexController.java |
| GET | `/post/{slug}` | IndexController.java |
| GET | `/category/{slug}` | IndexController.java |
| GET | `/tag/{slug}` | IndexController.java |
| GET | `/archive` | IndexController.java |
| GET | `/search` | IndexController.java |
| GET | `/{slug}` | IndexController.java |
| GET | `/links` | IndexController.java |
| GET | `/admin` | AdminController.java |
| GET | `/admin/` | AdminController.java |
| GET | `/admin/index` | AdminController.java |
| GET | `/admin/about` | AdminController.java |
| POST | `/admin/about/save` | AdminController.java |
| GET | `/admin/posts` | AdminController.java |
| GET | `/admin/drafts` | AdminController.java |
| GET | `/admin/posts/new` | AdminController.java |
| POST | `/admin/posts/save` | AdminController.java |
| GET | `/admin/posts/edit/{id}` | AdminController.java |
| GET | `/admin/posts/download/{id}` | AdminController.java |
| POST | `/admin/posts/delete/{id}` | AdminController.java |
| POST | `/admin/drafts/delete/{id}` | AdminController.java |
| GET | `/admin/categories` | AdminController.java |
| GET | `/admin/comments` | AdminController.java |
| POST | `/admin/comments/delete/{id}` | AdminController.java |
| GET | `/admin/links` | AdminController.java |
| GET | `/admin/links/new` | AdminController.java |
| GET | `/admin/links/edit/{id}` | AdminController.java |
| POST | `/admin/links/save` | AdminController.java |
| POST | `/admin/links/delete/{id}` | AdminController.java |
| GET | `/admin/options` | AdminController.java |
| POST | `/admin/options/save` | AdminController.java |
| GET | `/admin/profile` | AdminController.java |
| POST | `/admin/profile/save` | AdminController.java |
| POST | `/admin/profile/password` | AdminController.java |
| POST | `/comment/submit` | CommentController.java |
| POST | `/admin/api/upload` | UploadController.java |

框架额外路径：GET/POST /login，POST /logout，GET /logout 原框架确认页，GET /default-ui.css，GET /error。/login?logout 原运行出现500（forward冲突），/admin/categories 已登录500（模板缺失）。缺失文章/分类/标签/PAGE返回404模板HTTP200；静态不存在为404；/search缺keyword400；数字绑定错误400；未知POST需先经过CSRF/权限过滤，最终405或404/错误处理。登录失败302/login?error；权限不足匿名页面请求302绝对/login；缺/错CSRF403；成功写入通常302。

POST表单字段及下载/上传格式见后续实现和`docs/backend-contract.md`；保留原page/size默认值(1/10)，archive size30。客户端不可由框架默认422替代原400。
