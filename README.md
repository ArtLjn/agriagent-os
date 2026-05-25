# Farm Manager

> AI-powered farm management platform — backend + admin dashboard + mobile app

## Features

- **Crop & Cycle Management** — track planting cycles, crop templates, and field activities
- **Cost & Profit Tracking** — record costs/income, view per-cycle profit and yearly summaries; AI natural language parsing
- **Farm Activity Logs** — log operations with type, date, and notes
- **AI Advisor** — LangGraph-powered chat agent with tool calling; streaming SSE responses
- **Weather Integration** — multi-day forecast for farm planning
- **Admin Dashboard** — React + Ant Design management console
- **Mobile App** — React Native app for on-the-go farm management

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + SQLAlchemy + SQLite + LangGraph + LangChain-OpenAI |
| Admin Web | React 19 + TypeScript + Vite + Ant Design |
| Mobile | React Native 0.74 + TypeScript + Zustand |
| Infra | Docker / docker-compose, deploy to Alibaba Cloud ECS |

## Quick Start

```bash
# Backend (Docker)
docker compose up -d --build

# Admin Web
cd admin-web && npm install && npm run dev

# Mobile App
cd FarmManagerMobile && npm install
# Android
npx react-native run-android
# iOS
npx react-native run-ios
```

## Project Structure

```
backend/              # FastAPI application
  app/api/            # Route handlers
  app/agents/         # LangGraph AI agent
  app/services/       # Business logic
  app/models/         # SQLAlchemy models
  app/schemas/        # Pydantic schemas
admin-web/            # React admin dashboard
  src/pages/          # Dashboard, Crops, Costs, Agent, Weather...
FarmManagerMobile/    # React Native mobile app
  src/screens/        # Home, Cost, Cycle, Log, Agent, Settings
  src/stores/         # Zustand state management
docs/                 # Architecture and design docs
```

## API Overview

| Endpoint | Description |
|----------|------------|
| `POST /agent/chat/stream` | AI chat with SSE streaming |
| `POST /costs/parse` | AI natural language cost parsing |
| `GET /cycles` | List planting cycles |
| `GET /costs` | List cost records (paginated) |
| `GET /weather/forecast` | Weather forecast |

## License

MIT
