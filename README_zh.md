# Farm Manager

> AI 驱动的农场管理平台 — 后端 + 管理后台 + 移动端 App

## 功能特性

- **作物与周期管理** — 追踪种植周期、作物模板和田间活动
- **成本与利润追踪** — 记录收支、查看周期利润和年度汇总；AI 自然语言记账解析
- **农事日志** — 记录操作类型、日期和备注
- **AI 助手** — 基于 LangGraph 的聊天 Agent，支持工具调用和 SSE 流式响应
- **天气集成** — 多日天气预报辅助农事规划
- **管理后台** — React + Ant Design 管理控制台
- **移动端 App** — React Native 移动应用，随时随地管理农场

## 技术栈

| 层级 | 技术 |
|------|-----|
| 后端 | FastAPI + SQLAlchemy + SQLite + LangGraph + LangChain-OpenAI |
| 管理后台 | React 19 + TypeScript + Vite + Ant Design |
| 移动端 | React Native 0.74 + TypeScript + Zustand |
| 部署 | Docker / docker-compose，一键部署到阿里云 ECS |

## 快速开始

```bash
# 后端（Docker）
docker compose up -d --build

# 管理后台
cd admin-web && npm install && npm run dev

# 移动端
cd FarmManagerMobile && npm install
# Android
npx react-native run-android
# iOS
npx react-native run-ios
```

## 项目结构

```
backend/              # FastAPI 应用
  app/api/            # 路由处理器
  app/agents/         # LangGraph AI Agent
  app/services/       # 业务逻辑层
  app/models/         # SQLAlchemy 数据模型
  app/schemas/        # Pydantic 数据校验
admin-web/            # React 管理后台
  src/pages/          # 仪表盘、作物、成本、AI 助手、天气...
FarmManagerMobile/    # React Native 移动端
  src/screens/        # 首页、成本、周期、日志、AI 助手、设置
  src/stores/         # Zustand 状态管理
docs/                 # 架构与设计文档
```

## API 概览

| 端点 | 说明 |
|------|-----|
| `POST /agent/chat/stream` | AI 聊天（SSE 流式响应） |
| `POST /costs/parse` | AI 自然语言记账解析 |
| `GET /cycles` | 种植周期列表 |
| `GET /costs` | 成本记录（分页） |
| `GET /weather/forecast` | 天气预报 |

## 许可证

MIT
