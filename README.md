# ⚡ CleverAI — Full-Stack Agentic AI & RAG Workspace

> **CleverAI** is a state-of-the-art, full-stack multi-user AI chatbot and agentic workspace powered by **React 18**, **Node.js Express**, **Prisma ORM (PostgreSQL)**, **Python 3.14 FastAPI**, **LangChain**, **NVIDIA AI Endpoints (`ChatNVIDIA`)**, and **Microsoft MarkItDown**.

---

## 📐 System Architecture

```mermaid
flowchart TD
    subgraph Client["Frontend Layer (React 18 + Vite)"]
        UI["Vite React Dashboard (Port 5174/5173)"]
        PRG["Protected Route Guard"]
        API_CLIENT["Central API Client (apiClient.ts)"]
        UI --> PRG --> API_CLIENT
    end

    subgraph Proxy["Reverse Proxy Layer"]
        RP["Vite Dev Server Proxy (vite.config.js)"]
        API_CLIENT --> RP
    end

    subgraph NodeBackend["Express Backend Server (Port 8000)"]
        EX["Express REST API"]
        AUTH["Auth Router (JWT / bcrypt / Google OAuth)"]
        DB_ROUTER["Conversations & Messages Router"]
        PRISMA["Prisma ORM 6.x Singleton"]
        RP -->|/api/v1/auth & /api/v1/chat| EX
        EX --> AUTH
        EX --> DB_ROUTER
        AUTH --> PRISMA
        DB_ROUTER --> PRISMA
    end

    subgraph Database["Database Layer"]
        PG[("PostgreSQL Database (clever_db)")]
        PRISMA --> PG
    end

    subgraph PyServer["Python Agentic AI Server (Port 8001)"]
        FA["FastAPI Application (app.py)"]
        LC["LangChain Engine"]
        NVIDIA["NVIDIA AI Endpoints (ChatNVIDIA)"]
        MEM["Session Memory Manager (Thread Memory)"]
        MKD["Microsoft MarkItDown Conversion Engine"]
        EX -->|HTTP Proxy Call| FA
        FA --> LC --> NVIDIA
        FA --> MEM
        FA --> MKD
    end

    subgraph External["External Cloud AI Services"]
        NV_API["NVIDIA NIM API (meta/llama-3.1-70b-instruct)"]
        LS["LangSmith Tracing Service"]
        NVIDIA --> NV_API
        LC --> LS
    end
```

---

## ✨ Key Features & Capabilities

### 🔒 1. Strict Authentication & Session Authorization
- **JWT Bearer Token Security**: Password hashing via `bcryptjs` with salt rounds. Issues 24-hour or long-lived 30-day tokens when **"Remember me on this device"** is checked.
- **1-Click Google OAuth SSO**: Integrated with Google Identity Services (`POST /api/v1/auth/google`) for seamless authentication.
- **Protected Route Guard Architecture**: Full-screen gate ([`App.tsx`](file:///Users/ankit/Desktop/AI%20&%20ML/ChatbotAgent/src/App.tsx)) locks workspace components when unauthenticated.
- **Auto Session Recovery**: Valid tokens in `localStorage` auto-verify on app launch via `GET /api/v1/auth/me`.

### 🤖 2. Python FastAPI & LangChain AI Engine
- **NVIDIA AI Endpoints Integration**: Powered by `ChatNVIDIA` using model `meta/llama-3.1-70b-instruct` with fallback execution pipelines.
- **Dynamic Multi-Model Factory**: Extensible model provider factory ([`models.py`](file:///Users/ankit/Desktop/AI%20&%20ML/ChatbotAgent/python_project/models.py)) supporting `ChatNVIDIA`, `ChatOpenAI`, `ChatAnthropic`, and `ChatGoogleGenerativeAI` at runtime.
- **Live LangSmith Tracing**: Traces agent executions and chain steps via `LANGSMITH_TRACING` and `LANGSMITH_API_KEY`.

### 🧠 3. Stateful Thread Context & User Memory
- **`SessionMemoryManager`**: Maintains sliding-window conversation history per `threadId`.
- **Dynamic Context Injection**: Formats past message turns into prompt context blocks so the AI model remembers user facts, names, and preferences across messages.

### 📄 4. Microsoft MarkItDown RAG Document Pipeline
- **Multi-Format Conversion**: Integrates official [`microsoft/markitdown`](https://github.com/microsoft/markitdown.git) (v0.1.7) to convert PDF, DOCX, XLSX, PPTX, CSV, TXT, HTML, JSON, and XML files into structured Markdown.
- **Heading-Aware Text Chunking**: Splits converted Markdown into bounded overlapping text chunks with heading metadata.
- **PostgreSQL Document Retrieval**: Persists `Document` and `DocumentChunk` records in PostgreSQL (`clever_db`), retrieving relevant chunks for prompt context with cited LLM responses.

### 🧰 5. Multi-Tool & Plugin Ecosystem
- **🌐 Web Search Engine**: Real-time web citations and structured search results.
- **💻 Code Sandbox Interpreter**: Executable Python code blocks with simulated output.
- **🎨 DALL-E 3 Visual Studio**: Generative image prompt rendering.
- **📊 Data Viz & Chart Builder**: Structured bar, line, and pie chart rendering.
- **⚡ Custom Webhook Tool Builder**: Allows users to register custom REST API webhooks.

### 🌐 6. Vite Reverse Proxy & Centralized API Client
- **Universal API Client ([`apiClient.ts`](file:///Users/ankit/Desktop/AI%20&%20ML/ChatbotAgent/src/config/apiClient.ts))**: Centralized `apiFetch` helper automatically prepending `/api/v1` and attaching JWT headers.
- **Vite Reverse Proxy ([`vite.config.js`](file:///Users/ankit/Desktop/AI%20&%20ML/ChatbotAgent/vite.config.js))**: Proxy forwards `/api/v1/auth` to Express (Port 8000) and `/api/v1/pychat` to Python (Port 8001), eliminating CORS issues.

---

## 🗂️ Monorepo Directory Structure

```
ChatbotAgent/
├── index.html                   # HTML Entry Point
├── package.json                 # Frontend Dependencies & Scripts
├── tsconfig.json                # Frontend TypeScript Configuration
├── vite.config.js               # Vite Dev Server & Reverse Proxy Configuration
├── src/                         # React Frontend Monorepo
│   ├── App.tsx                  # Main App Component & Protected Route Guard
│   ├── index.css                # Master CSS Design System & Theme Variables
│   ├── components/              # UI Components
│   │   ├── AuthModal.tsx        # Login / Signup / Google OAuth Gate
│   │   ├── ChatFeed.tsx         # Conversation Feed & Message Cards
│   │   ├── ChatWelcome.tsx      # Welcome Screen & Quick Prompts
│   │   ├── CustomToolModal.tsx  # Custom REST Webhook Tool Builder
│   │   ├── Header.tsx           # Navigation Header & Single Theme Toggle
│   │   ├── PluginManagerModal.tsx # Multi-Tool Plugin Manager
│   │   ├── PromptInputCard.tsx  # Prompt Input, Attachments & Model Settings
│   │   ├── SettingsModal.tsx    # Workspace Configuration Modal
│   │   ├── Sidebar.tsx          # Conversation History, User Profile & Log Out
│   │   └── UpgradeModal.tsx     # Pro Plan Subscription Upgrade Modal
│   ├── config/                  # Configuration Modules
│   │   ├── apiClient.ts         # Central Universal API Fetch Client
│   │   └── appConfig.ts         # Default Branding & Backend Settings
│   ├── context/                 # State Management
│   │   └── ChatContext.tsx      # Global React Context Provider
│   └── types/                   # TypeScript Interfaces & Types
├── server/                      # Node.js Express Backend
│   ├── package.json             # Express Dependencies
│   ├── tsconfig.json            # Server TypeScript Configuration
│   ├── .env                     # Express & Database Environment Variables
│   ├── prisma/                  # Prisma ORM Setup
│   │   └── schema.prisma        # PostgreSQL Schema & Data Models
│   └── src/                     # Express Application Source
│       ├── index.ts             # Express Server Bootstrapper
│       ├── config/              # Prisma Client & DB Pool Singleton
│       ├── middleware/          # JWT Authentication Middleware
│       └── routes/              # Express API Routes
│           ├── auth.ts          # Auth Endpoints (signup, login, google, me)
│           ├── chat.ts          # Chat Endpoints & Python Proxy Bridge
│           ├── conversations.ts # Thread Management Endpoints
│           └── documents.ts     # Document Upload & MarkItDown Proxy
└── python_project/              # Python FastAPI & LangChain AI Server
    ├── .env                     # NVIDIA API Key & LangSmith Settings
    ├── requirements.txt         # Python Package Dependencies
    ├── app.py                   # FastAPI Application Entrypoint
    ├── config.py                # Pydantic Settings Manager
    ├── documents.py             # MarkItDown Document Conversion Engine
    ├── models.py                # Dynamic Multi-Model Factory (ChatNVIDIA)
    ├── chains/                  # LangChain Prompt Pipelines
    │   └── registry.py          # DynamicChainRegistry & Sequence Builders
    └── memory/                  # Session Context Manager
        └── manager.py           # SessionMemoryManager (Thread Memory)
```

---

## 🗄️ Database Schema & Data Models

The project uses **PostgreSQL** (`clever_db`) managed via **Prisma ORM 6.x** ([`server/prisma/schema.prisma`](file:///Users/ankit/Desktop/AI%20&%20ML/ChatbotAgent/server/prisma/schema.prisma)):

```prisma
model User {
  id           Int          @id @default(autoincrement())
  name         String
  email        String       @unique
  passwordHash String?      @map("password_hash")
  googleId     String?      @unique @map("google_id")
  avatarUrl    String?      @map("avatar_url")
  plan         String       @default("Free")
  createdAt    DateTime     @default(now()) @map("created_at")

  sessions     Session[]
  threads      ChatThread[]
  agentRuns    AgentRun[]
  documents    Document[]
}

model Session {
  id          String    @id @default(uuid())
  userId      Int       @map("user_id")
  tokenHash   String    @unique @map("token_hash")
  expiresAt   DateTime  @map("expires_at")
  user        User      @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model ChatThread {
  id          String     @id @default(uuid())
  userId      Int        @map("user_id")
  title       String
  category    String     @default("favorites")
  createdAt   DateTime   @default(now()) @map("created_at")

  user        User       @relation(fields: [userId], references: [id], onDelete: Cascade)
  messages    Message[]
  agentRuns   AgentRun[]
  documents   Document[]
}

model Document {
  id           String          @id @default(uuid())
  userId       Int             @map("user_id")
  threadId     String?         @map("thread_id")
  filename     String
  mimeType     String          @map("mime_type")
  sizeBytes    Int             @map("size_bytes")
  markdown     String          @db.Text
  createdAt    DateTime        @default(now()) @map("created_at")
  chunks       DocumentChunk[]
}

model DocumentChunk {
  id           String   @id @default(uuid())
  documentId   String   @map("document_id")
  ordinal      Int
  heading      String?
  content      String   @db.Text
}

model Message {
  id          String     @id @default(uuid())
  threadId    String     @map("thread_id")
  sender      String     // 'user' | 'ai' | 'system'
  text        String     @db.Text
  toolResults Json?      @map("tool_results")
  createdAt   DateTime   @default(now()) @map("created_at")
}
```

---

## ⚙️ Environment Configuration

### 1. Express Backend Environment (`server/.env`)
```env
PORT=8000
NODE_ENV=development
JWT_SECRET=clever-ai-jwt-secret-key-change-in-prod
GOOGLE_CLIENT_ID=

# PostgreSQL Database Connection
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/clever_db
PGHOST=localhost
PGPORT=5432
PGUSER=postgres
PGPASSWORD=postgres
PGDATABASE=clever_db
```

### 2. Python Server Environment (`python_project/.env`)
```env
NVIDIA_API_KEY=[REDACTED]
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=[REDACTED]
LANGSMITH_PROJECT="your-project-name"
PORT=8001
HOST=0.0.0.0
```

---

## 🚀 Quickstart & How to Run

### Prerequisites
- **Node.js** >= 18
- **Python** >= 3.10 (Python 3.14 recommended for MarkItDown)
- **PostgreSQL** running locally on port 5432

---

### Step 1: Clone Repository & Install Dependencies

```bash
# 1. Install root React dependencies
cd "/Users/ankit/Desktop/AI & ML/ChatbotAgent"
npm install

# 2. Install Express Backend dependencies
cd server
npm install

# 3. Setup Python Virtual Environment (Python 3.14 recommended)
cd "/Users/ankit/Desktop/AI & ML/ChatbotAgent"
/opt/homebrew/bin/python3.14 -m venv python_project/venv
python_project/venv/bin/pip install -r python_project/requirements.txt
python_project/venv/bin/pip install "git+https://github.com/microsoft/markitdown.git#subdirectory=packages/markitdown" python-multipart
```

---

### Step 2: Initialize PostgreSQL Database

```bash
# Create PostgreSQL database clever_db
psql -U postgres -c "CREATE DATABASE clever_db OWNER postgres;" || true

# Run Prisma migrations & Client generation
cd server
npx prisma db push
npx prisma generate
```

---

### Step 3: Launch Services

Run each service in separate terminal windows:

#### Terminal 1 — Python FastAPI Server (Port 8001)
```bash
cd "/Users/ankit/Desktop/AI & ML/ChatbotAgent"
python_project/venv/bin/python python_project/app.py
```

#### Terminal 2 — Express Backend Server (Port 8000)
```bash
cd "/Users/ankit/Desktop/AI & ML/ChatbotAgent/server"
npm run dev
```

#### Terminal 3 — Vite React Frontend (Port 5174 / 5173)
```bash
cd "/Users/ankit/Desktop/AI & ML/ChatbotAgent"
npm run dev
```

Access the application in your browser at:
👉 **`http://127.0.0.1:5174/`**

---

## 📡 API Endpoint Reference

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `POST` | `/api/v1/auth/signup` | Register new user account | ❌ No |
| `POST` | `/api/v1/auth/login` | Email & password authentication | ❌ No |
| `POST` | `/api/v1/auth/google` | 1-Click Google OAuth SSO | ❌ No |
| `GET` | `/api/v1/auth/me` | Authenticated session token recovery | 🔑 Yes |
| `POST` | `/api/v1/chat` | Send chat prompt (multi-tool & RAG) | 🔑 Yes |
| `GET` | `/api/v1/chat/history` | Fetch user chat threads | 🔑 Yes |
| `POST` | `/api/v1/documents/upload` | Upload PDF/DOCX/XLSX for MarkItDown RAG | 🔑 Yes |
| `GET` | `/api/v1/memory/{thread_id}` | Inspect thread context memory | ❌ No |

---

## 📜 License & Author

- **Author**: Ankit (`ankitkumar700413@gmail.com`)
- **Repository**: [https://github.com/ankit435/CleverAI](https://github.com/ankit435/CleverAI)
- **License**: MIT License