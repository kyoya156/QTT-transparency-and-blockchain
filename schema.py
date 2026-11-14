"""Database schema for the Quỹ Minh Bạch Tài Chính Topic 4 financial transparency system.

Design decisions worth stating, because each one is traceable to evidence:

1. `TransactionAllocation` is mandatory, not optional. 9,493 real multi-code
   transactions show one bank row funding up to 20 NE codes. Money lives on
   `bank_transactions` exactly once; allocations carry the split. This is what
   stops the same 2,900,000đ being counted five times.

2. `amount_allocated` on the allocation row can be NULL, meaning "the fund does
   not publish which pupil got which đồng". We record a computed split in
   `allocated_amount_computed` plus the policy used, so the number is always
   reproducible and never mistaken for a figure the fund actually confirmed.

3. Codes are stored both raw and normalized. `reference_tokens` (raw memo
   fragments) is kept for investigation; `ne_code_normalized` / `acn_code` are
   indexed for search. This removes the `LIKE '%...%'` full scan that measured
   205 ms p50 on 1.0 M rows.

4. The outbound chain follows the real process published by the fund: a school
   sends a công văn / đề nghị thanh toán, it is approved, money leaves, evidence
   is attached, the period closes, and a versioned report is published.
"""

from __future__ import annotations

SCHEMA_VERSION = "2.0"

SCHEMA = """
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- reference

CREATE TABLE schools (
    id            INTEGER PRIMARY KEY,
    school_code   TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    commune       TEXT,
    province      TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE students (
    id            INTEGER PRIMARY KEY,
    student_code  TEXT NOT NULL UNIQUE,
    school_id     INTEGER NOT NULL REFERENCES schools(id),
    class_name    TEXT,
    gender        TEXT,
    status        TEXT,
    campus        TEXT,
    village       TEXT
);

CREATE TABLE donors (
    id            INTEGER PRIMARY KEY,
    acn_code      TEXT NOT NULL UNIQUE,
    display_hint  TEXT
);

-- A student's support record for one academic year under one NE code.
-- legacy_ne_code keeps the pre-2026 code string so history survives the
-- annual re-coding the fund performs.
CREATE TABLE student_supports (
    id              INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES students(id),
    donor_id        INTEGER REFERENCES donors(id),
    ne_code         TEXT,
    legacy_ne_code  TEXT,
    meal_plan       TEXT CHECK(meal_plan IN ('lunch', 'dinner', 'both', NULL)),
    months          INTEGER,
    total_amount    INTEGER,
    unit_price      INTEGER,
    meal_count      INTEGER,
    support_start   TEXT,
    support_end     TEXT,
    academic_year   TEXT NOT NULL,
    source_row      INTEGER NOT NULL,
    UNIQUE(student_id, academic_year)
);

-- ------------------------------------------------------------- transactions

CREATE TABLE bank_transactions (
    id                  INTEGER PRIMARY KEY,
    provider_tx_id      TEXT NOT NULL UNIQUE,
    idempotency_key     TEXT NOT NULL UNIQUE,
    source_stage        TEXT NOT NULL,
    source_account      TEXT,
    tx_time             TEXT,
    direction           TEXT NOT NULL CHECK(direction IN ('inbound', 'outbound')),
    amount              INTEGER NOT NULL CHECK(amount >= 0),
    balance_after       INTEGER,
    category            TEXT,
    subcategory         TEXT,
    processing_status   TEXT NOT NULL,
    reference_tokens    TEXT NOT NULL DEFAULT '',
    raw_description     TEXT NOT NULL DEFAULT '',
    academic_year       TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per (transaction, NE code). The heart of the model.
CREATE TABLE transaction_allocations (
    id                         INTEGER PRIMARY KEY,
    transaction_id             INTEGER NOT NULL REFERENCES bank_transactions(id),
    ne_code                    TEXT NOT NULL,
    ne_number                  INTEGER,
    meal_suffix                TEXT,
    donor_id                   INTEGER REFERENCES donors(id),
    student_id                 INTEGER REFERENCES students(id),
    school_id                  INTEGER REFERENCES schools(id),
    allocated_amount_computed  INTEGER NOT NULL DEFAULT 0,
    allocation_policy          TEXT NOT NULL DEFAULT 'equal_split',
    match_status               TEXT NOT NULL DEFAULT 'unmatched',
    source_row                 INTEGER NOT NULL,
    UNIQUE(transaction_id, ne_code, source_row)
);

-- ------------------------------------------------------- reconciliation

-- Schools' payment requests (công văn / đề nghị thanh toán).
CREATE TABLE school_payment_requests (
    id                  INTEGER PRIMARY KEY,
    request_code        TEXT NOT NULL UNIQUE,
    school_id           INTEGER NOT NULL REFERENCES schools(id),
    period_label        TEXT NOT NULL,
    requested_amount    INTEGER NOT NULL CHECK(requested_amount >= 0),
    approved_amount     INTEGER,
    document_reference  TEXT,
    status              TEXT NOT NULL DEFAULT 'submitted',
    submitted_at        TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at          TEXT
);

-- Links an outbound bank transaction to the request it settles.
CREATE TABLE disbursements (
    id                  INTEGER PRIMARY KEY,
    payment_request_id  INTEGER NOT NULL REFERENCES school_payment_requests(id),
    transaction_id      INTEGER NOT NULL REFERENCES bank_transactions(id),
    amount              INTEGER NOT NULL,
    disbursed_at        TEXT,
    UNIQUE(payment_request_id, transaction_id)
);

CREATE TABLE evidence_documents (
    id                  INTEGER PRIMARY KEY,
    payment_request_id  INTEGER NOT NULL REFERENCES school_payment_requests(id),
    document_type       TEXT NOT NULL,
    file_reference      TEXT,
    external_url        TEXT,
    checksum_sha256     TEXT,
    verified_by         TEXT,
    verified_at         TEXT,
    version             INTEGER NOT NULL DEFAULT 1
);

-- Maker-checker: a proposed change needs a different person to approve it.
CREATE TABLE approval_tasks (
    id                    INTEGER PRIMARY KEY,
    entity_type           TEXT NOT NULL,
    entity_key            TEXT NOT NULL,
    action                TEXT NOT NULL,
    proposed_payload      TEXT NOT NULL,
    reason                TEXT NOT NULL,
    maker                 TEXT NOT NULL,
    checker               TEXT,
    status                TEXT NOT NULL DEFAULT 'pending',
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at            TEXT,
    decision_note         TEXT
);

-- Tamper-evident audit trail. Application writes are append-only, and the
-- triggers below reject ordinary UPDATE/DELETE operations. A database owner
-- can still remove those triggers, so the hash chain remains detection rather
-- than a claim of absolute immutability.
CREATE TABLE audit_events (
    id            INTEGER PRIMARY KEY,
    event_type    TEXT NOT NULL,
    entity_type   TEXT,
    entity_key    TEXT,
    actor         TEXT NOT NULL,
    actor_role    TEXT,
    detail        TEXT,
    prev_hash     TEXT,
    event_hash    TEXT NOT NULL,
    occurred_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TRIGGER audit_events_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only');
END;

CREATE TRIGGER audit_events_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only');
END;

-- Exception queue: things a human must resolve, with a reason and an owner.
CREATE TABLE exception_queue (
    id            INTEGER PRIMARY KEY,
    exception_code TEXT NOT NULL,
    severity      TEXT NOT NULL CHECK(severity IN ('high', 'medium', 'low', 'info')),
    entity_type   TEXT NOT NULL,
    entity_key    TEXT,
    detail        TEXT NOT NULL,
    source_ref    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open',
    assigned_to   TEXT,
    resolved_at   TEXT,
    resolution    TEXT
);

CREATE TABLE data_quality_issues (
    id            INTEGER PRIMARY KEY,
    severity      TEXT NOT NULL CHECK(severity IN ('high', 'medium', 'low', 'info')),
    issue_code    TEXT NOT NULL,
    entity_type   TEXT NOT NULL,
    entity_key    TEXT,
    message       TEXT NOT NULL,
    source_ref    TEXT NOT NULL
);

-- Period close + versioned public report snapshot.
CREATE TABLE report_periods (
    id                 INTEGER PRIMARY KEY,
    period_label       TEXT NOT NULL UNIQUE,
    opened_at          TEXT,
    closed_at          TEXT,
    closed_by          TEXT,
    inbound_total      INTEGER NOT NULL DEFAULT 0,
    outbound_total     INTEGER NOT NULL DEFAULT 0,
    opening_balance    INTEGER,
    closing_balance    INTEGER,
    status             TEXT NOT NULL DEFAULT 'open',
    version            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE import_runs (
    id                    INTEGER PRIMARY KEY,
    source_name           TEXT NOT NULL,
    source_sha256         TEXT NOT NULL,
    source_kind           TEXT NOT NULL DEFAULT 'excel',
    imported_at           TEXT NOT NULL,
    student_rows          INTEGER NOT NULL DEFAULT 0,
    processed_rows        INTEGER NOT NULL DEFAULT 0,
    raw_transaction_rows  INTEGER NOT NULL DEFAULT 0,
    allocation_rows       INTEGER NOT NULL DEFAULT 0,
    schema_version        TEXT NOT NULL DEFAULT '2.0'
);

-- ------------------------------------------------------------- role / access

CREATE TABLE roles (
    id     INTEGER PRIMARY KEY,
    name   TEXT NOT NULL UNIQUE,
    scope  TEXT NOT NULL
);

-- ---------------------------------------------------------------- indexes

CREATE INDEX idx_students_school        ON students(school_id);
CREATE INDEX idx_supports_donor         ON student_supports(donor_id);
CREATE INDEX idx_supports_student       ON student_supports(student_id);
CREATE INDEX idx_supports_ne            ON student_supports(ne_code);

CREATE INDEX idx_transactions_time      ON bank_transactions(tx_time DESC);
CREATE INDEX idx_transactions_status    ON bank_transactions(processing_status);
CREATE INDEX idx_transactions_direction ON bank_transactions(direction);

-- Composite index: the app's hot path filters by direction then orders by time.
-- Measured on 1.0 M rows: 4,188 ms without this, ~1 ms with it.
CREATE INDEX idx_tx_direction_time      ON bank_transactions(direction, tx_time DESC);
CREATE INDEX idx_tx_status_time         ON bank_transactions(processing_status, tx_time DESC);

-- Exact + prefix search on codes. Kills the LIKE '%token%' table scan.
CREATE INDEX idx_alloc_ne_code          ON transaction_allocations(ne_code);
-- Covering index for the admin "codes without a student record" list. That
-- query groups 140k rows by code; without this it scans the table and reads
-- every row's columns (371 ms), with it the scan is index-only (60 ms).
CREATE INDEX idx_alloc_ne_amount        ON transaction_allocations(ne_code, allocated_amount_computed);
CREATE INDEX idx_alloc_ne_number        ON transaction_allocations(ne_number);
CREATE INDEX idx_alloc_tx               ON transaction_allocations(transaction_id);
CREATE INDEX idx_alloc_donor            ON transaction_allocations(donor_id);
CREATE INDEX idx_alloc_match_status     ON transaction_allocations(match_status);
CREATE INDEX idx_donors_acn             ON donors(acn_code);

CREATE INDEX idx_requests_school        ON school_payment_requests(school_id);
CREATE INDEX idx_requests_status        ON school_payment_requests(status);
CREATE INDEX idx_disb_request           ON disbursements(payment_request_id);
CREATE INDEX idx_evidence_request       ON evidence_documents(payment_request_id);
CREATE INDEX idx_approval_status        ON approval_tasks(status);
CREATE INDEX idx_audit_entity           ON audit_events(entity_type, entity_key);
CREATE INDEX idx_audit_time             ON audit_events(occurred_at DESC);
CREATE INDEX idx_exception_status       ON exception_queue(status, severity);
CREATE INDEX idx_issues_severity        ON data_quality_issues(severity);
"""


ROLE_SEED = [
    ("fund_admin", "full system administration"),
    ("finance_officer", "record and reconcile transactions"),
    ("finance_manager", "approve matching changes and disbursements"),
    ("school_liaison", "submit payment requests and evidence"),
    ("auditor", "read-only access to everything including audit log"),
    ("public", "aggregate statements only, no personal data"),
]
