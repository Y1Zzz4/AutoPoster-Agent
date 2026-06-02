# AutoPoster-Agent

Neuro-symbolic multi-agent system for automated academic poster generation. A Cartesian engine handles deterministic spatial bin-packing while LLM/VLM agents manage semantic pagination, visual critique, and iterative layout refinement.

## Architecture

```
                    ┌──────────────────────┐
                    │   PreprocessorAgent  │  Phase 0: Global text compression
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │     ParserAgent      │  Phase 1: Symbolic AST extraction
                    │                      │         + LLM semantic grouping
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │   SummarizerAgent    │  Phase 1.5: Pre-bake 4-tier LODs
                    └──────────┬───────────┘
                               │
               ┌───────────────┼───────────────┐
               │               │               │
      ┌────────▼────────┐ ┌───▼────┐ ┌────────▼────────┐
      │  PlannerAgent   │ │Cartesian│ │  CriticAgent    │
      │  (DeepSeek)     │ │ Engine │ │  (Qwen VLM)     │
      │  column alloc   │ │ heights│ │  visual review   │
      └────────┬────────┘ └───┬────┘ └────────┬────────┘
               │               │               │
               └───────────────┼───────────────┘
                               │  iterate until convergence
                    ┌──────────▼───────────┐
                    │   RendererEngine     │  Final: Playwright headless
                    └──────────────────────┘
```

**Key design:** symbolic geometry (no browser, no hallucination) is decoupled from neural composition (LLM for semantics, VLM for critique).

## Quick Start

### Prerequisites

- Python 3.10+
- Playwright Chromium (auto-installed on first run)

### Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

### Configuration

Create `.env` in the project root:

```env
DEEPSEEK_API_KEY=sk-your-deepseek-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
QWEN_API_KEY=your-qwen-key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

### Usage

Place your Markdown paper under `assets/inputs/` (e.g., `assets/inputs/my_paper/paper.md` with images alongside), then:

```bash
python main.py -i my_paper/paper.md
```

The generated poster is saved to `assets/outputs/<document_name>/`.

## Project Structure

```
├── main.py                     # Entry point
├── core/
│   ├── pipeline.py             # Main loop: Planner → Cartesian → Critic
│   ├── state_context.py        # SystemState & PosterCard Pydantic models
│   └── constrained_layout.py   # Deterministic Cartesian engine
├── agents/
│   ├── preprocessor_agent.py   # Global text compression (DeepSeek)
│   ├── parser_agent.py         # Neuro-symbolic markdown parsing
│   ├── summarizer_agent.py     # 4-tier LOD pre-computation
│   ├── planner_agent.py        # Column allocation + monotonicity enforcement
│   └── critic_agent.py         # VLM visual review (Qwen)
├── renderer/
│   ├── engine.py               # Playwright headless renderer
│   └── templates/
│       └── poster_template.html
└── utils/
    ├── api_client.py           # OpenAI-compatible client (DeepSeek + Qwen)
    └── logger.py               # Structured logging
```

## How It Works

### 1. Parsing (ParserAgent)

Markdown is tokenized via `markdown-it`. The AST is sliced at headings into raw sections. The LLM then semantically merges these into 3–5 cohesive `PosterCard` objects. Orphan text is routed to a default "Introduction" card.

### 2. LOD Pre-baking (SummarizerAgent)

Each card's text is compressed into 4 tiers and cached: 100% (original), 75%, 50%, 25%. This enables zero-cost runtime degradation when a column overflows.

### 3. Planning & Layout (PlannerAgent + Cartesian Engine)

The Planner assigns cards to `left_col` / `mid_col` / `right_col` and emits CSS overrides. Card heights are estimated via rigid-flex heuristics:

```
H_rigid = 80 + title_lines×40 + ⌈chars/45⌉×32 + <li>_count×15
H_flex  = image_count × 380
```

Monotonicity (`Zᵢ ≥ Zᵢ₋₁`) is enforced post-hoc to guarantee left-to-right reading flow.

### 4. Critique & Convergence (CriticAgent)

Each iteration is rendered headlessly and reviewed by a Qwen VLM. A composite loss drives convergence:

```
L = 100,000 × N_issues + σ²(column_heights)
```

The loop stops on Critic approval, loss stabilization (patience=2), or max iterations (5). A best-snapshot rollback ensures valid output even on non-convergence.

## Key Constraints

| Constraint | Mechanism |
|---|---|
| Non-overlapping layout | Coordinate accumulation in Cartesian engine |
| Monotonic reading flow | `Zᵢ ≥ Zᵢ₋₁` enforced on Planner output |
| Column overflow | Inner-loop LOD degradation (zero LLM cost) |
| Fallback guarantee | Rollback to lowest-loss snapshot if max iterations exhausted |
