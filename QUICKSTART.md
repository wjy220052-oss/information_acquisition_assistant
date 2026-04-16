# 快速开始指南

5 分钟在本地启动「信息获取助手」。

## 前置要求

- Docker Desktop 已安装并运行
- PowerShell (Windows) 或 Terminal (macOS/Linux)

## 3 步启动

### 1. 配置环境变量

```powershell
copy .env.example .env
notepad .env  # 修改数据库密码和邮件配置
```

**最小配置（复制粘贴到 .env）：**
```env
# 数据库（Docker 使用）
DATABASE_PASSWORD=postgres
DATABASE_NAME=reading_agent

# 邮件（QQ 邮箱示例，可选）
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USER=your-qq@qq.com
SMTP_PASSWORD=your-auth-code
EMAIL_FROM=your-qq@qq.com
EMAIL_TO=your-qq@qq.com
```

### 2. 启动服务

```powershell
docker-compose up -d
```

等待约 30 秒，直到看到：`Application startup complete`

### 3. 验证运行

```powershell
# 健康检查
Invoke-RestMethod http://localhost:8000/health

# 访问首页
start http://localhost:8000
```

## 常用命令

```powershell
# 查看日志
docker-compose logs -f app

# 停止服务
docker-compose down

# 重启
docker-compose restart

# 完全重置（删除数据）
docker-compose down -v
```

## 详细文档

- [完整部署指南](docs/deployment/local_docker_setup.md)
- [API 文档](http://localhost:8000/docs)（启动后访问）

## 验证清单

- [ ] `docker-compose up -d` 成功
- [ ] http://localhost:8000/health 返回 `healthy`
- [ ] 首页能正常显示
- [ ] 邮件配置检查返回 `is_configured: true`
