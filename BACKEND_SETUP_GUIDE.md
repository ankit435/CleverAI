# Production Multi-User AI Chatbot Agent Platform

Welcome to the **Clever Multi-User AI Agent Platform** backend architecture and deployment guide. This document details the production design, database models, session management, multi-user isolation, and API specifications.

---

## 🏛️ System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                   Frontend Client (Browser)                      │
│   React 18 + TypeScript + Vite + Context State                   │
│   - Auth State Guard (Forces login if unauthenticated)           │
│   - Multi-Tool Selector (Web Search, Sandbox, DALL-E, Charts)    │
│   - Rich Tool Execution Widgets & Live Message Feeds             │
└────────────────────────────────┬─────────────────────────────────┘
                                 │ HTTPS / REST / Bearer JWT
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│              Backend Application Gateway (Port 8000)             │
│   Node.js + Express + TypeScript + Prisma ORM + pg Pool          │
│   - Middleware: Session-Verified Auth & Request ID Logging       │
│   - Routes: /api/v1/auth, /api/v1/conversations, /api/v1/chat    │
│   - Health / Readiness: /api/v1/health, /api/v1/ready            │
└────────────────┬───────────────────────────────┬─────────────────┘
                 │ Prisma ORM                    │ HTTP / REST
                 ▼                               ▼
┌─────────────────────────────────┐   ┌────────────────────────────┐
│      PostgreSQL (clever_db)     │   │  Python Agent Server :8001 │
│ - users                         │   │  FastAPI + LangChain       │
│ - sessions (Revocable Auth)     │   │  - ChatNVIDIA / OpenAI     │
│ - chat_threads (Conversations)  │   │  - Dynamic Chains          │
│ - messages (User & AI)          │   │  - Tool Pipelines          │
│ - agent_runs (Execution State)  │   │  - Session Thread Memory   │
│ - tool_calls (Auditing Data)    │   └────────────────────────────┘
└─────────────────────────────────┘
```

---

## 🗄️ PostgreSQL Database Schema (`server/prisma/schema.prisma`)

```prisma
model User {
  id           Int          @id @default(autoincrement())
  name         String
  email        String       @unique
  passwordHash String?      @map("password_hash")
  googleId     String?      @unique @map("google_id")
  avatarUrl    String?      @map("avatar_url")
  plan         String       @default("Free")
  isActive     Boolean      @default(true) @map("is_active")
  createdAt    DateTime     @default(now()) @map("created_at")
  updatedAt    DateTime     @default(now()) @updatedAt @map("updated_at")
  lastLoginAt  DateTime?    @map("last_login_at")

  sessions     Session[]
  threads      ChatThread[]
  agentRuns    AgentRun[]

  @@map("users")
}

model Session {
  id          String    @id @default(uuid())
  userId      Int       @map("user_id")
  tokenHash   String    @unique @map("token_hash")
  userAgent   String?   @map("user_agent")
  ipAddress   String?   @map("ip_address")
  expiresAt   DateTime  @map("expires_at")
  revokedAt   DateTime? @map("revoked_at")
  createdAt   DateTime  @default(now()) @map("created_at")
  lastUsedAt  DateTime  @default(now()) @map("last_used_at")

  user        User      @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId])
  @@index([tokenHash])
  @@map("sessions")
}

model ChatThread {
  id          String     @id @default(uuid())
  userId      Int        @map("user_id")
  title       String
  category    String     @default("favorites")
  isArchived  Boolean    @default(false) @map("is_archived")
  metadata    Json?
  createdAt   DateTime   @default(now()) @map("created_at")
  updatedAt   DateTime   @default(now()) @updatedAt @map("updated_at")

  user        User       @relation(fields: [userId], references: [id], onDelete: Cascade)
  messages    Message[]
  agentRuns   AgentRun[]

  @@index([userId])
  @@index([updatedAt])
  @@map("chat_threads")
}

model Message {
  id          String     @id @default(uuid())
  threadId    String     @map("thread_id")
  sender      String     // 'user' | 'ai' | 'system'
  text        String     @db.Text
  toolResults Json?      @map("tool_results")
  metadata    Json?
  createdAt   DateTime   @default(now()) @map("created_at")

  thread      ChatThread @relation(fields: [threadId], references: [id], onDelete: Cascade)

  @@index([threadId])
  @@index([createdAt])
  @@map("messages")
}

model AgentRun {
  id              String     @id @default(uuid())
  threadId        String     @map("thread_id")
  userId          Int        @map("user_id")
  prompt          String     @db.Text
  response        String?    @db.Text
  status          String     @default("pending") // 'pending' | 'running' | 'completed' | 'failed'
  model           String?
  provider        String?
  executionTimeMs Int?       @map("execution_time_ms")
  error           String?    @db.Text
  metadata        Json?
  startedAt       DateTime   @default(now()) @map("started_at")
  completedAt     DateTime?  @map("completed_at")

  thread          ChatThread @relation(fields: [threadId], references: [id], onDelete: Cascade)
  user            User       @relation(fields: [userId], references: [id], onDelete: Cascade)
  toolCalls       ToolCall[]

  @@index([threadId])
  @@index([userId])
  @@index([status])
  @@map("agent_runs")
}

model ToolCall {
  id              String    @id @default(uuid())
  agentRunId      String    @map("agent_run_id")
  toolId          String    @map("tool_id")
  toolName        String    @map("tool_name")
  status          String    @default("running") // 'running' | 'success' | 'error'
  input           Json?
  output          Json?
  executionTimeMs Int?      @map("execution_time_ms")
  error           String?   @db.Text
  startedAt       DateTime  @default(now()) @map("started_at")
  completedAt     DateTime? @map("completed_at")

  agentRun        AgentRun  @relation(fields: [agentRunId], references: [id], onDelete: Cascade)

  @@index([agentRunId])
  @@map("tool_calls")
}
```

---

## 🔒 Security & Multi-User Isolation

1. **Authentication**:
   - Password authentication with `bcryptjs` (salt rounds: 10).
   - Cryptographically signed JWT tokens linked directly to persistent `Session` records in PostgreSQL.
   - Immediate session revocation upon calling `POST /api/v1/auth/logout` (`revokedAt = NOW()`).
2. **Server-Side Authorization**:
   - User identity is resolved exclusively from the verified database session (`req.user.id`).
   - Every database query on conversations, messages, agent runs, and tool calls is strictly scoped with `where: { userId: req.user.id }`.
   - Cross-user queries return `404 Not Found / Access Denied` to prevent enumeration and data leakage.
3. **Agent Tool Boundaries**:
   - Tool executions inherit user context and are isolated per conversation.
   - Tool outputs and execution metrics are persisted in structured `ToolCall` relational records.

---

## 📡 API Endpoint Reference

### Authentication (`/api/v1/auth`)

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `POST` | `/api/v1/auth/signup` | Register new account (`name`, `email`, `password`, `rememberMe`) | No |
| `POST` | `/api/v1/auth/login` | Login with credentials (`email`, `password`, `rememberMe`) | No |
| `POST` | `/api/v1/auth/google` | Google OAuth SSO login/signup | No |
| `POST` | `/api/v1/auth/logout` | Revoke active PostgreSQL session | **Yes** |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile & active session metadata | **Yes** |

### Conversations (`/api/v1/conversations`)

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `GET` | `/api/v1/conversations` | List user's conversations with pagination (`page`, `limit`, `category`, `search`) | **Yes** |
| `POST` | `/api/v1/conversations` | Create a new isolated conversation thread | **Yes** |
| `GET` | `/api/v1/conversations/:id` | Get single conversation with full message history | **Yes** |
| `PATCH` | `/api/v1/conversations/:id` | Update conversation title or category | **Yes** |
| `DELETE` | `/api/v1/conversations/:id` | Delete conversation (cascades messages, runs, and tool calls) | **Yes** |
| `GET` | `/api/v1/conversations/:id/messages` | Paginated message history for a conversation | **Yes** |
| `GET` | `/api/v1/conversations/:id/runs` | Get agent execution runs and tool calls | **Yes** |

### Chat & Agent Execution (`/api/v1/chat`)

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `POST` | `/api/v1/chat` | Send prompt, execute multi-tool agent pipeline, persist AgentRun & ToolCalls | **Yes** |
| `GET` | `/api/v1/chat/history` | Backward-compatible history endpoint scoped strictly to user | **Yes** |

### Health & Readiness Checks

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Service liveness check |
| `GET` | `/api/v1/ready` | Verifies PostgreSQL and Python AI backend connectivity |

---

## 🚀 Running the Services & Tests

### 1. Start PostgreSQL & Apply Schema
```bash
cd server
npx prisma db push
```

### 2. Run Automated Integration Tests
```bash
cd server
npm test
```
*Executes all 19 automated tests covering Authentication, Multi-User Isolation, and Agent Persistence with 100% pass rate.*

### 3. Start Application Services
* **Node.js Express Backend**: `npm run dev --prefix server` (Port 8000)
* **Python LangChain AI Server**: `python python_project/app.py` (Port 8001)
* **React Frontend**: `npm run dev` (Port 5173)

