# CleverAI

Monorepo for the CleverAI project — fullstack chatbot agent with a React + Vite frontend, a Node backend, and Python services for model code.

## Repository layout

- `server/` — Node backend (TypeScript) with Prisma and API routes.
- `src/` — React + Vite frontend application.
- `python_project/` — Python project with model code and chains.
- `python_server/` — Lightweight Python server entrypoint.

## Requirements

- Node.js >= 18
- npm
- Python 3.10+
- (optional) venv or virtualenv for Python environments

## Quick setup

1. Install Node dependencies (root and server):

```bash
cd "$(pwd)"
npm install
cd server && npm install
```

2. Install Python dependencies (use virtualenv recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python_project/requirements.txt
pip install -r python_server/requirements.txt
```

3. Run services

- Start backend server (from `server`):

```bash
cd server
npm run dev
```

- Start frontend (from repo root):

```bash
npm run dev
```

- Start Python server (if applicable):

```bash
cd python_server
python main.py
```

## Files of interest

- `server/src` — API routes and Prisma configs
- `src/` — frontend components and pages
- `python_project/` — model and chain implementations

## Notes

- A `.gitignore` has been added and the project was imported in five logical commits on the `main` branch. A branch `import/split-commits` exists in the remote if you want to review the split commits.

## Contribution

Open an issue or PR on GitHub: https://github.com/ankit435/CleverAI