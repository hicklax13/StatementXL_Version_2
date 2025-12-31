# StatementXL AI Context & Handoff System

## 🚀 START HERE - For Any AI Model

**Read this file first.** This is the master context for the StatementXL project.

---

## Project Identity

**Name:** StatementXL - The Cognitive Financial Engine  
**Purpose:** AI-powered financial statement normalization: PDF → Structured Data → Excel  
**Repository:** `c:\Users\conno\OneDrive\Desktop\StatementXL_Version_2`

---

## Critical Files to Read (In Order)

### 1. Implementation Plan (THE MASTER PLAN)

```
.agent/IMPLEMENTATION_PLAN.md
```

This is the comprehensive Anti-Fragile Architecture specification. Read this to understand:

- Vision-First extraction (TATR, LayoutLMv3)
- Graph Neural Networks for cell classification
- Neo4j Knowledge Graph with RAG expansion
- Balance-Sheet-First UX design
- Agentic validation with LangGraph
- Polyglot Rust+Python stack
- Security-first multi-tenancy

### 2. Current Progress & Status

```
.agent/PROGRESS.md
```

This file tracks what has been completed and what's next. **ALWAYS check this first** to know where to pick up.

### 3. Technical Decisions Log

```
.agent/DECISIONS.md
```

Records all architectural decisions and their rationale.

---

## How to Continue Work

### Step 1: Check Progress

```bash
# Read the progress file
cat .agent/PROGRESS.md
```

### Step 2: Understand Current Phase

The project follows these phases:

1. **Phase 1:** Vision-First Foundation (TATR, PaddleOCR, Rust parser)
2. **Phase 2:** Intelligent Template Engine (GNN, xlcalculator)
3. **Phase 3:** Knowledge Graph & RAG (Neo4j, BGE-M3)
4. **Phase 4:** Cognitive UX (Balance-Sheet-First, synced view)
5. **Phase 5:** Agentic Validation (LangGraph constraint solver)
6. **Phase 6:** Enterprise Hardening (GPU, Temporal, SOC 2)

### Step 3: Update Progress When Done

After completing any task, update `.agent/PROGRESS.md` with:

- What you completed
- Any blockers encountered
- What's next

---

## Technology Stack Summary

| Layer | Technology | Status |
|-------|------------|--------|
| **Backend** | FastAPI (Python 3.11+) | Existing |
| **AI Classification** | Gemini 1.5 Flash + Ollama | Existing |
| **PDF Extraction** | TATR + PaddleOCR | TO IMPLEMENT |
| **Excel Parsing** | Rust (calamine) + xlcalculator | TO IMPLEMENT |
| **Knowledge Graph** | Neo4j | TO IMPLEMENT |
| **Embeddings** | BGE-M3 | TO IMPLEMENT |
| **Cell Classification** | Graph Neural Network | TO IMPLEMENT |
| **Validation** | LangGraph Agentic Solver | TO IMPLEMENT |
| **Frontend** | React + TypeScript + Zustand | Existing (needs rewrite) |

---

## Running the Application

```bash
# Terminal 1: Backend
cd c:\Users\conno\OneDrive\Desktop\StatementXL_Version_2
python -m uvicorn backend.main:app --port 8000 --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

---

## Key Contacts & Resources

- **Implementation Plan:** `.agent/IMPLEMENTATION_PLAN.md`
- **Progress Tracker:** `.agent/PROGRESS.md`
- **Decisions Log:** `.agent/DECISIONS.md`
- **Test PDFs:** `tests/fixtures/` directory

---

## Golden Rules

1. **Never use rule-based extraction (Camelot/pdfplumber)** — Use Vision models
2. **Never use static YAML ontology** — Use dynamic Knowledge Graph
3. **Security is Phase 1, not Phase 8** — Implement RLS immediately
4. **Balance-Sheet-First UX** — Not flat item lists
5. **Update PROGRESS.md after every session** — Keep continuity

---

*Last Updated: December 2024*
