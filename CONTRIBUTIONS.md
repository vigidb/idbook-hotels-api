# Contributing to IDBOOK Hotels API
**Last updated: March 2026**

---

## Project context (IDBOOK-specific)

IDBOOK Hotels API is a **Django REST Framework** backend that powers the IDBOOK hotel booking platform across **web, Android, and iOS**. It covers hotel listings, bookings, payments, customer management, partner (hotelier) operations, analytics, and background jobs.

- **Project root**: `IDBOOKAPI/`
- **Apps live in**: `IDBOOKAPI/apps/` (e.g. `authentication`, `hotels`, `booking`, `customer`, `payment_gateways`)
- **API base path**: `/api/v1/`
- **Docs (when enabled)**: ReDoc at `/api/v1/docs/`, Swagger at `/api/v1/docs/swagger/`
- **Architecture & commands**: see `CLAUDE.md` and `README.md`

---

## Local setup

```bash
python3 -m venv venv
source venv/bin/activate
cd IDBOOKAPI
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Run tests:

```bash
cd IDBOOKAPI
pytest
```

---

## Branching strategy

We follow a GitFlow-based model with three permanent branches:

| Branch | Purpose | Who pushes? |
|---|---|---|
| `main` | Production code only | No one directly — PR from `release/*` only |
| `test` | Integration branch for ongoing work | No one directly — PR from `feature/*` only |
| `feature/*` | Individual feature or fix work | Developer (you) |

**Temporary branch types:**

| Prefix | When to use | Example |
|---|---|---|
| `feature/` | New feature or enhancement | `feature/rbac-roles-api` |
| `fix/` | Bug fix | `fix/login-token-expiry` |
| `hotfix/` | Urgent production fix | `hotfix/payment-null-crash` |
| `release/` | Release preparation | `release/1.4.0` |
| `chore/` | Non-functional changes (deps, config) | `chore/update-django-4.2` |

> ⚠️ **Never commit directly to `main` or `test`. Branch protection rules will block it.**

---

## Commit message format

Follow [Conventional Commits](https://www.conventionalcommits.org/). Every commit must be descriptive and structured:

```
<type>(<scope>): <short summary>

[optional body]
[optional footer: ticket, breaking change note]
```

**Types:**

| Type | Use for |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code restructure without behavior change |
| `chore` | Dependency update, config change |
| `docs` | Documentation only |
| `test` | Adding or fixing tests |
| `perf` | Performance improvement |

**Examples:**

```bash
feat(auth): add email-based login with OTP verification
fix(rbac): resolve permission check in org-scoped context
chore(deps): upgrade django-rest-framework to 3.15
refactor(accounts): migrate Account to AbstractBaseUser
```

❌ Bad: `git commit -m "fix stuff"`  
✅ Good: `git commit -m "fix(scheduler): prevent duplicate CalendarEvent on retry"`

---

## Pull request (PR) rules

### Before Opening a PR

- Your branch is up to date with `test`
- Code runs locally without errors
- No debug prints, commented-out code, or TODOs without a ticket
- **If models changed**: migrations included + migration plan documented (see “Migrations”)
- `.env` secrets are never committed (no keys, tokens, creds, private URLs)

### PR Title Format

Same as commit format:

```
feat(rbac): add super admin role management APIs
fix(documents): fix S3 pre-signed URL expiry logic
```

### PR Description Template

```
## What does this PR do?
[1–2 sentences]

## How to test?
1. Step one
2. Step two

## Risk / rollout notes (optional)
- Any backwards compatibility concerns?
- Any data migration needed?

## Checklist
- [ ] Tests added/updated
- [ ] Migration files included (if applicable)
- [ ] No secrets or API keys in code
- [ ] Linked to ticket: #TICKET-ID
```

### Review Rules

- Minimum **1 approval** required before merge
- **Do not merge your own PR** — always get a peer review
- Reviewer must check: logic correctness, security, naming, and test coverage
- Address all review comments — don't dismiss without explanation
- **Squash merge preferred** to keep `test` history clean

---

## IDBOOK engineering conventions

### Django / DRF conventions

- **API versioning**: keep endpoints under `/api/v1/` and register routes in the relevant app `urls.py`.
- **Where to put logic**:
  - **Serializers**: validation and representation
  - **Viewsets/subviews**: orchestration + permissions + request/response
  - **Models**: invariants and core domain behavior (avoid request-dependent logic)
  - **Tasks**: anything async (emails/SMS, invoice generation, long-running integrations)
- **Permissions**: use existing custom permissions in `IDBOOKAPI/permissions.py` where applicable; do not copy/paste ad-hoc checks.

### Migrations (important)

When changing anything in `apps/*/models.py`:

```bash
cd IDBOOKAPI
python manage.py makemigrations <app_name>
python manage.py migrate
```

- **Keep migrations small and reviewable** (avoid mixing unrelated changes).
- If a migration is risky (large table, data migration), describe:
  - expected impact / downtime
  - backfill strategy (management command vs migration `RunPython`)
  - rollback plan

### Background jobs (Celery)

Run workers from `IDBOOKAPI/` after activating your venv. Common queues:

```bash
celery -A IDBOOKAPI worker -l info -Q dev-email-send-queue,dev-marketing-campaign-queue,airiq-token-queue,recpay-initiate-queue
```

(With `ENVIRONMENT=dev`; production all-queues worker: `email-send-queue,marketing-campaign-queue,airiq-token-queue,recpay-initiate-queue` — see root `README.md` § Celery.)

- Put new async work in the relevant app’s `tasks.py`.
- If you add a new task type that needs routing/scheduling, update `IDBOOKAPI/IDBOOKAPI/celery.py`.

### Security & privacy (IDBOOK is data-sensitive)

- Treat **phone numbers, emails, addresses, IDs, booking details, payment identifiers** as sensitive.
- **Never** log OTPs, access/refresh tokens, card data, or full payment payloads.
- Prefer masking in logs (e.g., last 4 digits) if you must log identifiers.
- Never commit `.env`, keys, certificates, or local credential files.

---

## Hard rules (non-negotiable)

```
❌ No direct push to main or test
❌ No force push (git push --force) to any shared branch
❌ No secrets, passwords, or API keys in code or commits
❌ No merging a PR with failing CI checks
❌ No deleting shared branches (main, test)
```

---

## Daily workflow

```bash
# 1. Start new work
git checkout test
git pull origin test
git checkout -b feature/your-feature-name

# 2. Work and commit regularly
git add .
git commit -m "feat(module): describe what you did"

# 3. Before raising PR — sync with test
git fetch origin
git rebase origin/test   # preferred over merge for cleaner history

# 4. Push and open PR
git push origin feature/your-feature-name
# → Open PR on GitHub targeting test
```

---

## Versioning

We use **Semantic Versioning**: `MAJOR.MINOR.PATCH`

| Part | Bump when |
|---|---|
| `MAJOR` | Breaking API or DB changes |
| `MINOR` | New feature, backward compatible |
| `PATCH` | Bug fix, no new features |

**Tag releases on `main`:**

```bash
git tag -a v1.4.0 -m "Release v1.4.0 - RBAC module"
git push origin v1.4.0
```

---

## Security practices

- Store secrets in environment variables or AWS Secrets Manager — **never in code**
- Add `.env` to `.gitignore` — commit only `.env.example` with placeholder values
- Never log sensitive data (passwords, tokens, PII) in application logs
- Run periodically to check for accidental secret commits:

```bash
git log --all --full-history -- "**/.env"
```
