# RAG Evaluation Report — 3M 2015 10-K Failure Analysis

## Objective

Stress-test the current RAG pipeline using a structured SEC filing (3M 2015 10-K) to identify retrieval weaknesses, ranking issues, and factual precision failures.

---

# Current Performance Summary

| Question | Score |
| -------- | ----- |
| Q1       | 1/10  |
| Q2       | 4/10  |
| Q3       | 2/10  |

**Average Score: 2.3/10**

Main issue:
The RAG retrieves **semantically adjacent chunks** instead of the **exact relevant chunk**.

Pattern:

- High semantic recall
- Very low precision
- Poor numerical retrieval
- Weak table extraction
- Bad temporal disambiguation

---

# Failure Case 1 — Employee Count Retrieval

## Question

As of December 31, 2015, how many employees did 3M have in total, and how many inside vs outside the United States?

---

## Ground Truth

Source: Item 1 — Business (Page 3)

- Total employees: **89,446**
- United States: **35,973**
- International: **53,473**

---

## RAG Output

Claimed:

- "Not explicitly stated"
- Retrieved retirement plan coverage
- Retrieved manufacturing facilities count

---

## Why It Failed

### 1. Semantic Drift

Query term:
`employees`

Retrieved:

- retirement plans
- employee benefits

Instead of:

- headcount statement

This means embedding similarity is overvaluing concept adjacency.

---

### 2. Poor Chunk Granularity

Likely chunk split:
The employee count exists inside a larger "Business Overview" chunk.

Possible causes:

- chunk too large
- important factual sentence buried
- low salience during embedding

---

### Fixes

#### Hybrid Search

Add BM25:

- lexical match for "employed"
- lexical match for "full-time equivalents"

Current:
Vector-only likely.

Needed:
Hybrid = BM25 + Dense Retrieval

---

#### Query Expansion

Expand:
employees → headcount, workforce, employed, full-time equivalents

---

#### Metadata Boosting

Boost sections:

- Business
- Overview
- Company Profile

for organizational factual queries.

---

# Failure Case 2 — R&D Expense Retrieval

## Question

How much did 3M spend in 2015 on:

1. Research, development and related expenses
2. Environmental capital projects

---

## Ground Truth

Research & Development:
**$1.763 billion**

Environmental Capital Projects:
**$26 million**

---

## RAG Output

Research:
**$45 million** ❌

Environmental:
**$26 million** ✅

---

## Why It Failed

### Numeric Hallucination via Wrong Retrieval

Likely retrieved an unrelated financial note.

This means:

- poor numeric anchoring
- no source verification against top-K
- model accepted first plausible number

---

### Missing Financial Section Prioritization

Correct answer is in:
`Research and Patents`

Likely not ranked high enough.

---

### Fixes

#### Numeric-Aware Re-ranking

When query contains:

- how much
- cost
- spend
- amount
- revenue

Boost chunks containing:

- $
- million
- billion
- financial tables

---

#### Section Weighting

Boost:

- Research
- Financial Summary
- Notes

---

#### Post-Retrieval Verification

Before generation:
if multiple numeric candidates exist,
compare based on semantic alignment.

---

# Failure Case 3 — Annual vs Quarterly Confusion

## Question

What were 3M’s:

1. Net sales in 2015
2. Net income attributable to 3M in 2015
3. How did both compare to 2014?

---

## Ground Truth

2015:

- Net sales: **$30.274B**
- Net income: **$4.833B**

2014:

- Net sales: **$31.821B**
- Net income: **$4.956B**

Comparison:

- Sales decreased by **$1.547B**
- Net income decreased by **$123M**

---

## RAG Output

Retrieved:

- Q4 sales = $7.3B
- Q4 net income = $1.038B

Claimed annual numbers missing.

---

## Why It Failed

### Temporal Resolution Failure

Query:
2015 annual

Retrieved:
Q4 2015

No understanding of:
annual > quarterly hierarchy.

---

### Table Parsing Weakness

Correct answer is inside:
Item 6 — Selected Financial Data

Likely:

- table chunking failed
- row/column relationships lost

---

### Fixes

#### Preserve Tables Properly

Current likely:
flattened badly

Needed:
Convert tables into structured row-wise chunks.

Example:

```json
{
  "year": 2015,
  "net_sales": "30,274",
  "net_income": "4,833"
}
```

---

#### Temporal Query Expansion

If query contains:
2015 net sales

Expand:
annual 2015 net sales
full-year 2015 net sales

Suppress:
quarterly

---

#### Re-ranker Rules

Prioritize:

- exact year match
- exact metric match
- table sections

---

# Root Cause Summary

---

## 1. Vector Search Too Fuzzy

Problem:
semantic neighbors > exact matches

Fix:
Hybrid retrieval

Recommended:
BM25 + BGE + Reciprocal Rank Fusion

---

## 2. No Cross-Encoder Re-ranking

Needed:
After retrieval:
top 20 → rerank → top 5

Recommended:
`bge-reranker-large`

This alone may improve factual retrieval massively.

---

## 3. Poor Chunking Strategy

Current likely:
uniform chunking

Bad for:

- financial tables
- business summaries
- itemized reports

Needed:
semantic chunking + section-aware chunking

Chunk by:

- headings
- tables
- bullet groups

---

## 4. No Section Metadata

Store:

```json
{
  "section": "Item 6",
  "title": "Selected Financial Data",
  "page": 15
}
```

Use metadata filtering.

---

## 5. No Numeric Reasoning Layer

Needed:
number-sensitive retrieval.

Boost:

- $ values
- percentages
- tabular rows

---

# Recommended Architecture

```text
PDF
 ↓
Layout-aware parser
 ↓
Section-aware chunker
 ↓
Table preservation layer
 ↓
Embeddings
 ↓
BM25 index
 ↓
Vector index
 ↓
Hybrid retrieval
 ↓
Cross-encoder reranker
 ↓
Top-K evidence
 ↓
LLM answer synthesis
 ↓
Answer verifier (optional)
```

---

# Priority Fix Order

## Highest impact:

1. Add BM25 hybrid retrieval
2. Add reranker
3. Improve chunking
4. Preserve tables properly

## Medium:

5. Add metadata filters
6. Add numeric-aware boosting

## Optional:

7. Add answer verification step

---

# Final Verdict

Current system behaves like:

> "good semantic search, bad factual search"

This is dangerous for:

- SEC filings
- legal docs
- contracts
- research papers
- financial reports

Current trust level:
**Low**

Expected improvement after fixes:
From **2.3/10 → 8/10+**
