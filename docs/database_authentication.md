# MSSQL账户、设备绑定与诊断日志

## 重要说明

VS Code 的 MSSQL 插件只是数据库查看与执行 SQL 的客户端，不会自动安装 SQL Server、ODBC Driver 或 Python 的 `pyodbc`。本机仍需有可连接的 SQL Server 数据库。

密码不会以明文写入数据库。`netdiag_users` 保存账号原文、随机盐、PBKDF2-SHA256摘要和摘要方案；因此数据库中的密码字段与用户输入不应相同。账号、诊断报告和 JSON 日志使用 SQL Server `NVARCHAR` 保存 Unicode 内容。

“一个设备一个账号”使用 IP、浏览器标识、语言、平台、时区和服务端 Secret 计算不可逆 HMAC 指纹，并由数据库唯一约束限制。浏览器隐私策略不允许网页读取真实硬件序列号，所以它是演示级设备绑定：网络、浏览器或时区变化可能改变指纹，共享出口和相同浏览器环境也可能碰撞。

## 本地配置

1. 安装 Microsoft ODBC Driver 18 for SQL Server。
2. 在 VS Code MSSQL 插件中连接 SQL Server。
3. 执行 `scripts/mssql_schema.sql`，或让应用账号拥有建表权限，由应用首次连接时自动建表。
4. 在项目根目录 `.env` 增加 `.env.example` 中的 `MSSQL_*` 和 `AUTH_DEVICE_SECRET` 配置。
5. Windows 集成认证可设置 `MSSQL_TRUSTED_CONNECTION=true`，此时用户名和密码可以留空；云端部署应使用可远程访问的 SQL Server 与 SQL 身份验证。

`AUTH_DEVICE_SECRET` 至少24个字符，应使用随机值，不能提交到仓库。更换它会让已有设备指纹失效。

## 表

- `dbo.netdiag_users`：账号、密码摘要、设备摘要、创建与最后登录时间。
- `dbo.netdiag_diagnosis_logs`：结果时间、账号、数据来源、模型、任务、工具记录、证据链、报告或错误摘要。

页面只向当前登录账号展示最近日志。数据库管理员可通过 MSSQL 插件查询完整记录。
