# DeepGuard X — Infrastructure & Integration


## Project Overview

**DeepGuard X** is an intelligent document analysis system powered by Large Language Models (LLMs) using a RAG (Retrieval-Augmented Generation) pipeline. It supports PDF summarization and context-aware Q&A over uploaded documents.

The system features a dedicated security layer that scans every uploaded file for threats before processing, and a distributed processing engine that splits PDF indexing work across multiple machines on the local network to significantly reduce processing time.

---

## My Role

I am responsible for the **full infrastructure and integration layer** of the project, which includes:

- Designing and configuring the complete Docker environment and linking all services together
- Designing and implementing the distributed PDF processing system across the local network
- Configuring Nginx as a Reverse Proxy and unified gateway for the system
- Ensuring correct communication between all system components (Backend ← AI Engine ← Workers)

---

## System Architecture

```
User (Browser / Mobile)
              ↓
         Nginx :80
    (Single entry point)
         ↓          ↓
    Frontend      Backend
    React/Vite    Node.js
    :5173         :3000
                    ↓
              Cyber Service
              Python/FastAPI
              (Security scan)
                    ↓
              AI Engine
              Python/FastAPI
              (Runs on Windows Host)
              :8000
                    ↓
         Splits PDF across machines
         ↙                    ↘
   Manager machine         Worker machines
   (assigned pages)        Workers :8001
         ↘                    ↙
      Merges Vectors → Builds FAISS Index
              ↓
         Saved to vs_cache
```

---

## 1. Docker Environment (4 Core Containers)

I configured and linked four services inside a shared Docker network (`deepguard-network`), with all internal ports hidden from the outside. Nginx is the only externally exposed service.

### Services

| Service | Image / Code | Internal Port | Externally Accessible |
|---------|-------------|--------------|----------------------|
| MongoDB | `mongo:latest` | 27017 | No |
| Cyber Service | Python/FastAPI | 5000 | No |
| Backend | Node.js | 3000 | No |
| Frontend | React/Vite | 5173 | No |
| **Nginx** | `nginx:alpine` | **80** | **Yes — only gateway** |

### Why Hide the Ports?

In the original setup all ports were exposed externally, meaning the database and backend were directly reachable from any machine.
The new setup makes Nginx on port 80 the **single entry point** — all other services communicate only internally.

---



## 2. AI Engine — Running Outside Docker

The AI Engine runs directly on Windows (outside Docker) on port 8000.

**Reason:** LLM models require direct access to hardware resources (RAM / GPU). Running them inside Docker adds a virtualization layer that degrades performance.

The Backend container reaches it via:
```
http://host.docker.internal:8000
```
This is a special Docker address that allows containers to reach the Windows Host.

---

## 3. Distributed Processing System (Core Contribution)

### The Problem

Building a FAISS Vector Index from a large PDF on a single machine is slow — embedding generation through Ollama processes one chunk at a time sequentially.

### The Solution

Distribute the PDF pages across multiple machines that work in parallel, then merge all results into one unified index on the manager machine.

### How It Works

```
1. User uploads a PDF
         ↓
2. ai_server (manager) counts total pages
         ↓
3. Splits pages evenly across available machines
   Example: 57 pages, 2 machines:
   - Manager machine  ← pages 29 to 57
   - Worker machine   ← pages  1 to 28
         ↓
4. Each machine works simultaneously (parallel):
   - Extracts text from its assigned pages
   - Splits text into chunks (100 words per chunk)
   - Generates embeddings via local Ollama
   - Normalizes the vectors
         ↓
5. Manager collects results from all machines
         ↓
6. Merges all vectors into one matrix (single vstack)
         ↓
7. Builds one FAISS IndexFlatL2 from the full matrix
         ↓
8. Saves to disk in vs_cache keyed by fileId
         ↓
9. Any question → Manager searches the Index and answers
```



### Performance Results

| Mode | Approximate Time (57 pages) |
|------|-----------------------------|
| Single machine | ~5 minutes |
| 2 machines (distributed) | ~2.7 minutes |
| 3 machines | ~1.9 minutes |

---

## 6. Setting Up a Worker Machine

### Requirements

- Python 3.10+
- Ollama installed and running on port 11434
- Same embedding model: `nomic-embed-text`



## Running the System

### Core Services (Docker)

```bash
docker-compose up -d --build
```

### AI Engine (Windows Host)

```bash
cd ai_service
python api_server.py
```

### Worker on a Teammate's Machine

```bash
python worker_server.py
```

---

## Port Summary

| Service | Port | Externally Accessible |
|---------|------|-----------------------|
| Nginx (Gateway) | 80 | ✅ Yes |
| Frontend | 5173 | ❌ Internal only |
| Backend | 3000 | ❌ Internal only |
| Cyber Service | 5000 | ❌ Internal only |
| MongoDB | 27017 | ❌ Internal only |
| AI Engine | 8000 | On Windows Host directly |
| Worker | 8001 | On teammate's machine |

---

*Rawan Samy Nada — Infrastructure & Integration | Tanta University*
