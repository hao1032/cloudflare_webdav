# Cloudflare R2 WebDAV Worker

一个用 Python 编写的 Cloudflare Worker，把 R2 Bucket 暴露为基础 WebDAV 存储。

## 功能

- 使用 R2 保存文件和目录占位对象。
- 支持 `OPTIONS`、`PROPFIND`、`GET`、`HEAD`、`PUT`、`DELETE`、`MKCOL`、`MOVE`、`COPY`。
- 可选 Basic Auth，通过 `WEBDAV_USERNAME` 和 `WEBDAV_PASSWORD` 配置。
- 目录使用 `path/.dir` 作为占位对象，因此空目录也能保留。
- 浏览器打开目录时显示文件列表。

## 部署

这份文档按 Cloudflare 网页后台部署说明。你需要一个 Cloudflare 账号、一个 GitHub 账号，以及这个项目的 GitHub 仓库。

## 1. 创建 R2 Bucket

1. 打开 Cloudflare Dashboard。
2. 进入「R2 Object Storage」。
3. 点击「Create bucket」。
4. 输入 bucket 名称，例如 `webdav`。
5. 点击创建。

如果希望预览环境和正式环境分开，可以再创建一个 bucket，例如 `webdav-preview`。不需要区分时，只创建 `webdav` 即可。

## 2. 创建 Worker 部署

1. 打开 Cloudflare Dashboard。
2. 进入「Workers & Pages」。
3. 点击「Create」或「Create application」。
4. 选择从 Git 仓库部署。
5. 连接 GitHub，并选择这个项目所在的仓库。
6. 选择 Worker 项目类型。

部署设置填写：

| 配置项 | 填写内容 |
| --- | --- |
| Project name | `cloudflare-r2-webdav`，或你自己的名称 |
| Build command | `npm run build` |
| Deploy command | `npm run deploy` |

如果网页只提供一个命令输入框，填写 `npm run deploy`。

## 3. 配置变量和 Secret

在 Worker 的部署设置或项目设置里找到「Variables and Secrets」或「Environment variables」。

添加这些变量：

| 变量 | 是否必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| `R2_BUCKET_NAME` | 必填 | `webdav` | 正式环境使用的 R2 Bucket |
| `WORKER_NAME` | 可选 | `webdav` | Worker 名称 |
| `R2_PREVIEW_BUCKET_NAME` | 可选 | `webdav-preview` | 预览环境使用的 R2 Bucket |
| `WEBDAV_USERNAME` | 可选 | `admin` | WebDAV 用户名 |
| `DEBUG_ERRORS` | 可选 | `1` | 临时诊断运行时报错；排查完成后请清空 |

添加这些 Secret：

| Secret | 是否必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| `WEBDAV_PASSWORD` | 可选 | `change-me` | WebDAV 密码 |

如果不设置 `WEBDAV_USERNAME` 和 `WEBDAV_PASSWORD`，服务将不需要登录即可访问。公开部署时建议设置用户名和密码。

## 4. 确认 R2 Binding

项目部署时会根据配置创建名为 `WEBDAV_BUCKET` 的 R2 binding。

如果 Cloudflare 页面要求手动配置 R2 binding，请这样填写：

| 配置项 | 填写内容 |
| --- | --- |
| Binding name | `WEBDAV_BUCKET` |
| R2 bucket | 选择你创建的 bucket，例如 `webdav` |

Binding name 必须是 `WEBDAV_BUCKET`，因为代码会用这个名字读取 R2。

## 5. 获取 WebDAV 地址

部署成功后，在 Worker 项目页面可以看到访问地址，通常类似：

```text
https://cloudflare-r2-webdav.your-account.workers.dev
```

这个地址就是 WebDAV 服务地址。如果你绑定了自己的域名，也可以使用自定义域名。

浏览器打开目录会显示文件列表；WebDAV 客户端使用 Worker 地址、`WEBDAV_USERNAME` 和 `WEBDAV_PASSWORD` 连接即可。

常见客户端：macOS Finder、Windows 网络驱动器、Cyberduck、Mountain Duck、RaiDrive、Infuse、Zotero，以及支持 WebDAV 的备份或同步软件。

## 使用示例

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

线上集成测试：

```bash
export WEBDAV_TEST_URL=https://your-worker.example.com/
export WEBDAV_USERNAME=admin
export WEBDAV_PASSWORD=change-me
npm run test:live
```

如果本机 Python 缺少 CA 证书导致测试报证书错误，可以临时加：

```bash
export WEBDAV_TEST_INSECURE=1
```

## 说明

- R2 是对象存储，不是原生文件系统；目录复制、移动和删除会逐个对象处理。
- 公开部署时建议设置 `WEBDAV_USERNAME` 和 `WEBDAV_PASSWORD`。
- `LOCK`/`UNLOCK` 用于兼容常见 WebDAV 客户端，目前不维护真实锁状态，不能作为强并发写入保护。
