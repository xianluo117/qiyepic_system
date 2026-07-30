# 后端模块说明

```text
app/
├── api/          # FastAPI 路由
├── core/         # 配置与数据库
├── models/       # SQLAlchemy 模型
├── processing/   # 图片裁剪与缩放
└── storage/      # 本地存储及未来对象存储接口

worker/
└── tasks/        # Celery 图片处理任务

migrations/       # Alembic 数据库迁移
requirements.txt      # 生产运行依赖
requirements-dev.txt  # 测试和代码检查依赖
```

安装生产依赖：

```text
python -m pip install -r requirements.txt
```

开发和测试环境安装：

```text
python -m pip install -r requirements-dev.txt
```

运行前必须提供环境变量配置。
