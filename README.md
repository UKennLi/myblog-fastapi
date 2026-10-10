# MyBlog-butterfly · FastAPI / MySQL

原项目 `UKennLi/MyBlog-butterfly` master `5f7353824b80e68e492253dac2ef84006d911908` 的实际后端迁移。Python 3.12、FastAPI、SQLAlchemy 2、PyMySQL、Jinja2；直接读取原有 8 张 MySQL 表，启动不执行任何 MySQL DDL。无需 Java、Spring Boot、Thymeleaf 或前端构建服务。

完整原始 CSS、JavaScript、图片复用。模板只替换动态渲染语法。页面由真实数据库查询渲染，后台表单直接写入同一数据结构。安全修复已获用户授权，仅改变恶意或越权请求。

## 本次交付下载

- [完整项目包（含截图和报告，约76 MiB）](artifacts/myblog-fastapi.zip)
- [离线依赖包（Python 3.12 / Linux x86_64，约22 MiB）](artifacts/myblog-fastapi-wheels.zip)
- [下载文件 SHA256](artifacts/myblog-fastapi.sha256)
- [启动与部署说明](docs/deployment.md)
- [完整验收报告](docs/acceptance.md)
- [逐页截图对照索引](reports/visual/index.html)

仓库根目录同时包含可直接运行的源码。ZIP保留已验证交付快照；真实环境密码、Session密钥和数据库运行文件不在仓库中。

## 本地启动

在本项目根目录执行，先准备原项目已有数据库的**测试副本**和上传文件副本：

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
pip check
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
# 编辑 .env：DB_HOST/PORT/NAME/USER/PASSWORD、SESSION_SECRET 和时区。
# 本地启动 DB_HOST 一般为 127.0.0.1；使用原库名称 myblog_db。
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

访问 `http://127.0.0.1:8000/`、`/login`、`/admin`。沿用已有用户和 BCrypt 密码；应用没有硬编码管理员密码，不创建用户，不重置数据。`.env` 不得提交。示例密钥和示例数据库密码必须替换。

MySQL 用户只需原 8 张表的 SELECT/INSERT/UPDATE/DELETE 权限。不要提供 DROP/ALTER/CREATE 权限。数据库不可用时启动失败，不会自动建库建表。`docs/schema.sql` 仅供审计；应用从不加载它。

`DB_TIMEZONE` 是原 JDBC 对 DATETIME 的解释时区，`DISPLAY_TIMEZONE` 应匹配旧 JVM 时区。本环境旧服务使用 Asia/Shanghai → UTC。生产必须核对旧服务实际配置，避免显示日期错位。

## Docker / Compose

```bash
cp .env.example .env
# 设置真实配置。容器连接宿主机 MySQL 可用 host.docker.internal。
# 把原项目 uploads 内容复制到 ./uploads，允许容器 UID 1000 写入。
mkdir -p uploads
sudo chown -R 1000:1000 uploads
docker compose up -d --build
docker compose ps
```

Compose 只部署博客，连接**已有 MySQL**；不会启动初始化数据库、执行 migration、删除数据。上传目录为宿主机 `./uploads`，Session 存储使用 `sessions` 持久卷；登录会话按原Java行为在应用重启时失效。健康检查会实际读取首页；监听地址默认 `127.0.0.1:8000`，可接反向代理。Docker 镜像使用固定 Python 3.12 镜像摘要和完整版本锁。

云构建环境 DNS 受限时，可先在可联网的 Python 3.12 Linux x86_64 环境下载 wheel，再离线构建（不要使用不同平台 wheel）：

```bash
mkdir -p .build-wheels
pip download --only-binary=:all: -r requirements.lock -d .build-wheels
docker build --network=none -f Dockerfile.offline -t myblog-fastapi:1.0.0 .
docker compose up -d --no-build
```

本次已实际验证该离线镜像安装、`pip check`、非 root 运行、健康检查及业务请求。首次下载基础镜像需要网络。交付源码包不包含 wheel 缓存，随附 myblog-fastapi-wheels.zip 可解压到项目根目录得到 .build-wheels（Linux x86_64/Python3.12专用）。

## 目录

```text
app/
  core/             配置、BCrypt、CSRF、服务端 Session、安全中间件
  db/               MySQL 连接池和事务 Session
  models/           原有 8 表 SQLAlchemy 映射（不执行 DDL）
  schemas/          原有表单绑定
  routers/          公开页面、后台表单、认证
  services/         文章、Markdown、评论树、配置缓存、视图
  repositories/     原 MyBatis SQL 的参数化实现
  dependencies/     请求级数据库依赖
 templates/         Jinja2 页面、布局、递归评论宏
 static/            原 CSS/JS/图片及原 WebJar 资源
 uploads/           原仓库上传文件，生产替换为历史上传副本
 tests/             真实 MySQL 集成测试、公开 demo seed
 scripts/           只读审计、明确隔离的测试初始化、基线/视觉/性能比较
 docs/              审计、契约、部署、切换和验收
 reports/           已执行测试、截图和机器可读结果
```

## 测试与复现

功能测试会写入并恢复测试记录，**只能使用专用一次性 MySQL 实例**，不得把 `.env` 指向生产。测试要求明确声明实例 UUID，并拒绝其他实例：

```bash
# .env.test 配置专用测试 MySQL，须已有原 schema 和公开 seed。
export MIGRATION_ENV_FILE=.env.test
export TEST_DATABASE_IS_DISPOSABLE=1
export TEST_MYSQL_SERVER_UUID='专用实例的 SELECT @@server_uuid 结果'
python -m pytest -q --junitxml=reports/pytest.xml
python -m scripts.inspect_database --env-file .env.test
```

如需全新 demo 数据库，`python -m scripts.init_test_database --env-file .env.test-admin --server-uuid UUID --disposable` 只允许明确指定实例上**尚不存在**的数据库；存在即拒绝，绝不 DROP/重置。这个一次性 CLI 与应用启动完全分离。初始化后把测试连接切换为 DML 权限账号。公开 seed 的测试用户仅供隔离环境；生产沿用原用户。

新旧差分测试使用两个隔离实例（默认 3307/3308），原服务 8081、新服务 8082。只对它们写入，随后用 DML 恢复原记录；自增计数自然增长，不重置：

```bash
python scripts/differential.py --env-file .env.test --old-uuid OLD_UUID --new-uuid NEW_UUID --disposable
```

视觉测试额外安装 `requirements.visual.txt` 并安装 Chromium，默认原服务 8081/新服务 8082。真实登录后比较页面：

```bash
pip install -r requirements.visual.txt
playwright install chromium
CHROMIUM_PATH=/usr/bin/chromium python scripts/browser_compare.py
VISUAL_WIDTH=390 VISUAL_HEIGHT=844 VISUAL_PREFIX=mobile python scripts/browser_compare.py
python scripts/scenario_visual.py --env-file .env.test --old-uuid OLD_UUID --new-uuid NEW_UUID --disposable --browser-python python
```

视觉和功能测试不要并行运行于相同数据库。视觉比较规范化 CSRF、属性空白、布尔属性，排除 SCRIPT 节点；截图使用 JS 开启的浏览器，另取 JS 关闭的 DOM。两边 CDN 返回相同响应、动画固定帧，只用于比较，不修改页面。CDN不可访问的交互、任意生产数据和浏览器需按验收报告继续验证。

性能比较：`python scripts/benchmark.py --old http://127.0.0.1:8081 --new http://127.0.0.1:8082 --old-pid JVM_PID --new-pid UVICORN_PID`。仅在隔离测试服务上执行。

## 兼容边界与维护

实际源码没有评论审核 HTTP 接口，也没有分类增删改管理路由；原 `/admin/categories` 引用不存在的模板，会返回 500，本次保留。没有注册、角色管理或新 REST API。原图标错误版本路径、`/login?logout` 的错误响应、改密跳转到退出确认页等也保留。详见 [功能清单](docs/feature-inventory.md)、[路由契约](docs/backend-contract.md)、[兼容风险](docs/compatibility-risks.md)。

`LEGACY_TEMPLATE_JS=true` 保留原模板 root 变量的错误 JavaScript，以保持原交互行为。设为 false 会显式修复这项旧缺陷，**属于另一个功能修复决定，不是默认迁移行为**。

Session 独立保存在 SQLite 文件，未向 MySQL 增加表。默认单worker；启动会清除旧登录，匹配原Java重启语义。多worker启动会影响其他worker会话，不作为受支持部署；多宿主机不可共享WAL文件。配置缓存按原设计为进程内缓存，默认运行一个 worker。升级时先在测试副本验证，再替换应用，不运行 schema migration。

[部署、HTTPS、备份和回滚](docs/deployment.md) · [逐项验收及测试限制](docs/acceptance.md) · [Java→Python 对应](docs/migration-map.md)
