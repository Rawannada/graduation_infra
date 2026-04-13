# DeepGrade X: Hybrid Infrastructure & Integration

This repository serves as the central integration and orchestration layer for the **DeepGrade X** project. It manages the connectivity between various microservices to ensure a seamless flow from document upload to AI analysis.

---

## Project Concept

**DeepGrade X** is an intelligent document grading and analysis system powered by **Large Language Models (LLMs)**, featuring a dedicated security layer to scan files for potential threats and adversarial attacks before processing.

---

## System Architecture & Orchestration

The project utilizes a **hybrid architecture** designed to balance portability with high-performance resource allocation.  
The infrastructure is managed using **Docker Compose** to orchestrate the core services.

---

## 1. Dockerized Environment (4 Core Containers)

I have configured and linked four primary services within a Docker environment to ensure consistent deployment:

### Backend Node (Node.js/TypeScript)
- The central hub managing business logic, user authentication, and service communication.  
- **Port:** `3000`

### Cyber Security Service (Python/FastAPI)
- A dedicated container for structural PDF validation and threat detection.  
- **Port:** `5000`

### Frontend Node (React/Vite)
- The interactive user dashboard for file management and reporting.  
- **Port:** `5173`

### Database (MongoDB)
- Persistent storage for system data and analysis logs.  
- **Port:** `27017`

---

## 2. Native Execution (Windows Host)

### AI Engine (Python/FastAPI)
- The LLM and RAG pipeline are executed directly on the Windows Host (**outside Docker**) on port **8000**.

#### Technical Justification
This allows the AI models to have **direct access to hardware resources (GPU/RAM)**, significantly improving processing speed for document analysis.

---


## Deployment

### Orchestrated Services

Build and run the 4 core containers using:

```bash
docker-compose up -d --build
```
### AI Engine

Manually executed on the Windows environment to ensure optimal resource allocation.

---

## Ports Mapping Summary

| Service | Port |
|---------|------|
| Frontend | 5173 |
| Backend API | 3000 |
| Security Service | 5000 |
| AI Engine (Host) | 8000 |

---
  **Shutdown:**
```bash
    docker-compose down
```


**Developed by: Rawan Samy Nada**
*(Infrastructure & Integration)| Tanta University*