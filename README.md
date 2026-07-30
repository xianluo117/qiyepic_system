# 简易图床系统

## 项目说明

本项目是部署在 Linux 服务器上的内部图床系统。

首版功能：

- 管理员创建、禁用员工账号；
- 管理员查看全部图片；
- 员工上传并查看自己的图片；
- Web 批量上传图片；
- 按目标比例居中裁剪；
- 裁剪后判断短边是否达到最小 px；
- 仅在不足时等比例放大；
- 原图和处理图保存到 Linux 本地目录；
- 图库预览、筛选和下载；
- 后续可增加 OSS、COS 或 S3 存储适配器。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Element Plus；
- 后端：Python、FastAPI、SQLAlchemy；
- 数据库：MySQL；
- 异步任务：Redis、Celery；
- 图片处理：Pillow；
- Web 服务：Nginx；
- 进程管理：systemd；
- 部署方式：Linux 原生部署，不使用 Docker。

## 项目结构

```text
image-system/
├── backend/                 # FastAPI、Celery 和图片处理
├── frontend/                # Vue 3 Web 前端
├── deploy/                  # Nginx 与 systemd 配置
├── docs/                    # 项目说明文档
├── scripts/                 # 初始化和部署辅助脚本
├── .env.example             # 环境变量示例
└── README.md
```

## 图片目录

默认图片根目录：

```text
/data/image-system/
```

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
6. 短边不足时等比例放大；
7. 保存到 processed 目录。

## 当前状态

项目骨架正在建立中。详细设计见工作区中的整体方案文档。
