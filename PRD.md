# PRD — Karyalaya AI (Air-Gapped Agentic AI for Govt/Defence/PSU)

## Problem
Refineries, PSUs, and defence manufacturing units generate sensitive routine knowledge work (approval notes, inspection reports, calculations, internal code, drawing review). This data can't touch cloud AI due to confidentiality mandates. Result: staff either do this by hand, or leak data by pasting it into public tools anyway. No deployable on-prem alternative exists today.

## Target users
- Plant engineers reviewing inspection reports and drawings
- Approval/compliance officers drafting sign-off notes
- Internal tooling developers writing scripts for plant systems
- Admin staff processing scanned correspondence and vendor documents

## Target hardware (prototype)
- Primary dev/demo machine: MacBook M4, 16GB+ unified memory (24GB+ preferred for smoother multitasking).
- No GPU/CUDA required — Apple Silicon runs quantized models natively via Ollama.
- Model size cap on this hardware: Lightweight quantized models (Q4/Q5). Google Gemma 4 E4B (`gemma4:e4b`) and `qwen2.5-coder:7b` fit comfortably within laptop memory.
- This is a prototype-grade deployment. Production deployment on an org GPU server removes these size caps.

## Core value proposition
A self-hosted, air-gapped AI workbench that gives users the Claude/Codex-style experience (agentic, multimodal, tool-using) with zero data leaving the organization's GPU server.

## Must-have features (v1 demo scope)
1. **Model router** — auto-selects the right open-weight model per task type (code → `qwen2.5-coder:7b` / document reasoning & vision → Google Gemma 4 E4B `gemma4:e4b`), config-driven so new models can be added without code changes.
2. **Agentic loop** — plans multi-step tasks, calls tools (file read/write, code sandbox, doc search, spreadsheet, doc generation), iterates instead of single-shot replying.
3. **Multimodal ingestion** — reads scanned PDFs, handwritten notes, photographs, engineering drawings via local OCR + `gemma4:e4b` vision-language capabilities (with `qwen2-vl:7b` fallback).
4. **Real deliverables** — outputs actual .docx/.xlsx files and runnable/verified code, not just chat text.
5. **Local knowledge base (RAG)** — grounds answers in the org's own manuals/SOPs/correspondence, fully local ChromaDB vector store.
6. **Sovereignty proof** — live network monitor/dashboard showing zero external calls at any point during operation.

## Explicit non-goals (v1)
- No internet-connected tools (no web search, no external APIs) — this is a hard constraint, not a missing feature.
- No multi-user auth/RBAC system (single-workstation demo scope; noted for future real deployment).
- No fine-tuning pipeline — use off-the-shelf open-weight models.

## Success criteria (demo)
- Model auto-selection shown across ≥2 task types with visible routing decision log.
- End-to-end agentic task: scanned inspection report → extracted findings → drafted approval note → exported as .docx.
- Coding task: code generated, run in sandbox, verified (test passes or output matches expectation), self-corrected on failure.
- Multimodal task: image/scanned doc understanding demonstrated live.
- Network monitor showing 0 outbound connections throughout the entire demo.

## Users' definition of "it works"
They can hand the system a messy scanned report and get back a properly formatted approval note in under 2 minutes, without ever seeing an internet call fire.

## Known prototype limitations (be upfront about these)
- OCR/handwriting accuracy will be rough on messy scans — good enough to prove the concept, not production-polished.
- Response speed on a laptop is noticeably slower than a GPU server — fine for a demo, not for daily heavy use.
- Everything used (Ollama, PaddleOCR, ChromaDB, python-docx, model weights) is free and open-source — zero licensing cost to build or demo this.
