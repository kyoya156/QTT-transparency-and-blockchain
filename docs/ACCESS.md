# Department access (Sprint 2, item N4)

## Roles
| Role | What it can do |
|---|---|
| `admin` | Sees everything. Uses the admin page to label data, tables and tools for other roles, and to edit permissions and users. |
| `dev` | Queries and changes the content of the database. Sees everything, but has no access to the admin page. |
| `finance` | Read-only, finance information: transactions, sponsor details for verifying a transfer, allocations, disbursements. |
| `volunteer` | Read-only, mostly low-level information that needs approval: sponsorship assignments, basic student information. |

Only `finance` and `volunteer` are labelled. `admin` and `dev` need no label.

## Rules
- The **admin** labels data and tools in the admin page (`/admin`). A department can only use what is labelled for it.
- **Unlabelled = admin and dev only.** New chunks from a sync inherit the label of their source, otherwise they start unlabelled.
- Admin can use everything, so `admin` is never written into a label.
- A source label beats a type label (`web` as a whole), which beats no label.

## Core database tables
The table list comes from the ERD (WIP) tab of `gradproj.drawio`; table names are my reading and must be checked against Topic 4's final schema (edit `CORE_TABLES` in `app/access.py`).
The admin page has a "Core DB tables" tab with proposed defaults (apply once, never overwrites a choice):

| Table group | Proposed access |
|---|---|
| province, commune, village, school, school_site, school_year, class, meal_plan, school_meal_plan | finance, volunteer |
| student, enrollment | volunteer |
| sponsorship_assignment, ne_code | finance, volunteer |
| sponsor (name, phone, email), bank_transaction, transaction_allocation, disbursement | finance |
| measurement, family_info, student_image, image_result, publication, school_case | unlabelled: admin and dev only |
| app_user, role, user_role, import_batch, import_issue, audit_log | system: admin and dev only, cannot be labelled |

`GET /api/admin/core-grants.sql` turns the labels into GRANT statements for the Core DB: `core_finance` and `core_volunteer` get SELECT only on labelled tables; `core_dev` gets INSERT/UPDATE (and DELETE, except on financial tables); `audit_log` is insert-only for everyone; `core_admin` reads all.

## How it is enforced
| Layer | What |
|---|---|
| Identity | Bearer token per user (hash stored). Department comes from the user record, never from the request. |
| Data | Postgres row-level security on `chunks`: role `chatbot_app` sees a row only if `labels` contains the user's department, or the user is admin. Vector and keyword search both go through it. |
| Tools | `access_rules` key `tool:<name>`; checked before the tool runs. Denied calls are logged. |
| Audit | `audit_log` (insert-only for `chatbot_app`): searches with the chunk ids returned, denied tool calls, label and user changes. |

`SET LOCAL` scopes the identity to one transaction, so it cannot leak between pooled connections.
`chatbot_app` cannot read `users` or `access_rules`, and cannot update or delete anything.

## Use
```
python -m scripts.create_user --email you@example.org --name "Name" --department admin   # prints a token once
```
Open `/admin`, paste the token, label sources and tools. Users call `POST /api/search` with their own token.

## Open questions
- Who reviews and approves student photos (`student_image`, `image_result`, `publication`)? Unlabelled for now.
- Should volunteers see `family_info` and `measurement`? Unlabelled for now (most sensitive).
- Dev can read donor and family personal data. Consider masked or staging data for dev work.
- The WIP ERD has three duplicate `user` blocks next to the `users`/`roles` tables; the roles table should hold exactly these four roles.

## Not done yet
- Messenger and Core database sources reuse the same label mechanism; they are not connected yet.
- Login is a token per user; single sign-on is a later decision.
- Labels apply per source or per type, not per individual chunk.
- Negative tests per role against real Postgres are manual so far (checked once; add to CI with Docker).
