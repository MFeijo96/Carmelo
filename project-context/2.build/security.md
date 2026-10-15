# Security Assessment

## Status

This is a scoped code-level assessment, not an independent security sign-off. Cloud Firestore/ADC and public hosting remain disabled. The unauthenticated local API is for synthetic demo data only.

## Controls Observed

- API and Vite entry points bind to loopback; CORS is restricted to the local frontend origins.
- `.env.example` contains variable names and an empty OpenAI key value; no service-account key is part of the documented setup.
- Emulator mode requires an explicit emulator host, rejects non-loopback hosts, and fails closed rather than using cloud access.
- Provider prompts exclude raw merchant/payee values, original descriptions, expense IDs, and internal category IDs. Merchants are represented by a stable fictitious alias with a business-context description, category hints, and a recurrence count. The reversible alias map is backend-only, never exported, and deleted with demo data. Classifier choices use per-request opaque tokens mapped back inside the backend.
- Insight outputs are schema, source, language, currency-grounding, and safety checked with deterministic fallback.
- Firestore client rules deny direct client reads and writes.

## Findings And Limitations

- No authentication or authorization exists. Local-only binding and synthetic data are mandatory constraints; do not host or use real household data.
- The Firestore Emulator gate passed (CSV import-to-dashboard, persistence, export, deletion, alias persistence/exclusion/deletion), and startup was confirmed to fail closed without `FIRESTORE_EMULATOR_HOST`.
- Accepted residual risk: `pip-audit` reports five advisories on `chromadb==1.5.9` (PYSEC-2026-311, -3813, -3814, -3815), a CrewAI dependency pinned `~=1.5.9`. No fixed version exists and 1.5.9 is the latest release. They affect the ChromaDB server (authentication, RBAC, code injection). The application never imports ChromaDB, both crews run with `memory=False`, and no ChromaDB server is started, so the vulnerable components are not reachable here. Re-audit when CrewAI or ChromaDB publishes a fix. `npm audit` reported zero frontend vulnerabilities.
- Gitleaks 8.30.1 (checksum-verified) scanned the whole working tree and found no leaks; `detect-secrets` agreed. `backend/uv.lock` provides a reproducible backend dependency graph.
- Full WCAG, operational logging/privacy, cloud IAM, backup/retention, and independent security reviews remain outstanding.

## Decision

Do not enable Cloud Firestore/ADC or deploy publicly until an independent security review approves the access-control and IAM plan and the ChromaDB advisories are re-audited.

## Sources

- `project-context/1.define/prd.md` Security & Compliance and P0.8/P0.9.
- `project-context/1.define/sad.md` AD-02/AD-06/AD-07 and deployment view.
- `backend/src/home_financial_backend/infrastructure/bootstrap.py`, `backend/src/home_financial_backend/runtime/adapters.py`, and `firestore.rules`.

## Assumptions

- Only synthetic records are used in local validation.
- Loopback binding is a deployment constraint, not user authentication.

## Open Questions

- Independent security review is still required; the ChromaDB advisories need re-audit when a fix is published.
- Cloud least-privilege IAM and the production auth boundary need a separate design before any hosted deployment.

## Audit

- 2026-10-12: scoped implementation-level assessment; no external provider or real financial data was used.
