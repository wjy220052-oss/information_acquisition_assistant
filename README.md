# 信息获取助手 / Information Acquisition Assistant

一个面向个人用户的高质量中文内容推荐 Agent / 阅读决策助手。

## 项目简介

系统从多个简体中文内容平台获取候选内容，完成质量筛选、个性化排序、解释生成、优质作者发现与主动推送，并通过用户反馈不断优化推荐结果。

**目标不是最大化点击率，而是帮助用户以更低时间成本发现更高质量、更适合长期成长、且不容易被信息茧房困住的中文内容。**

## 核心特性

- **多源内容采集**: V2EX、少数派、知乎、豆瓣、Solidot、阮一峰周刊
- **智能质量评分**: 基于内容结构、深度、可信度等多维度评分
- **个性化推荐**: 基于用户画像的加权排序与多样性重排
- **每日邮件摘要**: 早上 7 点自动发送阅读推荐
- **网页看板**: 浏览推荐、反馈评分、管理待读
- **优质作者发现**: 识别并推荐高质量作者

## 技术栈

- **后端**: Python + FastAPI
- **数据库**: PostgreSQL + SQLAlchemy 2.0
- **缓存**: Redis
- **调度**: APScheduler
- **部署**: Docker + Docker Compose

## 快速开始

### 使用 Docker（推荐）

```bash
# 1. 克隆仓库
git clone <your-repo-url>
cd information_acquisition_assistant

# 2. 复制环境配置
cp .env.example .env
# 编辑 .env 配置你的数据库和邮件

# 3. 启动服务
docker-compose up -d

# 4. 初始化数据库
docker-compose exec app python -m scripts.init_db

# 5. 访问
# Web UI: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### 本地开发

```bash
# 1. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env

# 4. 运行
uvicorn app.main:app --reload
```

## 配置说明

复制 `.env.example` 为 `.env` 并配置：

- **数据库**: PostgreSQL 连接信息
- **邮件**: SMTP 配置（支持 QQ/Gmail/163/Outlook/企业邮箱）
- **调度**: 定时任务时间配置

## 项目结构

```
.
├── app/                    # 主应用代码
│   ├── api/               # API 路由
│   ├── core/              # 核心配置、邮件、数据库
│   ├── models/            # 数据模型
│   ├── repositories/      # 数据仓库
│   ├── services/          # 业务服务
│   │   ├── sources/       # 内容源适配器
│   │   ├── intelligence/  # 分类、质量评分
│   │   └── recommendation/# 推荐系统
│   └── tasks/             # 后台任务
├── tests/                  # 测试
├── docs/                   # 文档
├── scripts/                # 辅助脚本
├── Dockerfile             # Docker 构建
└── docker-compose.yml     # Docker 编排
```

## 当前版本

**v0.1.1** - 新增 Solidot 内容源 + SMTP SSL 支持 + 推荐理由

查看 [RELEASE_NOTES_v0.1.0.md](./RELEASE_NOTES_v0.1.0.md) 和 [TODO_v0.1.1.md](./TODO_v0.1.1.md) 了解详细变更。

## 测试

```bash
# 运行全部测试
pytest

# 运行特定模块
pytest tests/services/
pytest tests/api/
```

## 贡献

这是一个个人阅读助手项目，欢迎建议和改进。

## License

MIT
