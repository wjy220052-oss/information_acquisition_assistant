# Claude Code Configuration

This document provides context and instructions for working with this project using Claude Code.

## Project Overview

**Purpose:**  
构建一个面向个人用户的高质量中文内容推荐 Agent / 阅读决策助手。  
系统从多个简体中文内容平台获取候选内容，完成质量筛选、个性化排序、解释生成、优质作者发现与主动推送，并通过用户反馈不断优化推荐结果。  
它的目标不是最大化点击率，而是帮助用户以更低时间成本发现更高质量、更适合长期成长、且不容易被信息茧房困住的中文内容。

**Primary Context:**  
个人阅读输入层 / 内容推荐与阅读决策系统 / 数据管道 + 推荐系统 + Web 应用

**Current State:**  
早期设计阶段，PRD 与系统设计文档已完成，正在进入可开发阶段。  
当前重点是搭建 MVP：先跑通“采集 -> 分析 -> 推荐 -> 交付 -> 反馈 -> 学习 -> 作者发现 -> 待读池”的闭环。

## Technical Stack

### Core Technologies
- **Language(s):** Python
- **Frameworks:** FastAPI
- **Database:** PostgreSQL
- **Other:** Redis, APScheduler（或 Celery）, pgvector（优先）/ Qdrant, SMTP 或邮件 API

### Key Dependencies
- **FastAPI**：提供 API 与后端服务
- **SQLAlchemy / SQLModel（建议二选一）**：ORM 与数据库模型
- **PostgreSQL**：主业务数据库
- **pgvector**：内容向量存储与相似度检索
- **Redis**：缓存、任务状态、可选消息队列
- **APScheduler**：定时任务调度
- **Celery（可选）**：异步任务执行
- **Pydantic**：请求/响应与内部 schema 校验
- **邮件库/邮件 API SDK**：每日邮件摘要发送
- **Embedding/LLM SDK（需统一封装）**：主题标签、摘要、解释生成、动作建议生成

## Architecture

### Project Structure
```text
app/
  api/
    routes/
      recommendations.py
      feedback.py
      authors.py
      reading_queue.py
      profile.py
  core/
    config.py
    logging.py
    scheduler.py
    database.py
  models/
    db/
    schemas/
  services/
    sources/
      base.py
      v2ex.py
      sspai.py
      rsshub_zhihu.py
      rsshub_douban.py
      media.py
    ingestion/
      normalize.py
      dedup.py
    intelligence/
      classifier.py
      embedder.py
      tagger.py
      quality.py
    recommendation/
      profile_matcher.py
      reranker.py
      explorer.py
      explainer.py
      action_suggester.py
    feedback/
      collector.py
      updater.py
      author_update.py
    delivery/
      dashboard.py
      email_digest.py
      weekly_author.py
      reading_queue.py
  repositories/
  tasks/
    fetch.py
    analyze.py
    recommend.py
    email.py
    queue_review.py
    calibration.py
  tests/

### Critical Files
- **Entry Points:** [Main application files]
    app/main.py（FastAPI 入口，建议）
    app/core/scheduler.py（定时任务注册入口）
    app/tasks/ 下各后台任务编排入口
- **Configuration:** [Config files and how they're managed]
    app/core/config.py
    采用环境变量 + .env 管理数据库、Redis、邮件、模型服务、来源配置等
- **Tests:** [Test structure and conventions]
    tests/
- **Documentation:** [Where important docs live]
    docs/
    存放 PRD、系统设计文档、数据库设计、API 说明、任务清单等
### Design Patterns
[Key architectural patterns, conventions, or paradigms used]
    - 单体应用 + 清晰分层架构
    - Source Adapter 模式：每个内容来源一个 adapter
    - Service + Repository 分离
    - 后台任务驱动的数据流水线
    - 规则优先于复杂学习模型
    - 数据驱动的推荐与反馈更新
    - LLM 通过统一 model gateway 封装，不允许业务层直接散连 SDK
    - 内容质量与个性化适配分层建模
    - “高质量”与“当前适配度”分层处理
## Working Style

### Coding Conventions
- **Style Guide:** [e.g., PEP 8, Airbnb, Google Style Guide]
    PEP 8
- **Linting/Formatting:** [Tools used: black, prettier, ESLint, etc.]
    Ruff + Black
- **Naming:** [e.g., snake_case, camelCase, descriptive names, etc.]
    Python 使用 snake_case；类名使用 PascalCase；变量/函数名尽量语义清晰、避免缩写
### Git Workflow
- **Branching Strategy:** [e.g., main, develop, feature branches]
    main 为稳定主分支；使用 feature branches 开发新功能
- **Commit Message Style:** [e.g., Conventional Commits]
    Conventional Commits（建议），例如：
        - feat: add v2ex source adapter
        - fix: correct reading queue decay logic
- **PR Review Process:** [Any specific requirements]
    - 小步提交；一个 PR 只解决一个明确模块
    - PR 需说明：模块职责、输入输出、边界条件、测试情况
    - 若由 AI 辅助完成，需人工检查接口契约、异常处理、测试覆盖和模块边界

### Testing Approach
- **Test Framework:** [e.g., pytest, Jest, unittest]
    pytest
- **Coverage Requirements:** [Minimum coverage or test philosophy]
    MVP 阶段不强制统一覆盖率阈值，但核心模块必须有测试：
    - URL 标准化
    - 去重逻辑
    - 内容分类
    - 质量评分
    - fit_score 计算
    - rerank 逻辑
    - 待读池衰减逻辑
    - rating 映射逻辑
- **Testing Philosophy:** [e.g., integration over unit, real data over mocks, etc.]
    - 核心业务优先测试
    - 规则逻辑优先单元测试
    - 关键数据流做集成测试
    - 尽量用真实结构的数据样例，少做无意义 mock
## Claude-Specific Instructions

### When to Ask
- 修改数据库 schema、核心表结构或推荐主流程前，需要先确认
- 引入新外部依赖、替换基础设施方案（如 pgvector/Qdrant、Celery/APScheduler）前，需要先确认
- 改动产品边界、反馈逻辑、评分规则、探索比例、作者权重规则前，需要先确认
- 删除功能、删除数据、改变推荐优先级前，需要先确认

### Behaviors to Follow
- 严格遵守 PRD 和系统设计文档定义的边界
- 一次只实现一个清晰模块，不要把多个模块混在一起写
- 先写数据模型和接口契约，再写业务逻辑
- 先给出实现计划，再开始写代码
- 代码要包含类型标注、必要注释、错误处理和测试
- 不要为了“更智能”擅自替换成复杂黑盒方案
- 不要在未说明的情况下把 LLM 直接作为最终排序器
- 推荐系统必须遵循：
    - 高质量 > 点击率
    - 宁缺毋滥 > 条数稳定
    - 受控探索 > 纯迎合
    - 长期收益 > 短期点击

### Context Preferences
- 回答风格：偏详细、结构清晰
- 更喜欢先解释模块边界、输入输出、实现顺序，再给代码
- 修改前最好说明会影响哪些文件
- 除非明确要求，否则不要一次输出过多无关代码

## Current Priorities

### Active Work
- 搭建 MVP 基础骨架
- 优先实现可跑通的核心闭环：
    1.来源接入
    2.内容入库与标准化
    3.内容分类与质量评分
    4.推荐生成
    5.网页看板 + 邮件摘要
    6.评分反馈
    7.作者发现
    8.待读池
- 第一批来源优先选择易获取且质量较高的来源：
    - V2EX
    - 少数派
    - RSSHub 提供的知乎相关源
    - RSSHub 提供的豆瓣相关源
    - 1 到 2 个媒体深度来源

### Known Issues
- 来源接入方式可能变化，adapter 需要可维护
- 候选内容质量波动大，需要足够稳的质量门槛
- 若把“未评价”误当负反馈，会导致系统学偏
- 若默认条数理解错误，会稀释“极强筛选器”定位
- 旧文、强作者、不同立场内容如何平衡，需要通过实现细节稳定落地
- 四类内容的质量规则需要逐步迭代，不宜一次写死得过细

### Upcoming Features
- 多源内容接入
- 四类内容质量评估
- 个性化加权排序
- 多样性重排与受控探索
- 推荐解释生成
- 网页看板
- 每日早上 7 点邮件摘要
- 评分与读后感反馈
- 优质作者发现
- 稍后读与待读池
- 每两周偏好校准
- 轻量临时模式（长期价值 / 即时可用 / 探索发现）

## Constraints & Requirements

### Performance
- MVP 不追求高并发，但必须稳定
- 每日任务要在邮件发送前完成
- 推荐生成应在合理时间内完成
- 向量检索与排序逻辑应足够轻量，避免早期过度工程化
- 默认推荐上限 10 条，但实际推荐可以低于 10 条，不得凑数

### Security
- 所有外部密钥通过环境变量管理
- 邮件服务、模型服务、数据库凭证不得硬编码
- API 至少要有基础鉴权/访问控制（如果仅个人本地使用，可后置）
- 原始抓取内容、反馈内容、用户偏好数据都应持久化并妥善管理
- 来源接入必须尽量使用公开、稳定、合法的接口或现成方案

### Compatibility
- 平台目标：优先桌面 Web
- 浏览器兼容：现代浏览器即可
- 数据库兼容：PostgreSQL 优先
- 部署环境：本地开发 + 可迁移到云服务器 / Docker 环境
- 不以移动端优先为目标

### External Dependencies
- RSSHub
- V2EX 接口 / 可用数据入口
- 少数派可访问入口
- RSS/Atom 来源
- 邮件发送服务
- Embedding/LLM 服务
- Redis
- PostgreSQL[APIs, services, or systems this project depends on]

## Resources

- **Repository:** [Link if applicable]
    待补充
- **Documentation:** [Links to external docs]
- **Issue Tracker:** [Where bugs/features are tracked]
- **CI/CD:** [How builds and deployments work]

## Notes
- 这是一个“阅读决策助手”，不是传统的点击率优化推荐系统。
- 系统核心是帮助用户判断“值不值得现在点开”，并逐渐成为稳定的“阅读输入层”。
- 内容价值判断优先级：
    - 客观高质量优先
    - 信息增量优先于可执行性
    - 一手经验 ≈ 系统化总结
    - 观点类内容要求新颖或论证严密
- 推荐系统必须显式区分：
    - 高质量且现在值得看
    - 高质量但更适合收藏
    - 值得知道但不必深读
- 四大内容类型：
    - 长文文章
    - 社区讨论
    - 媒体深度
    - 文化评论 / 书影音评论
- 用户画像优先级：
    作者 ≈ 主题 > 平台
- 探索策略：
    - 候选池层面约 30% 探索内容
    - 最终展示位不强制占 30%
    - 探索内容必须先通过质量门槛
    - 不为“立场不同”而推荐低质量内容
- 反馈规则：
    - 评分 1-9
    - 读后感为高价值反馈
    - 读完未评价默认按 5 分中性处理
    - 多次展示未点击才算弱负反馈
    - “最浪费时间的一篇”视为强负反馈
    - 屏蔽/降权支持撤销
- 待读池规则：
    - 每两天回顾一次
    - 2/5/7 天未读依次降权
    - 两周未读提示是否清除
- 轻量模式：
    - 偏长期价值
    - 偏即时可用
    - 偏探索发现
    - 仅影响当前轮推荐或当前视图，不直接重写长期画像
[Any additional context that doesn't fit elsewhere]
