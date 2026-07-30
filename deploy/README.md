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
