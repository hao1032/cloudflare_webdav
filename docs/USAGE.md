# 网页部署和使用文档

这份文档面向只想通过 Cloudflare 网页后台部署和使用 WebDAV 服务的用户。

部署完成后，你会得到一个 WebDAV 地址，可以用 Finder、Windows 网络驱动器、移动端 WebDAV 客户端、备份软件或其他 WebDAV 客户端访问 R2 中的文件。

## 1. 准备

你需要：

- 一个 Cloudflare 账号
- 一个 GitHub 账号
- 这个项目的代码仓库

推荐先把本项目上传到 GitHub。后续 Cloudflare 可以直接从 GitHub 仓库自动部署。

## 2. 在网页创建 R2 Bucket

1. 打开 Cloudflare Dashboard。
2. 进入左侧菜单的「R2 Object Storage」。
3. 点击「Create bucket」。
4. 输入 bucket 名称，例如：

```text
webdav
```

5. 点击创建。

这个 bucket 会作为 WebDAV 的文件存储位置。

如果你希望预览环境和正式环境分开，可以再创建一个 bucket，例如：

```text
webdav-preview
```

不需要区分时，只创建 `webdav` 一个 bucket 即可。

## 3. 在网页创建 Worker 部署

1. 打开 Cloudflare Dashboard。
2. 进入「Workers & Pages」。
3. 点击「Create」或「Create application」。
4. 选择从 Git 仓库部署。
5. 连接 GitHub，并选择这个项目所在的仓库。
6. 选择 Worker 项目类型。

在部署设置里填写：

| 配置项 | 填写内容 |
| --- | --- |
| Project name | `cloudflare-r2-webdav`，也可以改成你喜欢的名字 |
| Build command | `npm run build` |
| Deploy command | `npm run deploy` |

如果网页只提供一个命令输入框，填写：

```text
npm run deploy
```

## 4. 在网页配置环境变量

在 Worker 的部署设置或项目设置里找到「Variables and Secrets」或「Environment variables」。

添加这些变量：

| 变量 | 是否必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| `WORKER_NAME` | 可选 | `webdav` | Worker 项目名称；建议和 Cloudflare 网页里的 Project name 一致 |
| `R2_BUCKET_NAME` | 必填 | `webdav` | 正式环境使用的 R2 Bucket |
| `R2_PREVIEW_BUCKET_NAME` | 可选 | `webdav-preview` | 预览环境使用的 R2 Bucket |
| `WEBDAV_USERNAME` | 可选 | `admin` | WebDAV 登录用户名 |
| `WEBDAV_PASSWORD` | 可选 | `change-me` | WebDAV 登录密码；正式部署请配置为 Wrangler secret |
| `DEBUG_ERRORS` | 可选 | `1` | 临时诊断运行时报错；排查完成后请清空 |

如果没有创建预览 bucket，可以不设置 `R2_PREVIEW_BUCKET_NAME`。

如果不设置 `WEBDAV_USERNAME` 和 `WEBDAV_PASSWORD`，服务将不需要登录即可访问。公开部署时建议设置用户名和密码。

为了避免密码写入生成的 `wrangler.toml`，正式部署请用 secret 设置密码：

```bash
npx wrangler secret put WEBDAV_PASSWORD
```

本地开发时可以在 `.dev.vars` 中写入：

```text
WEBDAV_PASSWORD=change-me
```

保存环境变量后，重新触发一次部署。

## 5. 确认 R2 Binding

项目部署时会根据环境变量生成 Worker 配置，并创建名为：

```text
WEBDAV_BUCKET
```

的 R2 binding。

如果你在 Cloudflare 网页中看到需要手动选择 R2 binding，请这样填写：

| 配置项 | 填写内容 |
| --- | --- |
| Binding name | `WEBDAV_BUCKET` |
| R2 bucket | 选择你创建的 bucket，例如 `webdav` |

Binding name 必须是 `WEBDAV_BUCKET`，因为代码会用这个名字读取 R2。

## 6. 获取 WebDAV 地址

部署成功后，在 Worker 项目页面可以看到访问地址，通常类似：

```text
https://cloudflare-r2-webdav.your-account.workers.dev
```

这个地址就是 WebDAV 服务地址。

如果你绑定了自己的域名，也可以使用自定义域名作为 WebDAV 地址。

在浏览器中打开这个地址时，会显示当前目录的文件列表。

## 7. 连接 WebDAV 客户端

连接信息：

- 服务器地址：Worker 部署后的访问地址
- 用户名：`WEBDAV_USERNAME`
- 密码：`WEBDAV_PASSWORD`

如果没有设置用户名和密码，客户端中也不需要填写登录信息。

### macOS Finder

1. 打开 Finder。
2. 点击顶部菜单「前往」。
3. 选择「连接服务器」。
4. 输入 Worker 地址。
5. 点击连接。
6. 按提示输入用户名和密码。

### Windows

1. 打开「此电脑」。
2. 选择「映射网络驱动器」。
3. 输入 Worker 地址。
4. 按提示输入用户名和密码。

### 常见 WebDAV 客户端

这些客户端通常可以直接连接：

- Cyberduck
- Mountain Duck
- RaiDrive
- Infuse
- Zotero
- 支持 WebDAV 的备份或同步软件

## 8. 日常使用

连接成功后，你可以像使用普通 WebDAV 网盘一样：

- 创建目录
- 上传文件
- 下载文件
- 删除文件
- 移动文件或目录
- 复制文件或目录

文件实际保存在你创建的 Cloudflare R2 Bucket 中。

## 9. 修改配置

如果要修改 WebDAV 用户名、密码或 bucket 名称：

1. 进入 Cloudflare Dashboard。
2. 打开对应 Worker 项目。
3. 进入环境变量设置。
4. 修改 `R2_BUCKET_NAME`、`WEBDAV_USERNAME` 或 `WEBDAV_PASSWORD`。
5. 保存后重新部署。

重新部署完成后，新配置会生效。

## 10. 注意事项

- R2 是对象存储，不是传统文件系统。
- 大目录复制或移动会逐个文件处理，文件很多时可能较慢。
- 删除目录会删除目录下的所有对象。
- 公开部署时建议设置 `WEBDAV_USERNAME` 和 `WEBDAV_PASSWORD`。
- 如果客户端提示认证失败，先检查 Worker 环境变量里的用户名和密码。
- 如果客户端提示找不到存储，检查 R2 bucket 名称和 `WEBDAV_BUCKET` binding。
- `LOCK`/`UNLOCK` 只提供客户端兼容响应，不维护真实锁状态，不能作为强并发写入保护。

## 11. 验证部署

如果你有项目代码，也可以对线上地址运行集成测试：

```bash
export WEBDAV_TEST_URL=https://wd.tangome.dpdns.org/
export WEBDAV_USERNAME=tango
export WEBDAV_PASSWORD=123
npm run test:live
```

如果本机 Python 缺少 CA 证书导致测试报证书错误，可以临时设置 `WEBDAV_TEST_INSECURE=1`。

测试会创建一个临时目录，执行上传、下载、复制、移动、删除等操作，最后清理测试目录。
