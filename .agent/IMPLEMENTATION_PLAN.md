# StatementXL: The Cognitive Financial Engine

## Anti-Fragile Architecture Specification

> **Version:** 3.0 — Complete Rebuild  
> **Philosophy:** "Give the machine eyes to see and a brain to reason"  
> **Date:** December 2024

---

# Table of Contents

1. [Executive Summary: Beyond Deterministic Normalization](#1-executive-summary)
2. [The Failure of Rule-Based Extraction](#2-the-failure-of-rule-based-extraction)
3. [Vision-First Extraction Architecture](#3-vision-first-extraction-architecture)
4. [The Template Intelligence Revolution](#4-the-template-intelligence-revolution)
5. [Dynamic Knowledge Graph & Semantic Mapping](#5-dynamic-knowledge-graph--semantic-mapping)
6. [Human-in-the-Loop: Cognitive UX Design](#6-human-in-the-loop-cognitive-ux-design)
7. [Anti-Fragile Technical Stack](#7-anti-fragile-technical-stack)
8. [The Sovereign Data Pipeline](#8-the-sovereign-data-pipeline)
9. [Security-First Multi-Tenancy](#9-security-first-multi-tenancy)
10. [Reconstructed Implementation Roadmap](#10-reconstructed-implementation-roadmap)
11. [Appendices](#11-appendices)

---

# 1. Executive Summary

## The Fatal Flaw of the Original Plan

The original StatementXL rebuild plan relied on **"happy path" engineering** that catastrophically underestimated:

1. **The hostility of unstructured financial data** — Real 10-Ks and private company reports violate every assumption of rule-based parsers
2. **The computational requirements of semantic reasoning** — CPU-optimized embeddings sacrifice accuracy for pennies
3. **The cognitive limits of human operators** — 30%+ ambiguity rates cause "rubber stamping" that defeats audit trails

## The New Philosophy

> **From:** "Extract → Map"  
> **To:** "Understand → Reason → Generate"

StatementXL will become a **Cognitive Financial Engine** that:

- **Sees** documents through Vision-Language Models (not regex)
- **Reasons** through Graph Neural Networks (not heuristics)
- **Learns** through Dynamic Knowledge Graphs (not static YAML)
- **Validates** through Agentic Constraint Solving (not greedy algorithms)

## Core Architectural Shifts

| Original Approach | Anti-Fragile Replacement | Rationale |
|-------------------|--------------------------|-----------|
| Camelot/pdfplumber (rule-based) | LayoutLMv3 / TATR (vision-based) | Handles borderless tables, complex layouts |
| Tesseract OCR | TrOCR / PaddleOCR + Redundancy Check | Eliminates decimal precision errors |
| openpyxl static analysis | Headless Calc Engine + GNN | Evaluates formulas, detects true inputs |
| all-MiniLM-L6-v2 (23M params) | BGE-M3 / E5-Large (300M+ params) | Deep semantic understanding |
| Static YAML ontology (500 items) | Neo4j Knowledge Graph + RAG | Self-healing, expanding taxonomy |
| Greedy assignment algorithm | Agentic Solver (LangGraph) | Constraint satisfaction for accounting equation |
| Python-only stack | Polyglot (Rust parsing + Python AI) | 10-100x speedup, eliminates GIL |
| Security in Phase 8 | Security in Phase 1 (RLS + namespacing) | MNPI protection from day one |

---

# 2. The Failure of Rule-Based Extraction

## Why Camelot and pdfplumber Will Fail

The original plan proposed Camelot (lattice mode) for bordered tables and pdfplumber for borderless. This assumes table structure is binary. **It is not.**

### Catastrophic Failure Modes

#### 1. Borderless Table Destruction

- **Camelot's lattice mode** requires pixel-perfect ruling lines
- Modern financial documents remove vertical lines for aesthetics
- **Result:** 60%+ of real-world tables are invisible to lattice detection

#### 2. Variable Column Spacing

```
Financial Statement Example:
┌─────────────────────────────────────────────────────────┐
│          Three Months Ended    Six Months Ended        │
│          Dec 31    Dec 31      Dec 31     Dec 31       │
│          2024      2023        2024       2023         │
├─────────────────────────────────────────────────────────┤
│ Revenue  $1,500    $1,200      $2,900     $2,400       │
└─────────────────────────────────────────────────────────┘
```

- Spanning headers ("Three Months Ended") cause stream parsers to merge columns
- **Result:** 2023 data placed in 2024 column (silent corruption)

#### 3. Multi-line Row Fracturing

```
Depreciation and amortization
  of property, plant, and           $125,000    $118,000
  equipment
```

- Line-by-line parsers fracture this into 3 rows
- **Result:** Label decoupled from value, wrong associations

#### 4. Hierarchy Flattening

```
Current Assets:
    Cash and cash equivalents     $500,000
    Accounts receivable           $250,000
    Total Current Assets          $750,000
```

- Indentation = semantic hierarchy (parent-child)
- pdfplumber flattens this, losing structure

### Tesseract OCR Failures

| Failure Mode | Example | Impact |
|--------------|---------|--------|
| Decimal dropping | "1.00" → "100" | 100x magnitude error |
| Column bleed | "2023$1,000" merged | Nonsense tokens |
| Handwriting blindness | Margin notes ignored | Missing context |

---

# 3. Vision-First Extraction Architecture

## The Solution: See the Document as a Human Does

Instead of parsing text and inferring structure, we **detect structure visually first**, then map text into the grid.

### Primary Extraction Engine: TATR / LayoutLMv3

```
┌─────────────────────────────────────────────────────────────┐
│              VISION-FIRST EXTRACTION PIPELINE               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  INPUT: PDF Page Image (300 DPI)                            │
│                  │                                          │
│                  ▼                                          │
│  ┌────────────────────────────────────────┐                 │
│  │  Table Transformer (TATR)              │                 │
│  │  ─────────────────────────────         │                 │
│  │  • Object detection for tables         │                 │
│  │  • Row/column bounding boxes           │                 │
│  │  • Header detection                    │                 │
│  │  • Spanning cell detection             │                 │
│  └────────────────────────────────────────┘                 │
│                  │                                          │
│                  ▼                                          │
│  ┌────────────────────────────────────────┐                 │
│  │  Text Extraction (PaddleOCR)           │                 │
│  │  ─────────────────────────────         │                 │
│  │  • Transformer-based OCR               │                 │
│  │  • Context-aware correction            │                 │
│  │  • 2D spatial attention                │                 │
│  └────────────────────────────────────────┘                 │
│                  │                                          │
│                  ▼                                          │
│  ┌────────────────────────────────────────┐                 │
│  │  Grid Mapping                          │                 │
│  │  ─────────────────────────────         │                 │
│  │  • Map OCR tokens into TATR grid       │                 │
│  │  • Resolve multi-line labels           │                 │
│  │  • Preserve hierarchy via indent       │                 │
│  └────────────────────────────────────────┘                 │
│                  │                                          │
│                  ▼                                          │
│  OUTPUT: Structured Table JSON with confidence              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Model Specifications

| Component | Model | Parameters | Latency (CPU) | Accuracy |
|-----------|-------|------------|---------------|----------|
| Table Detection | TATR (microsoft/table-transformer-detection) | 110M | ~60ms/page | 95%+ |
| Structure Recognition | TATR-structure | 110M | ~80ms/page | 92%+ |
| OCR | PaddleOCR (en_PP-OCRv4) | 12M | ~100ms/page | 97%+ |
| **Total Pipeline** | - | - | **~250ms/page** | **90%+ end-to-end** |

### Redundancy Check for Critical Values

For numerical cells with high financial impact:

```python
async def extract_with_redundancy(cell_image: bytes) -> ExtractedValue:
    """Run dual OCR engines for critical value verification."""
    
    # Primary: PaddleOCR
    paddle_result = await paddle_ocr.extract(cell_image)
    
    # Secondary: EasyOCR
    easy_result = await easy_ocr.extract(cell_image)
    
    if paddle_result.value != easy_result.value:
        return ExtractedValue(
            value=paddle_result.value,  # Trust higher-accuracy model
            confidence=0.5,  # Flag for human review
            needs_verification=True,
            alternatives=[easy_result.value]
        )
    
    return ExtractedValue(
        value=paddle_result.value,
        confidence=0.95,
        needs_verification=False
    )
```

---

# 4. The Template Intelligence Revolution

## The Myth of Static Analysis

The original plan assumed:

- "Blue font = input cell" ❌
- "No formula = input" ❌
- openpyxl can parse formulas ❌

**Reality:**

- Formatting conventions are inconsistent
- Analysts hardcode formulas (e.g., `=100+50`)
- openpyxl cannot evaluate `INDIRECT`, `OFFSET`, `XLOOKUP`, or dynamic arrays

## The Solution: Headless Calculation + Graph Neural Networks

### Component 1: Formula Evaluation Engine

```python
# Using xlcalculator for formula evaluation
from xlcalc import ModelCompiler

class TemplateEngine:
    def __init__(self, excel_path: str):
        # Compile Excel into evaluatable model
        self.model = ModelCompiler().read_and_parse_archive(excel_path)
        
    def evaluate_cell(self, cell_ref: str) -> Any:
        """Evaluate formula and return computed value."""
        return self.model.evaluate(cell_ref)
    
    def get_true_dependencies(self, cell_ref: str) -> List[str]:
        """Resolve dynamic references like INDIRECT."""
        return self.model.get_input_addresses(cell_ref)
    
    def identify_true_inputs(self) -> List[str]:
        """Find cells that have no formula OR hardcoded formulas."""
        inputs = []
        for cell in self.model.cells:
            deps = self.get_true_dependencies(cell)
            if len(deps) == 0:  # No dependencies = true input
                inputs.append(cell)
            elif self._is_hardcoded_formula(cell):  # =100+50 style
                inputs.append(cell)
        return inputs
```

### Component 2: Cell-Type Classification GNN

Instead of brittle formatting heuristics, use a **Graph Neural Network** trained to predict cell types.

```
┌─────────────────────────────────────────────────────────────┐
│              SPREADSHEET AS GRAPH                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  NODES: Cells                                               │
│  ├── Content: value, formula, style                         │
│  ├── Position: row, column, sheet                           │
│  └── Embedding: text + visual features                      │
│                                                             │
│  EDGES:                                                     │
│  ├── SPATIAL: adjacent cells (up, down, left, right)        │
│  ├── FORMULA: dependency relationships                      │
│  ├── SEMANTIC: same-row labels linked to values             │
│  └── HIERARCHICAL: section → subsection → item              │
│                                                             │
│  OUTPUT: P(Label), P(Input), P(Header), P(Calculation)      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Training Data:** 1000+ annotated Excel templates from various industries.

**Model Architecture:**

- Based on CCNet (Cell Classification Network)
- 3-layer Graph Attention Network (GAT)
- ~5M parameters, CPU-runnable

---

# 5. Dynamic Knowledge Graph & Semantic Mapping

## The Static Ontology Trap

500 items in YAML is **hopelessly insufficient** for:

- Non-GAAP measures ("Community Adjusted EBITDA")
- Industry-specific metrics ("Daily Active Users")
- Related-party nuances ("Revenue from Related Parties")

## The Solution: Neo4j Knowledge Graph + RAG Expansion

### Knowledge Graph Schema

```cypher
// Core node types
CREATE (term:FinancialTerm {
    id: "revenue",
    label: "Revenue",
    gaap_code: "ASC 606",
    synonyms: ["Sales", "Net Sales", "Total Revenue"],
    definition: "Inflows from ordinary activities..."
})

// Hierarchical relationships
CREATE (term)-[:IS_A]->(parent:FinancialTerm {id: "income"})
CREATE (term)-[:PART_OF]->(section:Section {id: "income_statement"})
CREATE (term)-[:CALCULATED_FROM]->(cogs:FinancialTerm {id: "cogs"})

// Industry-specific variants
CREATE (softwareRevenue:FinancialTerm {
    id: "software_revenue",
    label: "Software Revenue",
    industry: "Technology"
})-[:IS_A]->(term)
```

### RAG-Based Ontology Expansion

When an extracted term doesn't match the core ontology:

```python
async def expand_ontology(unknown_term: str, context: str) -> OntologyNode:
    """Use RAG to classify and potentially add new terms."""
    
    # Query external financial corpus
    corpus_results = await rag_engine.query(
        query=f"What is '{unknown_term}' in financial statements? {context}",
        sources=["GAAP Codification", "IFRS Standards", "Investopedia"]
    )
    
    # LLM agent proposes classification
    proposal = await llm_agent.classify(
        term=unknown_term,
        context=context,
        corpus_knowledge=corpus_results
    )
    
    if proposal.is_synonym:
        # Map to existing term
        return existing_node
    else:
        # Propose new node (flagged for analyst confirmation)
        new_node = OntologyNode(
            label=unknown_term,
            proposed_parent=proposal.parent,
            confidence=proposal.confidence,
            requires_approval=True
        )
        await knowledge_graph.add_provisional(new_node)
        return new_node
```

### Upgraded Embedding Model

| Model | Parameters | Context Window | Financial Accuracy |
|-------|------------|----------------|-------------------|
| all-MiniLM-L6-v2 (original) | 23M | 256 tokens | ~72% |
| **BGE-M3** (recommended) | 560M | 8192 tokens | ~89% |
| **E5-Large-v2** (alternative) | 335M | 512 tokens | ~87% |

### Hierarchical Context Embedding

```python
def build_context_embedding(cell: Cell) -> Embedding:
    """Create semantic fingerprint from full cell lineage."""
    
    # Build context string with hierarchy
    context = f"""
    Sheet: {cell.sheet_name}
    Section: {cell.section}  # e.g., "Income Statement"
    Subsection: {cell.subsection}  # e.g., "Operating Expenses"
    Row Label: {cell.label}  # e.g., "Research and Development"
    Period: {cell.period}  # e.g., "FY2024"
    """
    
    # Use BGE-M3 for rich embedding
    return embedding_model.encode(context)
```

---

# 6. Human-in-the-Loop: Cognitive UX Design

## The Review Queue Problem

**Original Plan:** Flat list sorted by impact  
**Reality:** 30-40% ambiguity rate → analyst fatigue → rubber stamping

### Failure Modes

| Issue | Consequence |
|-------|-------------|
| Alert fatigue | 50+ items to review → "click-through" behavior |
| Context switching | Snippet view loses document context |
| Wrong prioritization | High-value items easy; obscure items break balance sheet |

## The Solution: Balance-Sheet-First Validation

### Core Insight

The analyst's job is not "data entry" — it's **puzzle solving**.

```
┌─────────────────────────────────────────────────────────────┐
│              BALANCE-SHEET-FIRST VALIDATION                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           ACCOUNTING EQUATION CHECK                 │    │
│  │                                                     │    │
│  │   Assets           $1,500,000                       │    │
│  │   Liabilities        $800,000                       │    │
│  │   Equity             $600,000                       │    │
│  │   ─────────────────────────────                     │    │
│  │   DIFFERENCE:       ⚠️ $100,000                     │    │
│  │                                                     │    │
│  │   [🔍 Find Missing Items]                           │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Clicking "Find Missing Items" triggers:                    │
│  • Semantic search for unmapped PDF items                   │
│  • Items summing to ~$100,000 highlighted                   │
│  • Analyst sees: "Retained Earnings: $100,000 (unmapped)"   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Synced Document View

```
┌─────────────────────────────────────────────────────────────┐
│                   SYNCED REVIEW UI                          │
├─────────────────────────┬───────────────────────────────────┤
│                         │                                   │
│    FULL PDF VIEW        │    EXCEL TEMPLATE                 │
│    (not snippet!)       │                                   │
│                         │                                   │
│    ┌───────────────┐    │    ┌─────────────────────────┐    │
│    │ Page 12       │    │    │ B10: Revenue            │    │
│    │               │    │    │ Value: $1,500,000       │    │
│    │    ┌─────────┐│    │    │ Confidence: 95%         │    │
│    │    │$1,500,000│◄───┼────│                         │    │
│    │    └─────────┘│    │    │ [✓ Accept] [✎ Override] │    │
│    │               │    │    └─────────────────────────┘    │
│    └───────────────┘    │                                   │
│                         │                                   │
│  Click cell → PDF       │    Click PDF → Cell               │
│  auto-scrolls to source │    auto-highlights in Excel       │
│                         │                                   │
└─────────────────────────┴───────────────────────────────────┘
```

### Active Learning Loop

```python
class ActiveLearningAdapter:
    """Retrain on analyst corrections in real-time."""
    
    async def on_analyst_correction(
        self,
        original_classification: Classification,
        corrected_classification: Classification,
        tenant_id: str
    ):
        # Store correction in training buffer
        self.correction_buffer.append({
            "input": original_classification.embedding,
            "target": corrected_classification.category,
            "tenant": tenant_id
        })
        
        # When buffer reaches threshold, train tenant-specific LoRA
        if len(self.correction_buffer) >= 10:
            await self.train_lora_adapter(tenant_id)
    
    async def train_lora_adapter(self, tenant_id: str):
        """Train lightweight adapter for tenant-specific patterns."""
        adapter = LoRAAdapter(base_model=self.embedding_model)
        await adapter.train(self.correction_buffer)
        await self.adapter_store.save(tenant_id, adapter)
```

---

# 7. Anti-Fragile Technical Stack

## The Python Problem

Python's Global Interpreter Lock (GIL) chokes on:

- Large PDF parsing
- Complex Excel DOM manipulation
- Concurrent file processing

openpyxl loading a complex LBO model can consume **gigabytes of RAM**.

## The Solution: Polyglot Architecture

### Layer Distribution

| Layer | Language | Libraries | Rationale |
|-------|----------|-----------|-----------|
| **File I/O** | Rust | calamine, pdf-rs | 10-100x faster, memory-safe |
| **Vision Models** | Python | transformers, ONNX | ML ecosystem |
| **Knowledge Graph** | Python | Neo4j driver | Graph queries |
| **API** | Python | FastAPI | Async, OpenAPI |
| **Worker Orchestration** | Go | Temporal | Reliable job execution |

### Rust-Python Integration

```rust
// Rust: High-performance Excel parsing (via PyO3)
use calamine::{Reader, Xlsx};
use pyo3::prelude::*;

#[pyfunction]
fn parse_excel_fast(path: &str) -> PyResult<Vec<CellData>> {
    let mut workbook: Xlsx<_> = open_workbook(path)?;
    let mut cells = Vec::new();
    
    for sheet_name in workbook.sheet_names() {
        if let Some(Ok(range)) = workbook.worksheet_range(&sheet_name) {
            for (row_idx, row) in range.rows().enumerate() {
                for (col_idx, cell) in row.iter().enumerate() {
                    cells.push(CellData {
                        sheet: sheet_name.clone(),
                        row: row_idx,
                        col: col_idx,
                        value: cell.to_string(),
                    });
                }
            }
        }
    }
    Ok(cells)
}
```

### Worker Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TEMPORAL WORKFLOW                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  API Request                                                │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────┐                                        │
│  │ Temporal Server │  ← Durable execution, auto-retry       │
│  └─────────────────┘                                        │
│       │                                                     │
│       ├──▶ Rust Worker: PDF Parsing                         │
│       │         └──▶ Returns: Page images, raw text         │
│       │                                                     │
│       ├──▶ Python Worker: TATR Extraction                   │
│       │         └──▶ Returns: Table structures              │
│       │                                                     │
│       ├──▶ Python Worker: Classification                    │
│       │         └──▶ Returns: Mapped line items             │
│       │                                                     │
│       └──▶ Python Worker: Excel Generation                  │
│                 └──▶ Returns: Populated template            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

# 8. The Sovereign Data Pipeline

## Complete Architecture Transformation

| Layer | Old Component | New Component | Improvement |
|-------|---------------|---------------|-------------|
| **Ingestion** | Python pdfplumber/openpyxl | Rust (pdf-rs, calamine) | 10x throughput, no GIL |
| **Extraction** | Camelot/Tesseract | LayoutLMv3/TATR + PaddleOCR | Vision-based, handles complexity |
| **Intelligence** | Heuristic rules ("blue font") | Graph Neural Network | Probabilistic cell detection |
| **Mapping** | MiniLM + Static YAML | BGE-M3 + Neo4j KG | Deep semantics, expanding ontology |
| **Validation** | Greedy algorithm | Agentic Solver (LangGraph) | Constraint satisfaction |

### Agentic Validation with LangGraph

```python
from langgraph.graph import StateGraph

class ValidationState(TypedDict):
    mappings: List[Mapping]
    balance_difference: float
    unmapped_items: List[ExtractedItem]
    iteration: int

def check_accounting_equation(state: ValidationState) -> ValidationState:
    """Calculate Assets - (Liabilities + Equity)."""
    assets = sum(m.value for m in state["mappings"] if m.category == "assets")
    liabilities = sum(m.value for m in state["mappings"] if m.category == "liabilities")
    equity = sum(m.value for m in state["mappings"] if m.category == "equity")
    
    state["balance_difference"] = assets - (liabilities + equity)
    return state

def find_missing_items(state: ValidationState) -> ValidationState:
    """Semantic search for items that could close the gap."""
    if abs(state["balance_difference"]) < 0.01:
        return state  # Balanced!
    
    # Search unmapped items for candidates
    target = state["balance_difference"]
    candidates = semantic_search(
        query=f"Find items summing to approximately ${target}",
        items=state["unmapped_items"]
    )
    
    return {**state, "candidates": candidates}

# Build validation graph
workflow = StateGraph(ValidationState)
workflow.add_node("check_equation", check_accounting_equation)
workflow.add_node("find_missing", find_missing_items)
workflow.add_edge("check_equation", "find_missing")
workflow.compile()
```

---

# 9. Security-First Multi-Tenancy

## Critical: Not a "Phase 8" Concern

Financial documents contain **Material Non-Public Information (MNPI)**. Security must be Phase 1.

### Risks of Deferred Security

| Risk | Consequence |
|------|-------------|
| Shared embedding space | Company A's data leaked to Company B |
| Global model training | Malicious mappings poison inference |
| No RLS | SQL injection exposes all tenants |

### Immediate Implementation

#### 1. Row-Level Security (Phase 1)

```sql
-- PostgreSQL RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON documents
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- All queries automatically filtered
CREATE FUNCTION set_tenant(tenant_id uuid) RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_tenant', tenant_id::text, false);
END;
$$ LANGUAGE plpgsql;
```

#### 2. Namespaced Vector Stores

```python
# Qdrant with strict tenant namespacing
class TenantIsolatedVectorStore:
    async def search(
        self,
        tenant_id: str,
        query_vector: List[float],
        limit: int = 10
    ) -> List[SearchResult]:
        return await self.qdrant.search(
            collection_name=f"embeddings_{tenant_id}",  # Tenant-specific collection
            query_vector=query_vector,
            limit=limit,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="tenant_id",
                        match=MatchValue(value=tenant_id)  # Double-check
                    )
                ]
            )
        )
```

#### 3. Federated LoRA Adapters

```python
class TenantAdapterManager:
    """Tenant-specific model adaptations - never shared."""
    
    async def get_adapter(self, tenant_id: str) -> LoRAAdapter:
        """Load tenant-specific adapter, never global."""
        adapter_path = f"adapters/{tenant_id}/lora_weights.pt"
        if await self.storage.exists(adapter_path):
            return await LoRAAdapter.load(adapter_path)
        return None  # Use base model if no tenant adapter
    
    async def train_adapter(self, tenant_id: str, corrections: List[Correction]):
        """Train isolated adapter - never pollutes global model."""
        adapter = LoRAAdapter(base_model=self.base_embedding_model)
        await adapter.train(corrections)
        await self.storage.save(f"adapters/{tenant_id}/lora_weights.pt", adapter)
```

---

# 10. Reconstructed Implementation Roadmap

## Fundamental Shift

> **HALT** the original Phase 1. Re-architect around Vision Transformers immediately.

### Phase 1: Vision-First Foundation (Week 1-2)

**Objective:** Build the Vision-Grid Extractor. Skip Camelot entirely.

| Task | Deliverable |
|------|-------------|
| Deploy TATR model | Table detection service |
| Integrate PaddleOCR | Layout-aware OCR service |
| Build Grid Mapper | Text → Structure alignment |
| Implement Rust parser | High-perf PDF/Excel I/O |
| Set up RLS | Tenant isolation from day 1 |

**Acceptance Criteria:**

- [ ] Extract tables from 20 diverse PDFs with >90% accuracy
- [ ] Handle borderless tables, multi-line rows, spanning headers
- [ ] Process 10-page PDF in <3 seconds
- [ ] Tenant A cannot see Tenant B's data

### Phase 2: Intelligent Template Engine (Week 2-3)

**Objective:** Build the GNN-based cell classifier with formula evaluation.

| Task | Deliverable |
|------|-------------|
| Integrate xlcalculator | Formula evaluation engine |
| Train Cell-Type GNN | Probabilistic input detection |
| Build Template Parser | Structure inference service |
| Deploy BGE-M3 | High-accuracy embeddings |

**Acceptance Criteria:**

- [ ] Correctly identify input cells on 10 diverse templates
- [ ] Evaluate INDIRECT, OFFSET formulas
- [ ] Embedding accuracy >85% on financial terms

### Phase 3: Knowledge Graph & RAG (Week 3-4)

**Objective:** Deploy Neo4j KG with RAG-based expansion.

| Task | Deliverable |
|------|-------------|
| Design KG schema | Neo4j ontology structure |
| Seed with 1000+ terms | Core financial taxonomy |
| Build RAG pipeline | LLM-powered term classification |
| Implement auto-expansion | Self-healing ontology |

**Acceptance Criteria:**

- [ ] Handle unknown terms via RAG lookup
- [ ] Propose new ontology nodes for analyst approval
- [ ] <500ms query latency

### Phase 4: Cognitive UX (Week 4-5)

**Objective:** Build the Balance-Sheet-First review UI.

| Task | Deliverable |
|------|-------------|
| Synced PDF/Excel view | Full-context review |
| Accounting equation checker | "Find Missing Items" |
| Active learning integration | Real-time LoRA training |
| Keyboard shortcuts | Power-user efficiency |

**Acceptance Criteria:**

- [ ] Analyst can solve balance discrepancies in <5 actions
- [ ] Corrections immediately improve future classifications
- [ ] No alert fatigue (focus on equation, not item list)

### Phase 5: Agentic Validation (Week 5-6)

**Objective:** Deploy LangGraph-based constraint solver.

| Task | Deliverable |
|------|-------------|
| Build validation workflow | Agentic solver |
| Implement backtracking | Constraint satisfaction |
| Add trend analysis | Outlier detection |

**Acceptance Criteria:**

- [ ] Automatically balance 80%+ of documents
- [ ] Flag Revenue drops >50% YoY as potential errors
- [ ] Provide actionable suggestions for discrepancies

### Phase 6: Enterprise Hardening (Week 6-8)

**Objective:** Production-ready security, performance, observability.

| Task | Deliverable |
|------|-------------|
| GPU embedding service | Triton Inference Server |
| Temporal workers | Durable job execution |
| SOC 2 controls | Audit logging, encryption |
| Load testing | 100 concurrent users |

---

# 11. Appendices

## Appendix A: Model Specifications

### TATR (Table Transformer)

```yaml
model: microsoft/table-transformer-detection
task: object-detection
input: PDF page image (300 DPI)
output: 
  - table bounding boxes
  - row bounding boxes
  - column bounding boxes
  - header cells
performance:
  accuracy: 95%+ on PubTables1M
  latency: 60-100ms per page (CPU)
```

### BGE-M3

```yaml
model: BAAI/bge-m3
task: dense-retrieval
input: text (up to 8192 tokens)
output: 1024-dim embedding
performance:
  mteb_score: 66.1 (vs MiniLM: 56.3)
  financial_accuracy: ~89%
```

### Cell-Type GNN

```yaml
architecture: 3-layer Graph Attention Network
input_features:
  - cell content embedding (768-dim)
  - position encoding (row, col)
  - formula topology features
  - style features (optional)
output: P(Label), P(Input), P(Header), P(Calc)
parameters: ~5M
latency: 10ms per spreadsheet (CPU)
```

## Appendix B: GPU Infrastructure

For production embedding service:

```yaml
# AWS Lambda with GPU (coming 2024) or:
# NVIDIA Triton Inference Server
service: triton-inference
model: bge-m3
instance: g4dn.xlarge (NVIDIA T4)
concurrency: 100 requests
latency: <10ms per embedding
cost: ~$0.50/hour

# Alternative: Modal.com serverless GPU
modal deploy embedding_service.py
```

## Appendix C: Comparison Table

| Aspect | Original Plan | Anti-Fragile Architecture |
|--------|---------------|---------------------------|
| **Table Extraction** | Camelot + pdfplumber (rule-based) | TATR + LayoutLMv3 (vision-based) |
| **OCR** | Tesseract | PaddleOCR + TrOCR + redundancy |
| **Cell Detection** | "Blue font" heuristic | Graph Neural Network |
| **Embeddings** | all-MiniLM-L6-v2 (23M) | BGE-M3 (560M) |
| **Ontology** | Static YAML (500 items) | Neo4j KG + RAG expansion |
| **Validation** | Greedy assignment | Agentic constraint solver |
| **Review UI** | Flat item list | Balance-sheet-first puzzle |
| **Learning** | None | Active learning LoRA adapters |
| **Parsing** | Python-only | Rust + Python polyglot |
| **Security** | Phase 8 | Phase 1 (RLS + namespacing) |

---

## Conclusion: The Path to Success

> "The path to success lies not in finding a cleaner regex, but in giving the machine the eyes to see and the brain to reason."

The original plan would produce a system that:

- ❌ Fails silently on real-world documents
- ❌ Frustrates analysts with high error rates
- ❌ Cannot achieve audit-grade reliability

The Anti-Fragile Architecture will produce a **Cognitive Financial Engine** that:

- ✅ Sees documents through Vision Transformers
- ✅ Reasons through Graph Neural Networks
- ✅ Learns through Dynamic Knowledge Graphs
- ✅ Validates through Agentic Constraint Solving

**Recommendation:** Halt the original Phase 1 and re-architect immediately. The investment in Vision-First extraction will pay dividends across every downstream component.

---

*Awaiting your approval to begin Phase 1: Vision-First Foundation.*
