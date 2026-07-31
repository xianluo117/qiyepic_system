# 简易图床系统

## 项目说明

本项目是通过 Docker Compose 部署在 Linux 服务器上的内部图床系统。

系统按角色分为两个独立入口：员工登录后进入 `/gallery`，管理员登录后进入 `/admin/images`。管理员后台提供全部图片、账号管理和系统日志。

主要功能：

- 管理员创建、禁用员工账号；
- 管理员查看全部图片；
- 员工上传并查看自己的图片；
- Web 批量上传图片；
- 按目标比例居中裁剪；
- 裁剪后判断短边是否达到最小 px；
- 仅在不足时等比例放大并进行轻度清晰度增强；
- 原图和处理图保存到 Linux 本地目录；
- 图库筛选、下载、删除、失败原因查看和失败重试；
- 管理员查看登录、账号、图片操作和图片处理日志；
- 后续可增加 OSS、COS 或 S3 存储适配器。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Element Plus；
- 后端：Python、FastAPI、SQLAlchemy；
- 数据库：MySQL；
- 异步任务：Redis、Celery；
- 图片处理：Pillow；
- Web 服务：Nginx；
- 部署方式：Docker Compose；
- 应用镜像：`qingmiaoai/qiyeimagesystem`。

## 快速部署

服务器只需安装 Docker Engine 和 Docker Compose 插件，不需要单独安装 Python、Node.js、MySQL、Redis 或 venv。

复制环境变量示例：

```text
cp .env.example .env
```

修改 `.env` 中的以下必填项：

```text
SECRET_KEY
MYSQL_PASSWORD
MYSQL_ROOT_PASSWORD
BOOTSTRAP_ADMIN_USERNAME
BOOTSTRAP_ADMIN_PASSWORD
```

启动全部服务：

```text
docker compose up -d
```

默认访问地址：

```text
http://服务器IP:1230
```

查看服务状态和日志：

```text
docker compose ps
docker compose logs -f
```

更新应用：

```text
docker compose pull
docker compose up -d
```

停止服务：

```text
docker compose down
```

不要使用 `docker compose down -v`，否则会删除 MySQL 和 Redis 数据卷。

## 本地构建镜像

根目录的 `Dockerfile` 会同时完成：

1. 安装 Node.js 前端依赖；
2. 构建 Vue 静态文件；
3. 安装 Python 后端依赖；
4. 打包 FastAPI、Celery 和 Nginx 运行环境。

构建并启动：

```text
docker compose up -d --build
```

API、Worker 和 Web 服务复用同一个应用镜像，通过不同启动参数运行。

## 项目结构

```text
image-system/
├── backend/                 # FastAPI、Celery 和图片处理
├── frontend/                # Vue 3 Web 前端
├── deploy/docker/           # 容器内 Nginx 配置
├── docs/                    # 项目说明文档
├── Dockerfile               # 应用多阶段构建文件
├── compose.yaml             # 完整服务编排
├── .dockerignore            # Docker 构建忽略规则
├── .env.example             # Docker Compose 环境变量示例
└── README.md
```

## 数据持久化

图片默认保存到宿主机：

```text
./data/images
```

可以通过 `.env` 修改：

```text
IMAGE_DATA_PATH=/data/image-system
```

MySQL 和 Redis 分别使用 Docker Volume：

```text
qiye-image-system_mysql-data
qiye-image-system_redis-data
```

部署前需要为图片目录和数据库数据制定备份策略。

## 图片目录

原图：

```text
员工ID/original/货号/原文件名
```

处理图：

```text
员工ID/processed/货号/原文件名
```

同一员工、同一货号下遇到同名文件时拒绝上传，不覆盖旧文件，也不自动重命名。

## 图片处理顺序

1. 读取原图并修正 EXIF 方向；
2. 按目标比例居中裁剪；
3. 获取裁剪后的宽度和高度；
4. 判断短边是否小于最小长度；
5. 短边达标时保持当前尺寸；
6. 短边不足时分阶段等比例放大；
7. 对放大结果进行轻度锐化；
8. 保存到 processed 目录。

详细运行和宝塔部署说明见 `docs/运行说明.md`。
