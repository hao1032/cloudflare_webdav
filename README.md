# Cloudflare R2 WebDAV Worker

一个用 Python 编写的 Cloudflare Worker，把 R2 Bucket 暴露为基础 WebDAV 存储。

## 功能

- 使用 R2 保存文件和目录占位对象。
- 支持 `OPTIONS`、`PROPFIND`、`GET`、`HEAD`、`PUT`、`DELETE`、`MKCOL`、`MOVE`、`COPY`。
- 可选 Basic Auth，通过 `WEBDAV_USERNAME` 和 `WEBDAV_PASSWORD` 配置。
- 目录使用 `path/.dir` 作为占位对象，因此空目录也能保留。

部署和使用说明见 [docs/USAGE.md](docs/USAGE.md)。

## 准备

安装 Wrangler：

```bash
npm install
```

创建 R2 Bucket：

```bash
npx wrangler r2 bucket create webdav
npx wrangler r2 bucket create webdav-preview
```

通过环境变量生成 `wrangler.toml`：

```bash
export R2_BUCKET_NAME=webdav
export R2_PREVIEW_BUCKET_NAME=webdav-preview
export WEBDAV_USERNAME=admin
export WEBDAV_PASSWORD=change-me
npm run render:wrangler
```

`R2_BUCKET_NAME` 是必填项。`R2_PREVIEW_BUCKET_NAME` 可选；不设置时会和 `R2_BUCKET_NAME` 使用同一个 bucket。

`WEBDAV_USERNAME` 和 `WEBDAV_PASSWORD` 可选；两个都为空时不启用认证。

## 本地开发

```bash
npm run dev
```

`npm run dev` 会先读取环境变量并重新生成 `wrangler.toml`。

## 部署

```bash
npm run deploy
```

`npm run deploy` 同样会先读取环境变量并重新生成 `wrangler.toml`。

部署后可以用 WebDAV 客户端连接 Worker URL。示例：

```bash
curl -u "$WEBDAV_USERNAME:$WEBDAV_PASSWORD" -X MKCOL https://your-worker.example.com/docs
curl -u "$WEBDAV_USERNAME:$WEBDAV_PASSWORD" -T ./hello.txt https://your-worker.example.com/docs/hello.txt
curl -u "$WEBDAV_USERNAME:$WEBDAV_PASSWORD" https://your-worker.example.com/docs/hello.txt
```

## 测试

```bash
npm run check
npm test
```

## 说明

R2 是对象存储，不是原生文件系统，所以 `MOVE` 和 `COPY` 对目录会逐个对象复制。大目录操作可能比较慢，也可能受到 Worker 执行时间限制。这个项目适合作为个人 WebDAV、备份入口或小规模文件同步服务的基础版本。
