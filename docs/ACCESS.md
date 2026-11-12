# Department access (Sprint 2, item N4)

Departments: `admin`, `finance`, `volunteers`.

## Rules
- The **admin** labels data and tools in the admin page (`/admin`). A department can only use what is labelled for it.
- **Unlabelled = admin only.** New chunks from a sync inherit the label of their source, otherwise they start unlabelled.
- Admin can use everything, so `admin` is never written into a label.
- A source label beats a type label (`web` as a whole), which beats no label.

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

## Not done yet
- Messenger and Core database sources reuse the same label mechanism; they are not connected yet.
- Login is a token per user; single sign-on is a later decision.
- Labels apply per source or per type, not per individual chunk.
- Negative tests per role against real Postgres are manual so far (checked once; add to CI with Docker).
