## Context

用户父母承包二三十亩土地，采用传统的经验和手工记录方式管理农事。春季种植西瓜（3月定植，6-7月采收），秋季种植豆角（7月播种，10月采收）。目前缺乏系统化的种植周期管理、天气预警和成本核算工具。

本项目旨在开发一款原生移动 App，帮助农民用户数字化管理种植全过程，提升农事安排的准确性和投入产出的清晰度。

## Goals / Non-Goals

**Goals:**
- 建立可扩展的多作物种植周期管理系统，支持自定义生长阶段
- 实现基于天气数据的灾害预警和农事建议
- 构建 AI Agent，融合种植周期、天气、农事记录生成个性化建议
- 提供简洁的成本记账和年度利润分析
- 支持每日农事打卡记录，形成完整种植档案
- 代码架构清晰，便于后续功能迭代（如图像识别、市场行情、客户管理等）

**Non-Goals:**
- 图像识别病虫害（用户明确不需要，其他 App 已覆盖）
- 电商/农资采购功能
- 多用户协作/团队管理
- 实时 IoT 传感器接入
- 离线地图/GIS 功能

## Decisions

### 后端框架：FastAPI + SQLAlchemy
- **选择原因**：Python 生态丰富，AI 集成方便；FastAPI 异步性能优秀，自动 API 文档；SQLAlchemy ORM 便于数据建模
- **替代方案**：Django（太重）、Flask（缺少现代特性）

### 数据库：SQLite（初期）
- **选择原因**：部署简单，无需独立数据库服务，适合初期单用户使用场景
- **未来演进**：用户量增长后可迁移至 PostgreSQL，SQLAlchemy 抽象层保证迁移平滑

### 客户端：React Native
- **选择原因**：跨平台（iOS/Android），一套代码覆盖；原生体验接近纯原生 App；JavaScript 生态丰富
- **替代方案**：Flutter（学习成本）、纯原生（开发效率低）、小程序（功能受限）

### AI Agent 架构：大模型 API + 结构化提示词
- **选择原因**：用户会提供第三方 AI API 接口，采用提示词工程 + 函数调用模式实现 Agent 能力，无需自建模型
- **Agent 工作流**：收集上下文（周期状态 + 天气 + 近期农事）→ 构建结构化提示 → 调用大模型 → 解析建议 → 推送用户

### 代码组织：分层架构
```
backend/
├── app/
│   ├── api/          # API 路由层
│   ├── services/     # 业务逻辑层
│   ├── models/       # 数据模型层
│   ├── schemas/      # Pydantic 数据校验
│   ├── agents/       # AI Agent 模块
│   └── core/         # 配置、工具函数
└── tests/

mobile/
├── src/
│   ├── api/          # Axios 实例 + API 封装 + TypeScript 类型
│   ├── components/   # 通用 UI 组件（BigButton、Card、Timeline 等）
│   ├── navigation/   # React Navigation（Tab + Stack）配置
│   ├── screens/      # 页面组件（home/cycle/log/cost/agent/settings）
│   ├── stores/       # Zustand 状态管理（按模块拆分）
│   └── theme/        # 配色方案 + 间距/字体规范
├── App.tsx           # 应用入口
├── index.js          # 注册组件
├── metro.config.js   # Metro 配置
├── babel.config.js   # Babel 预设
├── tsconfig.json     # TypeScript 配置
└── package.json      # 依赖（RN 0.74 + Navigation 6 + Zustand 4 + Axios）
```

### 认证：设备级本地认证（初期免登录）
- **选择原因**：面向单一家庭用户，无需复杂的用户注册登录流程，降低使用门槛
- **未来演进**：如需要多设备同步或数据备份，可后续增加账号系统

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| 父母使用手机操作不熟练 | 界面极简设计、大按钮、语音输入支持、减少文字输入 |
| 农村地区网络不稳定 | 本地 SQLite 缓存、离线记录能力、弱网友好设计 |
| AI 建议的准确性 | 明确标注"建议仅供参考"、结合本地农技知识库做校验 |
| 种植周期因地区/品种差异大 | 支持自定义阶段时长、提供模板但允许灵活调整 |
| 第三方 API 稳定性（天气/AI） | 添加降级策略，API 不可用时使用本地规则和缓存数据 |

## Migration Plan

- 新系统从零开发，无迁移需求
- 部署：后端可部署至家庭服务器或云服务器，客户端通过应用商店分发

## Open Questions

1. AI API 的具体提供商和能力边界（决定 Agent 提示词设计策略）
2. 推送通知方案：本地定时通知 vs 远程推送服务
3. 天气 API 选型（国内服务商如和风天气、心知天气等）
4. 是否需要数据导出/备份功能（如 Excel 报表导出）
