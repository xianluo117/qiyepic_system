# Docker Compose 部署说明

## 文件用途

- `../../Dockerfile`：构建统一应用镜像；
- `../../compose.yaml`：编排 Web、API、Worker、MySQL 和 Redis；
- `docker/nginx.conf`：应用镜像中 Web 容器使用的 Nginx 配置；
- `systemd/`：旧版 Linux 原生部署模板，仅供迁移参考；
- `nginx/`：旧版宿主机 Nginx 静态托管模板，仅供迁移参考。

当前推荐使用 Docker Compose，不再要求安装 Python venv 或配置 FastAPI/Celery systemd 服务。

## 启动

在项目根目录创建 `.env` 后执行：

```text
docker compose up -d
```

默认 Web 端口：

```text
1230
```

宝塔中可创建普通 Nginx 网站并反向代理到：

```text
http://127.0.0.1:1230
```

HTTPS 证书由宝塔网站管理。

## 数据

- 图片：通过 `IMAGE_DATA_PATH` 映射到 Linux 本地目录；
- MySQL：使用 Docker Volume `mysql-data`；
- Redis：使用 Docker Volume `redis-data`。

停止服务时使用：

```text
docker compose down
```

不要附加 `-v`，否则数据库数据卷会被删除。

## COS 故障本地兜底升级

本次更新需同时更新 API、Worker 和独立同步服务，不能只替换 API。使用项目根目录的 [compose.yaml](../compose.yaml) 执行：

```text
docker compose up -d --build
```

API 启动时自动执行数据库迁移；独立同步服务等待 API 健康后启动，复用同一应用镜像、数据库和图片目录挂载，无需增加环境变量。

- COS 正常时直接写入云端；故障时新原图和处理图暂存共享图片目录。
- 同步服务每轮处理最多 50 个对象，间隔 60 秒继续扫描；恢复后自动补传原路径并清理副本。
- 不备份历史云端图库。没有本地副本的历史图片在 COS 故障期间仍无法读取。
- COS 中已同步的原图、处理图和历史版本通过短期签名地址跳转，图片正文不经过 API，可减少服务器出网；本地待上传对象仍由 API 提供。
- 需要在 COS 桶配置前端实际来源的跨域规则，允许 GET/HEAD 及预检所需请求头，不启用跨域凭据，否则前端脚本下载可能被浏览器拦截。
- 本地存储模式不执行云端同步。
- 三个服务必须运行在同一宿主机并挂载同一持久化图片目录；不要在待同步期间清空或更换该目录。

查看运行状态：

```text
docker compose ps
docker compose logs --tail=100 storage-sync
```

本次仅完成代码与本地回归，未执行线上升级或真实 COS 故障演练。
