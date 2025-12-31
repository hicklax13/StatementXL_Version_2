# StatementXL - AI Handoff Prompt

## Copy-Paste This to Any New AI Model

---

### SYSTEM CONTEXT

You are continuing work on **StatementXL**, a Cognitive Financial Engine that converts financial PDFs into populated Excel models using Vision-Language Models, Graph Neural Networks, and Dynamic Knowledge Graphs.

**IMPORTANT:** Before doing anything, read these files in order:

1. `.agent/AI_CONTEXT.md` - Project overview and golden rules
2. `.agent/PROGRESS.md` - Current status and what's next
3. `.agent/IMPLEMENTATION_PLAN.md` - Complete technical specification
4. `.agent/DECISIONS.md` - All architectural decisions

---

### QUICK STATUS CHECK

Run this command to see current progress:

```bash
cat .agent/PROGRESS.md
```

---

### PROJECT LOCATION

```
c:\Users\conno\OneDrive\Desktop\StatementXL_Version_2
```

---

### GOLDEN RULES (NEVER VIOLATE)

1. **Vision-First:** Use TATR/LayoutLMv3 for extraction, NOT Camelot/pdfplumber
2. **Dynamic Ontology:** Use Neo4j Knowledge Graph, NOT static YAML
3. **Security First:** Implement RLS immediately, NOT in Phase 8
4. **GNN for Cells:** Use Graph Neural Networks, NOT "blue font" heuristics
5. **Agentic Validation:** Use LangGraph constraint solver, NOT greedy algorithms
6. **Update Progress:** Always update `.agent/PROGRESS.md` after work

---

### CURRENT PHASE

Check `.agent/PROGRESS.md` for the current phase. As of last session:

- **Phase:** Phase 1 - Vision-First Foundation
- **Status:** NOT STARTED - Awaiting approval

---

### HOW TO RUN THE APP

```bash
# Backend
cd c:\Users\conno\OneDrive\Desktop\StatementXL_Version_2
python -m uvicorn backend.main:app --port 8000 --reload

# Frontend
cd frontend
npm run dev
```

---

### AFTER YOUR SESSION

Update `.agent/PROGRESS.md` with:

- What you completed
- Any blockers
- What's next
- Session timestamp

---

*This ensures the next AI can pick up exactly where you left off.*
