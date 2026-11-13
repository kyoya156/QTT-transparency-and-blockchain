# Correction tickets: spec for the Core database (Topic 4)

Prototype: `app/api/tickets.py` in this repo (26 tests). This page is the contract for adopting it in the Core DB.
Idea from the team: when finance finds a number is wrong, they send a ticket instead of editing.

## Why
Finance and volunteer are read-only, and the architecture says corrections create versions and financial or audit history is never hard-deleted. A ticket gives a controlled, audited way to fix data (maker-checker, segregation of duties).

## Flow
```
finance/volunteer  --open-->  OPEN  --admin approve-->  APPROVED  --dev applies-->  APPLIED
                                 |--admin reject (note required)--> REJECTED
                                 |--requester cancel--> CANCELLED
```
| Step | Who | Rule |
|---|---|---|
| Open | finance, volunteer | Only on tables they may read. Not on system tables or `audit_log`. |
| Approve / reject | admin | Not the requester. A rejection needs a note. |
| Apply | dev | Only after approval. Not the requester and not the approver. Records the value actually applied. |
| Cancel | requester | Only while OPEN. |
| Read | requester; admin and dev see all | Other users get 404, not 403, so ticket existence is not leaked. |

The AI assistant may draft a ticket and attach the evidence it found. It never approves or applies (architecture slide 07).

## Suggested tables (map to the `ApprovalRequest` / `ApprovalDecision` pair in 06_Core_Data_Model)
`correction_ticket`: id, requester_id (FK app_user), table_name, record_id, field_name, current_value, proposed_value, reason, evidence, status, created_at.
`ticket_decision`: ticket_id, decided_by, decision, note, decided_at.
`ticket_application`: ticket_id, applied_by, applied_value, note, applied_at.
The prototype keeps these in one table for simplicity.

## Audit
Every step writes `audit_log` with `correlation_id = "ticket:<id>"` (the ERD already has `correlation_id`, `before_data`, `after_data`, `change_reason`). On apply: before = current value, after = applied value, reason = ticket reason.

## Financial corrections
Do not overwrite `bank_transaction`, `transaction_allocation` or `disbursement` history. Apply a correction as a new version or an adjustment row that points to the original, so the report can show both. The prototype only records that dev made the change; it does not write to the Core DB.

## Checks for Topic 4
- Uniqueness and constraints still hold after a correction (unique external transaction, one active assignment per code and year).
- The applying dev change and the audit row happen in one database transaction.
- Test: finance cannot edit directly; volunteer cannot open a ticket on finance tables; a rejected or applied ticket cannot change state.
