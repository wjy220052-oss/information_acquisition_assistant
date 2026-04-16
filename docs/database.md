# 数据库设计文档

## 概述

本文档描述了 MVP 阶段的核心数据库 Schema 设计。数据库使用 PostgreSQL，ORM 框架为 SQLAlchemy。

## 表结构设计

### 1. Source（来源表）

**作用**：管理内容来源，控制抓取策略和优先级。

**字段**：
| 字段名 | 类型 | 描述 | 约束 |
|--------|------|------|------|
| id | UUID | 主键 | PRIMARY KEY |
| name | VARCHAR(100) | 来源名称 | NOT NULL |
| domain | VARCHAR(100) | 域名 | NOT NULL |
| type | ENUM | 来源类型 | NOT NULL |
| base_url | VARCHAR(2048) | 基础URL | NOT NULL |
| rss_url | VARCHAR(2048) | RSS地址 | |
| api_url | VARCHAR(2048) | API地址 | |
| source_key | VARCHAR(100) | 自定义唯一标识 | NOT NULL, UNIQUE |
| slug | VARCHAR(100) | URL友好标识 | NOT NULL, UNIQUE |
| is_active | BOOLEAN | 是否启用 | DEFAULT TRUE |
| priority | INTEGER | 优先级(1-100) | DEFAULT 1 |
| articles_per_day | INTEGER | 每日文章数 | DEFAULT 10 |

**索引**：
- `idx_source_domain`
- `idx_source_priority`
- `idx_source_active`

### 2. Author（作者表）

**作用**：管理内容创作者，支持来源内识别。

**字段**：
| 字段名 | 类型 | 描述 | 约束 |
|--------|------|------|------|
| id | UUID | 主键 | PRIMARY KEY |
| source_id | UUID | 来源ID | FOREIGN KEY |
| username | VARCHAR(100) | 用户名 | Nullable |
| name | VARCHAR(100) | 显示名 | |
| author_url | VARCHAR(2048) | 作者页面URL | |
| description | TEXT | 描述 | |
| avatar_url | VARCHAR(2048) | 头像URL | |

**约束**：
- `UNIQUE(source_id, username)` - 仅约束非空 username
- `FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE`

**索引**：
- `idx_author_source_url`
- `idx_author_name`

**特殊处理**：
- username 可为空（某些来源无稳定用户名）
- 同一 source 可有多个 NULL username 记录
- 建议通过 author_url 识别无 username 的作者

### 3. Article（内容表）

**作用**：核心内容实体，包含原始内容和元数据。

**字段**：
| 字段名 | 类型 | 描述 | 约束 |
|--------|------|------|------|
| id | UUID | 主键 | PRIMARY KEY |
| content_hash | VARCHAR(64) | 内容哈希 | Index |
| source_id | UUID | 来源ID | FOREIGN KEY |
| source_item_id | VARCHAR(256) | 来源内部ID | NOT NULL |
| title | VARCHAR(500) | 标题 | NOT NULL |
| url | VARCHAR(2048) | 原始URL | NOT NULL |
| normalized_url | VARCHAR(2048) | 标准化URL | NOT NULL |
| original_content | TEXT | 原始内容 | NOT NULL |
| summary | TEXT | 内容摘要 | |
| content_type | ENUM | 内容类型 | DEFAULT 'unknown' |
| author_id | UUID | 作者ID | FOREIGN KEY, Nullable |
| language | VARCHAR(10) | 语言 | DEFAULT 'zh-CN' |
| status | ENUM | 处理状态 | DEFAULT 'pending' |
| publish_time | TIMESTAMP | 发布时间 | |
| crawl_time | TIMESTAMP | 抓取时间 | NOT NULL, DEFAULT NOW |
| process_time | TIMESTAMP | 处理时间 | |
| word_count | INTEGER | 字数 | DEFAULT 0 |
| reading_time_minutes | INTEGER | 预估阅读时间 | DEFAULT 0 |
| has_images | BOOLEAN | 是否含图片 | DEFAULT FALSE |
| raw_payload | JSONB | 原始数据 | |

**约束**：
- `UNIQUE(source_id, source_item_id)` - 来源内唯一
- `FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE`
- `FOREIGN KEY(author_id) REFERENCES authors.id ON DELETE SET NULL`

**索引**：
- `idx_article_content_hash`
- `idx_article_crawl_time`
- `idx_article_status`
- `idx_article_author`

### 4. Recommendation（推荐结果表）

**作用**：记录推荐决策，支持多批次管理。

**字段**：
| 字段名 | 类型 | 描述 | 约束 |
|--------|------|------|------|
| id | UUID | 主键 | PRIMARY KEY |
| user_id | UUID | 用户ID | NOT NULL, Default: MVP_USER_ID |
| article_id | UUID | 文章ID | FOREIGN KEY |
| recommendation_type | ENUM | 推荐类型 | NOT NULL |
| score | DECIMAL(10,4) | 推荐分数 | NOT NULL |
| rank | INTEGER | 排名 | NOT NULL |
| batch_date | VARCHAR(10) | 批次日期 | NOT NULL |
| status | ENUM | 状态 | DEFAULT 'pending' |
| delivered_at | TIMESTAMP | 推送时间 | Nullable |

**约束**：
- `UNIQUE(user_id, article_id, recommendation_type, batch_date)`
- `FOREIGN KEY(article_id) REFERENCES articles.id ON DELETE CASCADE`

**索引**：
- `idx_recommendation_batch_date`
- `idx_recommendation_status`
- `idx_recommendation_rank`

### 5. Feedback（用户反馈表）

**作用**：收集用户对内容的反馈和评分。

**字段**：
| 字段名 | 类型 | 描述 | 约束 |
|--------|------|------|------|
| id | UUID | 主键 | PRIMARY KEY |
| user_id | UUID | 用户ID | NOT NULL, Default: MVP_USER_ID |
| article_id | UUID | 文章ID | FOREIGN KEY |
| recommendation_id | UUID | 推荐ID | FOREIGN KEY, Nullable |
| feedback_type | ENUM | 反馈类型 | NOT NULL |
| rating | INTEGER | 评分(1-9) | CHECK(rating BETWEEN 1 AND 9) |
| created_at | TIMESTAMP | 创建时间 | NOT NULL, DEFAULT NOW |

**约束**：
- `FOREIGN KEY(article_id) REFERENCES articles.id ON DELETE CASCADE`
- `FOREIGN KEY(recommendation_id) REFERENCES recommendations.id ON DELETE SET NULL`

**索引**：
- `idx_feedback_created_at`
- `idx_feedback_article_rating`
- `idx_feedback_type`

### 6. ReadingQueue（待读池表）

**作用**：管理用户收藏的内容，支持优先级和位置管理。

**字段**：
| 字段名 | 类型 | 描述 | 约束 |
|--------|------|------|------|
| id | UUID | 主键 | PRIMARY KEY |
| user_id | UUID | 用户ID | NOT NULL, Default: MVP_USER_ID |
| article_id | UUID | 文章ID | FOREIGN KEY |
| status | ENUM | 状态 | DEFAULT 'active' |
| added_at | TIMESTAMP | 添加时间 | NOT NULL, DEFAULT NOW |
| position | INTEGER | 队列位置 | NOT NULL |

**约束**：
- `UNIQUE(user_id, article_id)`
- `FOREIGN KEY(article_id) REFERENCES articles.id ON DELETE CASCADE`

**索引**：
- `idx_reading_queue_user_active`
- `idx_reading_queue_added_at`
- `idx_reading_queue_position`

## 数据关系图

```
Source
  |
  |---> Author
  |       |
  |       |---> Article
  |               |
  |               |---> Recommendation
  |               |       |
  |               |       |---> Feedback
  |               |
  |               |---> Feedback
  |               |
  |               |---> ReadingQueue
  |
  |---> Article
        |
        |---> Recommendation
        |       |
        |       |---> Feedback
        |
        |---> Feedback
        |
        |---> ReadingQueue
```

## MVP 特点

1. **单用户模式**：所有 user_id 固定为 `MVP_USER_ID`
2. **最小可行**：只包含核心功能必需的表和字段
3. **渐进式扩展**：预留了扩展字段的位置（不在本轮模型中）
4. **外键策略**：
   - CASCADE：删除来源/文章时级联删除
   - SET NULL：删除作者时保留文章（清空作者信息）

## 后续扩展计划

1. **V1 阶段**：添加质量评分、作者权重字段
2. **V1.5 阶段**：添加向量存储、推荐解释字段
3. **未来**：考虑用户表支持多用户