# StatementXL Technical Decisions Log

## Purpose

This document records all major architectural and technical decisions for the StatementXL Cognitive Financial Engine.

---

## Decision Record

### DEC-001: Vision-First Extraction Architecture

**Date:** 2024-12-29  
**Status:** APPROVED  
**Decision:** Replace rule-based extraction (Camelot/pdfplumber) with Vision-Language Models (TATR/LayoutLMv3)

**Context:**

- Rule-based extractors fail on 60%+ of real-world financial documents
- Borderless tables, spanning headers, and multi-line rows cause silent corruption
- Forensic audit identified this as the "most critical point of failure"

**Alternatives Considered:**

1. ❌ Camelot (lattice mode) - Requires pixel-perfect ruling lines
2. ❌ pdfplumber (stream mode) - Brittle whitespace heuristics
3. ✅ TATR/LayoutLMv3 - Treats tables as visual objects

**Consequences:**

- Requires ~250ms per page (vs ~50ms for rule-based)
- Needs model download (~400MB)
- Dramatically improved accuracy on complex documents

---

### DEC-002: Transformer-Based OCR

**Date:** 2024-12-29  
**Status:** APPROVED  
**Decision:** Replace Tesseract with PaddleOCR + TrOCR with redundancy checking

**Context:**

- Tesseract frequently drops decimals ("1.00" → "100")
- Column bleed merges adjacent values
- Financial documents require 99.9% numerical accuracy

**Consequences:**

- Slightly higher latency
- Redundancy check catches 95%+ of OCR disagreements
- Critical values flagged for human verification

---

### DEC-003: Graph Neural Network for Cell Classification

**Date:** 2024-12-29  
**Status:** APPROVED  
**Decision:** Replace "blue font" heuristics with GNN-based probabilistic cell type detection

**Context:**

- Visual formatting conventions are inconsistent across templates
- Analysts hardcode formulas or overwrite with "plugs"
- Static analysis cannot detect true input vs. calculated cells

**Consequences:**

- Requires training data (1000+ annotated templates)
- Generalizes to unseen templates
- Provides confidence scores for each prediction

---

### DEC-004: Dynamic Knowledge Graph

**Date:** 2024-12-29  
**Status:** APPROVED  
**Decision:** Replace static YAML ontology (500 items) with Neo4j Knowledge Graph + RAG expansion

**Context:**

- Financial reporting evolves constantly (new Non-GAAP measures)
- Static lists become stale immediately
- Need to handle industry-specific and company-specific terminology

**Consequences:**

- Requires Neo4j infrastructure
- Self-healing ontology via RAG-based expansion
- Analyst confirmations train the system

---

### DEC-005: BGE-M3 Embeddings

**Date:** 2024-12-29  
**Status:** APPROVED  
**Decision:** Replace all-MiniLM-L6-v2 (23M) with BGE-M3 (560M) or E5-Large

**Context:**

- MiniLM lacks nuanced financial understanding
- Cannot distinguish "EBITDA" vs "Adjusted EBITDA" vs "EBITDAR"
- Benchmarks show 17+ point accuracy improvement

**Consequences:**

- Requires GPU for production (or high-latency CPU)
- Significantly better semantic matching
- Cost increase negligible vs. error correction costs

---

### DEC-006: Agentic Validation (LangGraph)

**Date:** 2024-12-29  
**Status:** APPROVED  
**Decision:** Replace greedy assignment with LangGraph-based constraint solver

**Context:**

- Greedy algorithms cannot backtrack
- Accounting equation must balance exactly
- Need to "find missing items" that close gaps

**Consequences:**

- More complex implementation
- Treats validation as constraint satisfaction problem
- Dramatically better balance sheet reconciliation

---

### DEC-007: Security in Phase 1

**Date:** 2024-12-29  
**Status:** APPROVED  
**Decision:** Implement PostgreSQL RLS and namespaced vector stores immediately (not Phase 8)

**Context:**

- Financial documents contain MNPI (Material Non-Public Information)
- Shared embedding spaces risk cross-tenant data leakage
- Global model training risks poisoning attacks

**Consequences:**

- Slightly more complex initial setup
- Tenant isolation from day one
- Federated LoRA adapters (never global training)

---

### DEC-008: Polyglot Architecture (Rust + Python)

**Date:** 2024-12-29  
**Status:** APPROVED  
**Decision:** Use Rust for file I/O (PDF parsing, Excel reading) with Python for AI/ML

**Context:**

- Python GIL chokes on concurrent large file processing
- openpyxl consumes gigabytes for complex models
- 10-100x speedup possible with Rust

**Consequences:**

- Requires Rust toolchain
- PyO3 bindings for Python interop
- Eliminates GIL bottleneck

---

### DEC-009: Balance-Sheet-First UX

**Date:** 2024-12-29  
**Status:** APPROVED  
**Decision:** Replace flat review queue with accounting equation-focused validation UI

**Context:**

- 30-40% ambiguity rate causes "rubber stamping"
- Flat lists prioritize wrong items
- Analysts are puzzle-solvers, not data-entry clerks

**Consequences:**

- Show Assets - (Liabilities + Equity) difference
- "Find Missing Items" semantic search
- Synced PDF/Excel view with bounding boxes

---

## Pending Decisions

| ID | Topic | Status | Notes |
|----|-------|--------|-------|
| DEC-010 | GPU infrastructure provider | PENDING | AWS Lambda GPU vs. Modal.com vs. self-hosted |
| DEC-011 | Temporal vs. Celery | PENDING | Worker orchestration choice |
| DEC-012 | Authentication provider | PENDING | Auth0 vs. Supabase vs. Keycloak |

---

*Update this file when making significant architectural decisions.*
