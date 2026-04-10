# Data Model - Untitled request

## Runtime Entities
- Task
- StageRecord
- Approval
- Event
- DeliveryRecord

## Mermaid
```mermaid
erDiagram
  TASK ||--o{ STAGE_RECORD : contains
  TASK ||--o{ APPROVAL : waits_on
  TASK ||--o{ EVENT : emits
```

system-architect produced an artifact for design.
Key assumptions, risks, and next actions were captured for handoff.
VERDICT: PASS