# Release Notes v0.1.0

## 概述

信息获取助手首个 MVP 版本，实现从内容采集到邮件推送的完整闭环。

## 已完成功能

### 内容采集
- [x] V2EX 来源适配器（最新/热门主题）
- [x] 少数派来源适配器
- [x] RSSHub 知乎来源适配器
- [x] RSSHub 豆瓣来源适配器
- [x] RSS 基础解析框架
- [x] 内容标准化与去重

### 内容处理
- [x] 内容分类器（technology/discussion/product/culture）
- [x] 质量评分器（基于可读性、信息密度、时效性）
- [x] Embedding 向量支持（预留）

### 推荐系统
- [x] 个性化匹配算法
- [x] 重排序器（SimpleReranker）
- [x] 多样性控制
- [x] 探索机制（30% 探索比例）
- [x] 推荐理由生成（预留）

### 邮件系统
- [x] SMTP 邮件发送核心（支持 QQ/Gmail）
- [x] HTML/纯文本双版本模板
- [x] 邮件配置检查接口
- [x] 测试邮件发送接口（含今日推荐）
- [x] 邮件发送历史查询
- [x] 每日定时邮件任务（7:00）
- [x] EmailLog 表记录发送状态

### 调度器
- [x] APScheduler 定时任务
- [x] 每日采集任务（6:00）
- [x] 每日推荐生成（6:30）
- [x] 任务执行状态记录

### API 层
- [x] 17 个 HTTP 接口
- [x] 自动 API 文档（/docs）
- [x] 健康检查端点

### Web 看板
- [x] 首页推荐展示
- [x] 响应式设计

### 测试与质量
- [x] 287 个自动化测试（全部通过）
- [x] 邮件功能测试（81 个）
- [x] 调度器测试（19 个）
- [x] API 端点测试（21 个）

### 部署支持
- [x] Docker 支持（Dockerfile + docker-compose.yml）
- [x] 环境变量配置模板（.env.example）
- [x] 部署文档（docs/deployment/）
- [x] 快速开始指南（QUICKSTART.md）

## 已验证功能

| 功能 | 验证方式 | 状态 |
|------|----------|------|
| 内容采集 | 手动触发 fetch | ✅ 可抓取 V2EX 20+ 条 |
| 推荐生成 | 手动触发 recommend | ✅ 生成 10 条推荐 |
| 邮件发送 | API + 实际收件 | ✅ 含推荐列表 |
| 首页展示 | 浏览器访问 | ✅ 显示 10 条推荐 |
| API 文档 | 浏览器访问 | ✅ Swagger UI 正常 |
| 定时任务 | 调度器状态接口 | ✅ 3 个任务已注册 |
| 测试全量 | pytest -q | ✅ 287 passed |

## 技术栈

- **后端**: Python 3.11 + FastAPI
- **数据库**: PostgreSQL 15
- **ORM**: SQLAlchemy 2.0
- **调度**: APScheduler
- **邮件**: smtplib + Jinja2 模板
- **测试**: pytest
- **部署**: Docker + Docker Compose

## 已知限制

### 非阻塞问题（不影响 v0.1.0 发布）
1. **邮件链接手机端兼容性** - 部分邮件客户端链接跳转问题（详见 TODO_v0.1.1.md）
2. **首次启动无数据** - 需要手动运行一次采集/推荐任务
3. **单用户支持** - 当前为 MVP 单人使用设计
4. **内容源有限** - 仅 V2EX 实时更新，其他源待扩展

### 功能限制
- 邮件退订功能未实现
- 多收件人支持未实现
- 邮件模板自定义需改代码
- 富媒体邮件（图片/视频）不支持

## 安装与运行

```bash
# 1. 克隆代码
git clone <repo-url>
cd information_acquisition_assistant

# 2. 配置环境
cp .env.example .env
# 编辑 .env 配置数据库和邮件

# 3. Docker 启动
docker-compose up -d

# 4. 访问
open http://localhost:8000
```

## API 端点

```
GET  /                          首页看板
GET  /health                    健康检查
GET  /docs                      API 文档

GET  /api/recommendations/today              今日推荐
GET  /api/recommendations/{id}               推荐详情
POST /api/recommendations/{id}/click         记录点击
POST /api/recommendations/{id}/feedback      提交反馈

GET  /api/scheduler/status                   调度器状态
POST /api/scheduler/trigger/fetch            手动采集
POST /api/scheduler/trigger/recommend        手动推荐
POST /api/scheduler/trigger/email            发送测试邮件
GET  /api/scheduler/emails                   邮件历史
GET  /api/scheduler/email/config-check       邮件配置检查
```

## 版本信息

- **版本**: v0.1.0
- **发布日期**: 2026-04-15
- ** commit**: 待打 tag
- **状态**: 可发布

## 贡献者

- 主要开发: Claude Code AI Assistant
- 需求与设计: 项目发起人

## 许可证

待补充

---

**v0.1.0 是首个可运行的 MVP 版本，标志着项目从概念验证进入实际可用阶段。**
