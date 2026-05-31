# chatbot simple

## what we are preparing 

A application with interface:
to provide the chat interface to connect with LLM and chat

## stack

| Layer                         | Choice                             |
| ----------------------------- | ---------------------------------- |
| Frontend UI                   | Streamlit                          |
| LLM Model                     | Gemma4:e2b (7.2 GB)                |
| LLM Serving                   | Ollama local setup not in Kubernetes(local cluster)|
| Containerization              | Docker                             |
| Container Orchestration       | Kubernetes (Local Cluster)         |
| Kubernetes Package Management | Helm                               |
| CI/CD Source Control          | GitHub                             |
| CI/CD Pipeline                | GitHub Actions                     |
| Image Registry                | Docker Hub        |
| Operating System              | windows      |


## Planning
- Save all plans to `.agent/plans/` folder
- Naming convention: `{sequence}.{plan-name}.md` (e.g., `1.auth-setup.md`, `2.document-ingestion.md`)
- Plans should be detailed enough to execute without ambiguity
- Each task in the plan must include at least one validation test to verify it works
- Assess complexity and single-pass feasibility - can an agent realistically complete this in one go?
- Include a complexity indicator at the top of each plan:
  - ✅ **Simple** - Single-pass executable, low risk
  - ⚠️ **Medium** - May need iteration, some complexity
  - 🔴 **Complex** - Break into sub-plans before executing


## Development Flow
1. **Plan** - Create a detailed plan and save it to `.agent/plans/`
2. **Build** - Execute the plan to implement the feature
3. **Validate** - Test and verify the implementation works correctly. Use browser testing where applicable via an appropriate MCP
4. **Iterate** - Fix any issues found during validation  

## Progress
Check PROGRESS.md for current module status. Update it as you complete tasks.

## Phase 1

###  Module 1 - chatbot UI implementaion 


### Module 2 - git hub and CI pipeline


### MOdule 3 - helm charts and kubernetes local server deployment


### Module 4 - ArgoCD for automatic deployment

### Module 5 - CI pipeline improvements


### Module 6 - Suggested Follow-up Questions - significantly increases user interaction

### Module 7 - Observibity using 

## Phase 1 completed

## Phase 2 - Data Ingestion flow

## Module 8 -  user upload the excel files from UI to DB
     1.Basic ingestion (validate → parse → store) , we have multiple tables to be created
     2.client_id details are not required in any table
     Table 1 : daily_positions
     3.schema for the each table will be provided with reference excel file in @raw_data_files , eg : for daily_positions table check the raw_data_files and daily_positions folder
     4. do not allow duplicate records , make tradeday + symbol as the key for the daily_positions table





