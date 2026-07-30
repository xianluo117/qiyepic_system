# Linux 部署文件说明

## systemd

- `image-system-api.service`：运行 FastAPI；
- `image-system-worker.service`：运行 Celery Worker。

安装时复制到：

```text
/etc/systemd/system/
```

然后重新加载 systemd 并启用服务。

## Nginx

`image-system.conf` 是站点配置模板。

Debian 或 Ubuntu 通常放置到：

```text
/etc/nginx/sites-available/image-system.conf
```

然后建立到 sites-enabled 的链接。

其他发行版可以放置到 Nginx 的 conf.d 目录。

生产环境需要根据实际域名增加 HTTPS 配置。
