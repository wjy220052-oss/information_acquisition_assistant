# 环境搭建说明

## 前置依赖

- Python 3.10+
- PostgreSQL 15+ (推荐)
- Redis 7+ (推荐)

## 快速开始

### 1. 创建虚拟环境

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS
python -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

```bash
pip install fastapi uvicorn pydantic[settings] pytest httpx
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并根据需要修改：

```bash
cp .env.example .env
```

### 4. 启动应用

开发模式（自动重载）：
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

生产模式：
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. 验证

访问健康检查：
```bash
curl http://localhost:8000/health
```

或访问浏览器：
- http://localhost:8000/ (开发模式下可用)
- http://localhost:8000/docs (开发模式下可用，查看 API 文档)

## 运行测试

```bash
pytest tests/
```

带详细输出：
```bash
pytest tests/ -v
```

带覆盖率：
```bash
pytest tests/ --cov=app --cov-report=html
```

## 项目结构

```
information_acquisition_assistant/
├── app/
│   ├── core/
│   │   ├── config.py      # 配置管理
│   │   └── logging.py     # 日志配置
│   └── main.py            # FastAPI 应用入口
├── tests/
│   ├── test_config.py     # 配置模块测试
│   └── test_main.py       # 主应用测试
├── docs/
│   └── setup.md           # 本文档
├── .env.example           # 环境变量示例
└── CLAUDE.md              # 项目说明
```

## 开发建议

- 使用 `ruff` 进行代码检查和格式化（推荐）
- 遵循 PEP 8 编码规范
- 编写测试时遵循 `tests/` 目录结构
