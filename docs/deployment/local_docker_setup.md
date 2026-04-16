# 本地 Docker 部署指南

本指南帮助你在本地使用 Docker 快速启动「信息获取助手」项目。

## 前置条件

- Windows 10/11 或 macOS 或 Linux
- Docker Desktop 已安装并运行
- PowerShell (Windows) 或 Terminal (macOS/Linux)
- Git (可选，用于克隆代码)

## 快速开始（5 分钟）

### 1. 准备环境文件

```powershell
# 进入项目目录
cd information_acquisition_assistant

# 复制环境变量模板
copy .env.example .env

# 编辑 .env 文件（使用记事本或 VS Code）
notepad .env
```

### 2. 配置环境变量（最小配置）

打开 `.env` 文件，确保以下必填项已配置：

```env
# 数据库（Docker 方式使用默认值即可）
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_NAME=reading_agent

# 邮件（如需邮件功能，填写 QQ 邮箱或 Gmail）
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USER=your-qq@qq.com
SMTP_PASSWORD=your-smtp-auth-code
EMAIL_FROM=your-qq@qq.com
EMAIL_TO=your-qq@qq.com
```

**QQ 邮箱授权码获取方式：**
1. 登录 QQ 邮箱 → 设置 → 账号
2. 开启「POP3/IMAP/SMTP服务」
3. 按提示发送短信，获得 16 位授权码
4. 将授权码填入 `SMTP_PASSWORD`

### 3. 启动服务

```powershell
# 启动所有服务（首次会自动下载镜像并构建）
docker-compose up -d

# 查看启动状态
docker-compose ps

# 查看日志
docker-compose logs -f app
```

等待看到以下日志表示启动成功：
```
Application startup complete
```

### 4. 验证服务

#### 4.1 健康检查
```powershell
Invoke-RestMethod -Uri http://localhost:8000/health | ConvertTo-Json
```
**预期结果：** `{"status": "healthy"}`

#### 4.2 访问首页
浏览器打开：http://localhost:8000/

#### 4.3 查看 API 文档
浏览器打开：http://localhost:8000/docs

#### 4.4 检查邮件配置
```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/scheduler/email/config-check | ConvertTo-Json -Depth 3
```
**预期结果：** `is_configured: true`（如果配置了 SMTP）

#### 4.5 发送测试邮件
```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/scheduler/trigger/email -Method POST | ConvertTo-Json
```
**预期结果：** `success: true`, `sent: true`，并在邮箱收到测试邮件

#### 4.6 查看邮件历史
```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/scheduler/emails | ConvertTo-Json -Depth 3
```

## 常用命令

### 查看日志
```powershell
# 查看应用日志
docker-compose logs -f app

# 查看数据库日志
docker-compose logs -f db

# 查看所有日志
docker-compose logs -f
```

### 停止服务
```powershell
# 停止但保留数据
docker-compose stop

# 停止并删除容器（数据保留在卷中）
docker-compose down

# 完全重置（删除容器和数据卷，慎用！）
docker-compose down -v
```

### 重启服务
```powershell
docker-compose restart

# 或先停止再启动
docker-compose down
docker-compose up -d
```

### 更新代码后重新构建
```powershell
# 拉取最新代码后重新构建
docker-compose down
docker-compose up -d --build
```

## 数据库管理

### 进入数据库命令行
```powershell
docker-compose exec db psql -U postgres -d reading_agent
```

### 常用 SQL 查询
```sql
-- 查看文章数量
SELECT COUNT(*) FROM articles;

-- 查看推荐记录
SELECT * FROM recommendations ORDER BY created_at DESC LIMIT 5;

-- 查看邮件发送记录
SELECT * FROM email_logs ORDER BY created_at DESC LIMIT 5;

-- 退出
\q
```

## 常见错误排查

### 错误："connection to server refused"
**原因：** 数据库未启动或配置错误

**排查步骤：**
```powershell
# 1. 检查数据库容器状态
docker-compose ps

# 2. 检查数据库日志
docker-compose logs db

# 3. 确保 .env 中数据库配置正确
# Docker 方式：DATABASE_HOST=localhost（外部）或 db（内部）
```

### 错误："Email service is not configured"
**原因：** 未配置 SMTP 或配置错误

**排查步骤：**
```powershell
# 1. 检查 .env 中的邮件配置
# 2. 验证配置状态
Invoke-RestMethod -Uri http://localhost:8000/api/scheduler/email/config-check | ConvertTo-Json

# 3. 常见错误：
# - 使用了 QQ 密码而非授权码
# - SMTP_HOST 拼写错误
# - 端口错误（QQ 用 587，Gmail 用 587 或 465）
```

### 错误：端口被占用
**原因：** 8000 或 5432 端口已被其他程序使用

**解决：**
```powershell
# 修改 .env 中的端口映射
PORT=8001
DATABASE_PORT=5433

# 或使用 Docker 动态端口
docker-compose up -d
```

### 错误：PowerShell 中 Invoke-RestMethod 失败
**替代方案：**
```powershell
# 方案1：使用 curl（PowerShell 7+）
curl http://localhost:8000/health

# 方案2：使用浏览器直接访问
# http://localhost:8000/health

# 方案3：使用 Python
python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
```

## 验收通过标准

完成以下检查即表示部署成功：

- [ ] `docker-compose up -d` 成功，无报错
- [ ] `docker-compose ps` 显示两个容器都在运行
- [ ] 访问 http://localhost:8000/health 返回 `{"status": "healthy"}`
- [ ] 访问 http://localhost:8000 能看到首页
- [ ] 访问 http://localhost:8000/docs 能看到 API 文档
- [ ] 配置了邮件后，发送测试邮件能收到
- [ ] `pytest -q` 全量测试通过（开发环境）

## 下一步

部署成功后，你可以：

1. **手动触发采集**：`POST /api/scheduler/trigger/fetch`
2. **手动生成推荐**：`POST /api/scheduler/trigger/recommend`
3. **查看推荐结果**：访问首页或 `GET /api/recommendations/today`
4. **设置定时任务**：调度器会自动在配置的时间运行

## 故障反馈

如遇到本指南未覆盖的问题，请记录：
1. 错误信息和完整日志
2. 当前 `.env` 配置（脱敏后）
3. Docker 版本 (`docker --version`)
4. 操作系统版本
