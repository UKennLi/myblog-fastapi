# 可复现测试环境

测试必须分离生产。集成测试在每个用例开始前验证实例UUID和 `TEST_DATABASE_IS_DISPOSABLE=1`，捕获全部8表数据，用例结束用DML恢复；不重置AUTO_INCREMENT，不执行Schema操作。

此次实例：原服务测试克隆端口3307、FastAPI测试克隆3308；MySQL8.4镜像摘要 `sha256:6ea90827b1100f8f2ae306a539f86d2c264a26ed435a2a9f75551dd5c3aeb242`，公开原SQL seed。原已配置3306实例从未用于写入测试。原服务8081与新服务8082比较；Compose8000用于独立部署验证。每组写入检查串行执行，再运行浏览器，以免截图碰到临时测试数据。

`differential.py` 和 `scenario_visual.py` 都要求 `--disposable --old-uuid ... --new-uuid ...`，仅用于上述明确隔离的两个实例。脚本需要连接账号具有DML权限。中断写入测试可能导致测试副本暂时保留场景数据；不应把此类工具指向生产。

基线视觉比较的 TEST_ADMIN_USERNAME/TEST_ADMIN_PASSWORD 是**公开seed测试用户**，可通过环境变量替换。应用本身从未使用这两个测试环境变量，不包含自动管理员登录或预设密码。脚本的默认端口用于本次复现，可以按文件中说明调整。

锁定业务依赖与测试依赖均在requirements.lock，浏览器验证依赖独立requirements.visual.txt，不引入生产运行依赖。浏览器脚本需要Chromium，本次使用 `/usr/bin/chromium`；其它环境设置 CHROMIUM_PATH 指向已安装的浏览器。

容器独立部署测试：

```bash
python scripts/deployment_smoke.py --env-file .env.test --uuid TARGET_TEST_UUID --disposable --base http://127.0.0.1:8000 --container 实际测试Compose容器名
```

这个脚本会在隔离库创建测试文章/标签，上传PNG，验证ZIP，重启指定**测试容器**并验证会话失效和文件持久化，随后清理自己的记录和上传。不要对生产容器执行。

性能脚本是只读查询，SESSION Cookie依然会写入各服务自己的会话存储。应用CPU是 `/proc` CPU时间差/墙钟时间，RSS为批次前后样本（不是峰值）；MySQL CPU/RSS来自各专用实例进程，Questions等为该期间计数差。健康检查和其他后台请求可能对数据库计数带来微小影响。
