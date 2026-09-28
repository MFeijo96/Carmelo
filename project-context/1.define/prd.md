# Product Requirements Document (PRD): Home Financial

## Context & Instructions

Home Financial is a capstone MVP for Brazilian household personal finance awareness. It helps households register expenses, classify spending, review monthly totals, and receive educational insights in Portuguese (pt-BR). The product is intentionally scoped as an awareness and learning tool, not a regulated financial adviser.

This PRD is based on `project-context/1.define/mrd.md` and is intended to guide the AAMAD Build phase. It defines product scope, user needs, MVP requirements, success metrics, acceptance criteria, and implementation boundaries. Architecture details should be refined in the SAD, but product requirements here should remain stable unless stakeholder assumptions change.

**Deep Research Report / MRD**: `project-context/1.define/mrd.md`  
**System Description**: N/A; MRD and stakeholder decisions provide the primary product context.  
**System Concept**: A web-first, household-aware expense intelligence system that uses deterministic calculations, editable categorization, correction history, and LLM-generated educational narratives to explain monthly spending in Portuguese.  
**Selected Runtime**: `crewai`, from `aamad.config.yml`. Runtime choice constrains Build-phase implementation conventions, but it is not a product requirement.

## 1. Executive Summary

### Problem Statement

Brazilian households face recurring pressure from essential expenses such as housing, food, transportation, utilities, health, education, communication, debt payments, and subscriptions. Many people can access digital payment data through banks, cards, Pix records, statements, or spreadsheets, but they still struggle to answer basic monthly questions:

- Quanto a casa gastou?
- Para onde foi o dinheiro?
- O que mudou neste mes?
- Quais categorias precisam de revisao?

Existing alternatives include spreadsheets, individual banking apps, digital wallets, and personal budget apps. These tools often focus on individual account views, require heavy manual maintenance, or do not support a shared household perspective. The MVP opportunity is to provide low-friction expense understanding for households without requiring bank credentials or Open Finance integrations.

The most important product risk is incorrect expense classification. If categories are wrong, monthly summaries and LLM-generated insights lose trust. Therefore, categorization accuracy is the primary product metric, with a demo MVP acceptance threshold of at least 70% accuracy on a curated golden dataset.

### Solution Overview

Home Financial will provide a Portuguese-language web MVP where a household can:

- Import expenses from CSV and add expenses manually.
- View household expenses by month, category, payment method, and recurrence.
- Use a Brazilian household expense taxonomy seeded from IBGE POF-inspired categories and common app-level categories.
- Review and correct category assignments.
- Improve future categorization using deterministic rules, global category frequencies, and household-specific correction history.
- Generate grounded monthly educational insights through the OpenAI API, using deterministic totals and structured summaries rather than raw unrestricted personal data.
- Export or delete demo/local household data.

The differentiator is explainable monthly household intelligence: the product should not merely classify expenses, but explain why spending changed, identify source transactions behind insights, and allow users to reshape categories when the system is wrong.

### Strategic Rationale

A multi-agent design is appropriate because the product contains distinct responsibilities that benefit from explicit boundaries:

- Ingestion and validation require deterministic parsing and error reporting.
- Categorization requires repeatable rules, correction memory, and confidence scoring.
- Aggregation requires exact arithmetic and traceability.
- Insight generation requires constrained Portuguese narrative output based on validated summaries.
- Evaluation requires repeatable categorization scoring against a golden dataset.

For a capstone MVP, this separation supports clearer implementation, simpler testing, and safer LLM use. The selected `crewai` runtime can coordinate specialized agents for classification, analysis, and explanation, while deterministic application services retain authority over data validation and numeric calculations.

## 2. Market Context & User Analysis

### Target Market / Users

**Primary geography**: Brazil.  
**Product language**: Portuguese (pt-BR).  
**Primary segment**: households that need simple monthly clarity over shared home expenses.  
**Secondary segment**: students, young professionals, couples, families, and shared homes building financial awareness habits.

#### Persona 1: Household Organizer

- Coordinates bills, groceries, rent, subscriptions, and recurring payments for the home.
- May already use spreadsheets or banking exports.
- Needs fast monthly answers and category correction tools.
- Measures success by reduced manual work and clearer household conversations.

#### Persona 2: Shared Home Member

- Represents a person who may eventually use a shared household account with family, a partner, friends, or roommates.
- Needs visibility into shared categories and the ability to register household expenses.
- Needs an interface that is simple, nonjudgmental, and mobile-friendly.
- Measures success by knowing where money went without needing to maintain a full spreadsheet.
- **MVP limitation**: the local/demo experience uses one shared workspace without individual identity, permissions, invitations, or per-person action history; this persona describes the intended future authenticated experience.

#### Persona 3: Capstone Evaluator / Demo Operator

- Runs the MVP locally or in a controlled demo environment.
- Imports a sample dataset and verifies the application against acceptance criteria.
- Needs repeatable accuracy measurement, visible system behavior, and documented limitations.
- Measures success by artifact completeness, working flows, and testability.

### User Needs Analysis

Users need the product to support the following jobs:

- Understand monthly household spending in BRL.
- Import existing expense data without connecting bank accounts.
- Add missing expenses paid in cash, debit, or credit, and mark recurrence separately when applicable.
- Correct categories when classification is wrong.
- Understand why the system assigned a category.
- See which expenses contributed to each monthly insight.
- Avoid shame-based or prescriptive financial advice.
- Keep sensitive household financial data private and deletable.

### User Journey

1. User opens the web MVP in local/demo mode.
2. User opens the single shared demo household workspace.
3. User imports a CSV file or adds expenses manually.
4. System validates expense fields and reports import errors clearly.
5. System normalizes values into BRL, dates, payment methods, and merchant/description fields.
6. System classifies expenses into editable categories with confidence scores.
7. User reviews low-confidence or important category assignments.
8. User corrects categories and optionally restructures the category taxonomy.
9. Dashboard shows monthly totals, category breakdown, payment method mix, recurring expenses, and month-over-month changes.
10. System generates Portuguese educational insights grounded in deterministic summaries and source expenses.
11. User exports or deletes local/demo data when desired.

### Adoption Barriers and Success Factors

**Barriers**:

- Concern about sharing household financial data.
- Distrust caused by incorrect categorization.
- Friction importing CSV files from varied sources.
- Confusion if AI-generated insights sound like financial advice.
- Lack of visible value after first import.

**Success factors**:

- Clear CSV template and validation feedback.
- Fast time-to-first-dashboard after import.
- Editable categories and visible learning from corrections.
- Grounded insights with links back to source expenses.
- Neutral, plain Portuguese copy.
- Data deletion/export controls available from the start.

### Competitive Landscape

Direct and indirect alternatives include spreadsheets, banking dashboards, card apps, digital wallets, budgeting apps, and manual notebooks. Home Financial should differentiate by combining household collaboration, editable Brazilian categories, transparent classification, and grounded LLM-assisted monthly explanations without requiring bank integration in the MVP.

### MRD-to-PRD Traceability

| MRD driver | PRD coverage | MVP disposition |
| --- | --- | --- |
| MRD-01: Shared household clarity | P0.1 workspace, P0.3 manual entry, P0.7 dashboard | One shared local/demo workspace; authenticated members, invitations, roles, and personal action history are deferred to P2. |
| MRD-02: Low-friction input without bank access | P0.2 CSV import, P0.3 manual entry; P2 Future Features | CSV/manual input is in MVP; bank and Open Finance integration are out of scope. |
| MRD-03: Classification trust and measurable quality | P0.4 classification, P0.5 correction, P0.6 taxonomy, P0.10 evaluation | Editable and explainable classification with a repeatable golden-dataset gate. |
| MRD-04: Brazilian household taxonomy | P0.4 taxonomy, P0.6 category editing | Hierarchical taxonomy; each expense maps to exactly one active leaf category. |
| MRD-05: Grounded, nonjudgmental insights | P0.8 insights; sections 5 and 6 safety/tone requirements | pt-BR insights cite supporting data and avoid advice. |
| MRD-06: Sensitive-data control | P0.8.6-P0.8.7 LLM data minimization, P0.9 export/deletion, section 5 Security & Compliance | Privacy controls are MVP requirements; production controls gate real shared household use. |
| MRD-07: Recurrence analysis | P0.2/P0.3 recurrence input, P0.7 dashboard; P1 recurring detection | Recurrence is modeled separately from payment method; advanced detection is P1. |
| MRD-08: Responsive web access | Sections 5 and 6 accessibility/localization and interface requirements; P2 Future Features | Responsive web is MVP; PWA and native apps are deferred. |
| MRD-09: Unproven willingness to pay | Section 9 launch/validation plan | Validate user usefulness; pricing and commercial launch are future work. |

## 3. Technical Requirements & Architecture

### Runtime & Agent Specifications

The Build phase should use `crewai` only where orchestration improves clarity. Core product logic must remain testable outside LLM calls.

Recommended agent collaboration pattern:

- Sequential pipeline for ingestion, normalization, categorization, aggregation, and insight generation.
- Human-in-the-loop category review before final monthly insights when confidence is low or user corrections exist.
- Deterministic services own validation, totals, percentages, date ranges, and accuracy measurement.
- LLM agents produce narrative explanations only from structured, precomputed summaries and allowed context.

### Core Agent Definitions

#### agent: ingestion_agent

- **role**: Expense ingestion and validation specialist.
- **goal**: Convert CSV/manual inputs into normalized expense records or actionable validation errors.
- **tools**: CSV parser, schema validator, date parser, BRL amount normalizer, import error reporter.
- **runtime notes**: Deterministic behavior preferred; no LLM required for MVP ingestion.

#### agent: categorization_agent

- **role**: Expense classification specialist.
- **goal**: Assign categories using rules, merchant keywords, global frequencies, household history, and optional AI fallback for ambiguous items.
- **tools**: Category taxonomy, merchant keyword map, household correction history, confidence scorer, optional OpenAI classification helper.
- **runtime notes**: Must emit category, confidence, reason, and whether user review is recommended. Classification must be measurable against the golden dataset.

#### agent: aggregation_agent

- **role**: Monthly spending analyst.
- **goal**: Produce deterministic totals, category breakdowns, month-over-month comparisons, recurring-expense summaries, and source transaction groups.
- **tools**: Expense repository, aggregation functions, recurrence detector, date range utilities.
- **runtime notes**: All arithmetic must be deterministic and covered by tests.

#### agent: insight_agent

- **role**: Portuguese educational insight writer.
- **goal**: Convert structured monthly summaries into plain-language, nonjudgmental insights in pt-BR.
- **tools**: OpenAI API provider abstraction, prompt templates, safety constraints, source-expense references.
- **runtime notes**: Must avoid investment, tax, credit, affordability, or prescriptive financial advice. Must ground each insight in provided categories, transactions, or date ranges.

#### agent: evaluation_agent

- **role**: Categorization accuracy evaluator.
- **goal**: Compare predicted categories against expected categories in the golden dataset and produce repeatable accuracy reports.
- **tools**: Golden dataset loader, classifier runner, confusion report generator, acceptance threshold checker.
- **runtime notes**: Must run on demand and report pass/fail against the 70% MVP threshold.

### Integration Requirements

- **Frontend**: Responsive web interface for local/demo use.
- **Backend**: Modular API with services for expenses, categories, imports, aggregation, insights, and evaluation.
- **LLM provider**: OpenAI API through a provider abstraction. Use a cost-efficient GPT-4o mini-class model or current equivalent at implementation time.
- **Storage**: Firebase Firestore on the free tier for the capstone MVP, with repository interfaces so the storage layer can be replaced later if needed. Must preserve domain entities for future user accounts and household membership.
- **Authentication**: Deferred for MVP runtime, but data model and route boundaries must be ready for future login/password auth.
- **Email**: Deferred; future password recovery requires email sending.
- **Bank integration**: Explicitly out of scope.

### Data Model Requirements

The MVP domain model must support, at minimum:

- `User`: future account identity and profile fields.
- `AuthCredential`: future password-auth record and password recovery support.
- `Household`: shared household workspace.
- `HouseholdMembership`: user-to-household relation with future role.
- `Role`: future `admin`, `member`, and `viewer` values.
- `Category`: editable category taxonomy with household-specific customization.
- `Expense`: date, description, amount in BRL, merchant/payee, category, payment method, source, recurrence flag, confidence score, and user override flag.
- `ImportRun`: source file metadata, row count, validation errors, and import status.
- `ClassificationDecision`: predicted category, confidence, reason, rule/source used, and user correction link.
- `InsightRun`: month, input summary hash/version, generated insights, provider metadata, and safety status.
- `EvaluationRun`: golden dataset version, accuracy score, confusion details, and pass/fail threshold.
- `MerchantContext`: internal merchant/payee safety record with original merchant text, generated fictitious alias, business-context description, category hints, and household scope.
- `LLMDataMap`: reversible mapping between original merchant/payee data and aliases used in LLM prompts, available only to backend services that need to restore source references for the user.

### Infrastructure Specifications

- MVP may run locally or in a simple demo deployment.
- Secrets must be provided through environment variables and never committed.
- Logs must avoid plaintext sensitive expense descriptions where practical.
- Development environment should support repeatable setup, tests, and validation through documented commands.
- Monitoring for hosted deployment should capture import success, classification confidence distribution, user corrections, insight generation errors, latency, and deletion/export events.

## 4. Functional Requirements

### Core Features (P0)

#### P0.1 Local/Demo Household Workspace

**User story**: As a demo user, I want to use the shared demo household without production account setup so that I can evaluate household expense tracking quickly.

**Acceptance criteria**:

- AC-P0.1.1: The app provides exactly one shared local/demo household workspace.
- AC-P0.1.2: All expenses are associated with a household identifier.
- AC-P0.1.3: The domain model supports future users, memberships, and roles, but the MVP does not create individual identities or enforce member roles.
- AC-P0.1.4: The UI communicates access state without implying production-grade authentication.
- AC-P0.1.5: The MVP provides one shared local/demo household workspace. Anyone using that local/demo instance sees the same household data; there are no invitations, per-person permissions, or personal action attribution. The demo workspace must not be presented as suitable for real financial data.

#### P0.2 CSV Expense Import

**User story**: As a household organizer, I want to import expenses from CSV so that I can generate monthly views without typing every expense manually.

**Acceptance criteria**:

- AC-P0.2.1: The system accepts a documented Portuguese CSV format with required columns `data`, `descricao`, `valor`, and `forma_pagamento`, plus optional columns `estabelecimento`, `categoria`, `recorrente`, and `observacoes`.
- AC-P0.2.2: CSV dates must use `dd/mm/yyyy` format.
- AC-P0.2.3: The system supports BRL amounts and rejects unsupported currencies.
- AC-P0.2.4: The `forma_pagamento` field accepts only `dinheiro`, `debito`, or `credito` (case-insensitive after trimming whitespace).
- AC-P0.2.5: Invalid rows produce clear validation messages without blocking valid rows unless the file is structurally invalid.
- AC-P0.2.6: Import results show total rows, imported rows, rejected rows, and error details.
- AC-P0.2.7: Recurrence is independent of payment method. The optional `recorrente` field accepts `sim` or `nao` (case-insensitive after trimming whitespace); omitted values default to `nao`.
- AC-P0.2.8: When `categoria` is present and non-empty, it must match exactly one active leaf-category label after trimming whitespace and comparing case- and accent-insensitively. A parent category, unknown label, or ambiguous match rejects only that row with a validation error naming the field and supplied value; it must not create a category, silently map to `outros`, or invoke the classifier. Blank or omitted `categoria` invokes normal classification. The user can correct the value or create the category in category settings before re-importing; other valid rows still import.

#### P0.3 Manual Expense Entry

**User story**: As a demo user, I want to add an expense manually so that cash or missing household expenses are included in the shared monthly view.

**Acceptance criteria**:

- AC-P0.3.1: User can create an expense with date, description, amount, payment method, and category or category suggestion.
- AC-P0.3.2: Amount is stored and displayed in BRL.
- AC-P0.3.3: Required fields are validated before save.
- AC-P0.3.4: New manual expenses appear in the dashboard and expense review list.
- AC-P0.3.5: Manual entry accepts cash, debit, or credit as payment method and a separate optional recurring flag, defaulting to non-recurring.

#### P0.4 Expense Categorization

**User story**: As a household user, I want expenses classified into understandable categories so that I can see where household money went.

**Acceptance criteria**:

- AC-P0.4.1: The initial taxonomy is hierarchical. Top-level categories include moradia, alimentacao, transporte, saude, educacao, contas da casa, lazer, dividas, pets, impostos/taxas, cuidados pessoais, and outros. At minimum, `alimentacao` has leaf categories `mercado` and `restaurantes`; `assinaturas` is a leaf under `lazer`. Each expense is assigned to exactly one active leaf category; parent categories are roll-up groups and cannot be assigned directly to expenses.
- AC-P0.4.2: For rows accepted by validation, classification follows this precedence: (1) a valid category explicitly supplied by the user (CSV category matching follows AC-P0.2.8); (2) an exact household correction matching normalized merchant and description; (3) the most-specific unambiguous deterministic keyword/rule match; (4) household correction frequency, with global category frequency used only as a tie-breaker; (5) optional LLM fallback for unresolved ambiguous cases. If no decisive result is available and LLM fallback is unavailable, assign `outros` and flag the expense for review.
- AC-P0.4.3: Household-specific correction evidence takes precedence over global category frequencies; neither frequency source may override an explicit user category, an exact household correction, or an unambiguous deterministic rule.
- AC-P0.4.4: Each classifier-produced decision stores one active leaf category, a confidence score from 0.0 to 1.0, a reason, and the decision source. User-supplied categories are recorded as user overrides.
- AC-P0.4.5: Classifier-produced decisions with confidence below 0.70 are marked review-needed and shown in the review list. The score is a decision-confidence heuristic, not a calibrated probability.
- AC-P0.4.6: MVP acceptance requires top-1 accuracy of at least 70%, calculated as exact predicted canonical leaf-category matches divided by total golden-dataset records. Report the numerator and denominator; run the acceptance evaluation with LLM fallback disabled or mocked.

#### P0.5 Category Review and Correction

**User story**: As a household user, I want to correct expense categories so that the system becomes more trustworthy over time.

**Acceptance criteria**:

- AC-P0.5.1: User can change an expense category from the review list or expense detail view.
- AC-P0.5.2: User corrections are stored with a user override flag.
- AC-P0.5.3: Future classifications can use household-specific correction history.
- AC-P0.5.4: The UI distinguishes system-predicted categories from user-corrected categories.
- AC-P0.5.5: Category changes update monthly totals and insights inputs.

#### P0.6 Editable Category Taxonomy

**User story**: As a household organizer, I want to adjust categories so that the system reflects how my household thinks about spending.

**Acceptance criteria**:

- AC-P0.6.1: User can view the category list.
- AC-P0.6.2: User can create a household-specific leaf category under an existing top-level category; arbitrary nesting and user-created parent categories are out of scope.
- AC-P0.6.3: User can rename household-specific leaf categories; standard top-level categories and standard leaf categories retain their canonical identities for evaluation.
- AC-P0.6.4: User can merge household-specific leaf categories into an existing active leaf category. Parent categories cannot be merged or assigned to expenses.
- AC-P0.6.5: User can reassign expenses from one category to another.
- AC-P0.6.6: Existing expenses remain linked to valid categories after category changes.
- AC-P0.6.7: Category changes do not remove the ability to run golden-dataset evaluation against the standard taxonomy.

#### P0.7 Monthly Dashboard

**User story**: As a household user, I want a monthly dashboard so that I can quickly understand household spending.

**Acceptance criteria**:

- AC-P0.7.1: Dashboard shows total spending for the selected month.
- AC-P0.7.2: Dashboard shows category breakdown by amount and percentage.
- AC-P0.7.3: Dashboard shows payment method breakdown for cash, debit, and credit where present.
- AC-P0.7.4: Dashboard shows month-over-month comparison when prior-month data exists.
- AC-P0.7.5: Dashboard calculations are deterministic and do not depend on LLM output.
- AC-P0.7.6: Dashboard shows recurring expense totals separately using the recurrence flag; recurrence is not displayed as a payment method.

#### P0.8 Portuguese Monthly Insights

**User story**: As a household user, I want plain-language insights in Portuguese so that I can understand what changed in the month.

**Acceptance criteria**:

- AC-P0.8.1: Insights are generated in pt-BR.
- AC-P0.8.2: Insights use deterministic monthly summaries and source-expense groups as input.
- AC-P0.8.3: Every insight references the category, date range, or expenses that support it.
- AC-P0.8.4: Insights avoid regulated financial advice, investment advice, tax advice, credit decisions, or affordability claims.
- AC-P0.8.5: If the LLM provider fails or is not configured, the app shows deterministic fallback summaries rather than blocking the dashboard.
- AC-P0.8.6: Merchant/payee data sent to the LLM must use fictitious aliases and business-context descriptions from the internal merchant context layer unless the user explicitly chooses a less restrictive demo mode.
- AC-P0.8.7: Source references shown back to the user must be restored from the internal alias map, not guessed by the LLM.

#### P0.9 Data Export and Deletion

**User story**: As a household user, I want to export or delete my data so that I can control sensitive household financial information.

**Acceptance criteria**:

- AC-P0.9.1: User can export household expense data as CSV using the same documented field schema accepted by import.
- AC-P0.9.2: User can export a complete household data archive as JSON, including expenses, categories, import runs, classification decisions, insights, and evaluation runs tied to the household.
- AC-P0.9.3: CSV and JSON exports include generated timestamp, household identifier, selected date range, and schema version.
- AC-P0.9.4: CSV exports are suitable for spreadsheet review; JSON exports are suitable for backup, portability, QA inspection, and future migration.
- AC-P0.9.5: Exports must not include API keys, provider secrets, internal prompt text, or unrelated household data.
- AC-P0.9.6: User can delete demo/local household data.
- AC-P0.9.7: Deletion removes expenses, imports, classifications, insights, and evaluation artifacts tied to the household unless retained only as anonymous aggregate logs.
- AC-P0.9.8: The UI confirms destructive deletion before execution.
- AC-P0.9.9: PDF export is not required for MVP data portability; a PDF monthly report is a P1 enhancement.

#### P0.10 Repeatable Accuracy Evaluation

**User story**: As a capstone evaluator, I want a repeatable categorization accuracy report so that MVP acceptance can be verified on demand.

**Acceptance criteria**:

- AC-P0.10.1: A golden dataset of 30-50 anonymized Brazilian household expenses is available for QA and demo use, with expected categories expressed as canonical leaf categories.
- AC-P0.10.2: Each golden dataset record includes expected category, date, description, amount, payment method (`dinheiro`, `debito`, or `credito`), and an independent recurrence flag.
- AC-P0.10.3: The evaluation command or UI action runs the classifier against the dataset.
- AC-P0.10.4: The report shows total records, correct predictions, incorrect predictions, accuracy percentage, and category-level confusion details.
- AC-P0.10.5: The report clearly passes when exact top-1 leaf-category accuracy is at least 70% and fails otherwise; it reports the correct-count numerator and total-record denominator.

### Enhanced Features (P1)

P1 features may be included if P0 scope is stable, but should not block MVP acceptance unless explicitly promoted.

- Non-functional household invitation placeholder only; it does not send invitations or grant access to external users.
- More advanced recurring-expense detection.
- Anomaly detection for unusual category changes.
- Insight feedback controls such as useful/not useful.
- Sample CSV template download using the Portuguese schema: `data`, `descricao`, `valor`, `forma_pagamento`, `estabelecimento`, `categoria`, `recorrente`, and `observacoes`.
- PDF monthly report export with totals, category breakdown, selected insights, and date range.
- Import mapping UI for alternate CSV column names.
- Configurable insight tone within non-advice safety limits.

### Future Features (P2)

The following features are explicitly future work and out of MVP scope:

- Direct bank integration.
- Open Finance account aggregation.
- Production login/password registration.
- Email-based password recovery.
- Email verification.
- Household invitations with real external users.
- Production authorization enforcement for admin/member/viewer roles.
- Per-member expense attribution and household action history.
- Audit logging for authenticated shared household access.
- Native Android or iOS apps.
- PWA or hybrid mobile packaging.
- Receipt scanning.
- Pix/payment statement import beyond generic CSV.
- Investment advice.
- Tax advice.
- Credit recommendations or affordability decisions.
- Automated real-time financial coaching.
- Monetization, billing, or subscriptions.

## 5. Non-Functional Requirements

### Performance Requirements

- Import 50 demo expenses in under 5 seconds on a typical local development machine.
- Render the monthly dashboard in under 2 seconds after data is available.
- Classify the 30-50 row golden dataset in under 30 seconds when LLM fallback is disabled or mocked.
- Generate monthly insights in under 20 seconds when the OpenAI API is configured and available.
- Provide a deterministic fallback summary when insight generation exceeds timeout or fails.

### Security & Compliance

- Treat household financial records as sensitive personal data.
- Do not commit API keys, credentials, real financial records, or secrets.
- Use environment variables for OpenAI API configuration.
- Minimize personal identifiers sent to LLM providers; use aggregated summaries and anonymized merchant/payee aliases by default.
- Maintain an internal merchant context layer that maps real merchant/payee values to fictitious aliases, stores a short business-context description for categorization, and can restore original labels only inside trusted backend responses to the user.
- Do not send raw merchant/payee names to the LLM by default. If a demo mode allows raw names, it must be explicit, documented, and disabled by default.
- Avoid logging sensitive expense details in plaintext.
- Provide data deletion and export controls.
- Align future production design with LGPD principles: purpose limitation, data minimization, transparency, access/export, deletion, and security safeguards.
- Add authentication, authorization, audit logging, encryption at rest, backup/restore, and retention policy before production shared household use.

### Safety Requirements

- The product must position insights as educational awareness, not financial advice.
- Insight generation prompts must prohibit regulated financial advice, investment recommendations, tax advice, credit decisions, and affordability claims.
- Numeric calculations must not be delegated to the LLM.
- LLM output must be grounded in structured summaries and source-expense references.
- LLM prompts should receive alias-safe merchant context such as merchant type, recurring behavior, and category hints instead of raw merchant names.
- The UI should use neutral, nonjudgmental language.

### Reliability Requirements

- CSV import should preserve valid rows when other rows fail validation.
- Dashboard calculations should remain available without LLM configuration.
- Classification evaluation should be reproducible with the same dataset and configuration.
- Data deletion should be confirmed and idempotent.

### Scalability Requirements

- MVP should support one local/demo household and at least 12 months of sample expenses comfortably.
- The domain model must not prevent future multi-user, multi-household operation.
- Production scaling, background jobs, and hosted observability are deferred to SAD and later implementation phases.

### Accessibility and Localization Requirements

- User-facing product copy must be in pt-BR.
- Currency must be displayed as BRL.
- Dates should follow Brazilian user expectations.
- UI should meet WCAG 2.1 AA intent for contrast, keyboard navigation, labels, and focus states where feasible for MVP.
- Responsive layout must support desktop and mobile web viewports.

## 6. User Experience Design

### Interface Requirements

The MVP should include the following screens or equivalent views:

- Local/demo access state with no login/password controls.
- Current shared demo-household indicator; household selection is out of scope for MVP.
- Monthly overview dashboard.
- Category breakdown view.
- Expense review list with confidence indicators.
- Manual expense entry form.
- CSV import flow with validation report.
- Monthly insights view.
- Category settings view.
- Data export/delete settings.
- Accuracy evaluation report for demo/QA.

### Interaction Patterns

- Dashboard-first navigation after data exists.
- Clear empty states before import or manual entry.
- Inline validation for manual expense forms.
- Import summary after CSV upload.
- Filterable expense review by month, category, confidence, payment method, and source.
- One-step category correction from review lists.
- Drill-down from insights to supporting expenses.
- Confirmation before data deletion.

### Agent Interaction Design

Users should not need to understand the internal agent architecture. The interface should expose system behavior through product-level explanations:

- Show confidence or review-needed indicators for classification.
- Show brief category reasons, such as merchant keyword match or previous household correction.
- Show the source categories or transactions behind insights.
- Show when LLM insight generation is unavailable and deterministic fallback summaries are being used.
- Provide correction flows that visibly improve future classification.

### Tone and Content Guidelines

- Use clear, conversational pt-BR.
- Avoid blame, shame, or moralizing language.
- Prefer observations such as "Os gastos com mercado aumentaram em relacao ao mes anterior" over prescriptions such as "Voce deve cortar mercado".
- Avoid claims about what the household can afford.
- Avoid financial, tax, credit, or investment recommendations.

## 7. Success Metrics & KPIs

### Primary Product Metric

- **Categorization accuracy**: At least 70% accuracy on the curated golden dataset for MVP acceptance.

### Product Metrics

- Time-to-first-dashboard after CSV import: under 2 minutes for demo user.
- Import completion rate on sample CSV: at least 95% valid rows imported.
- Manual correction completion: user can correct a category in under 30 seconds during usability testing.
- Insight grounding: 100% of generated insights include supporting category, date range, or source-expense reference.
- Data control: export and deletion controls are discoverable from settings.

### Technical Metrics

- Dashboard arithmetic correctness: 100% pass on deterministic unit tests.
- Golden dataset evaluation reproducibility: same input and configuration produce same accuracy report when LLM fallback is disabled or mocked.
- LLM safety: 0 accepted insights containing investment, tax, credit, or affordability advice in QA safety checks.
- Secret hygiene: 0 committed secrets detected before delivery.
- Integration smoke test: CSV import to dashboard to insight/fallback flow passes before release.

### User Experience Metrics

- 3-5 Brazilian target users can describe the main dashboard result after first import.
- Users rate insights as understandable and useful in concept validation.
- Users can identify how to fix an incorrect category without instruction.
- Users perceive language as neutral and nonjudgmental.

## 8. Implementation Strategy

### Development Phases

#### Phase 1: Define

- Complete MRD.
- Complete this PRD.
- Create SAD with architecture, security, data, LLM, and evaluation criteria.
- Create MVP user stories mapped to acceptance criteria.

#### Phase 2: Build

- Scaffold project using selected runtime conventions.
- Implement Firebase Firestore storage, data model, and sample/golden datasets.
- Implement CSV import and manual entry.
- Implement category taxonomy, classifier, correction history, and confidence scoring.
- Implement dashboard aggregations.
- Implement OpenAI provider abstraction using `gpt-4o-mini` as the default configured model, with environment-based override and deterministic fallback.
- Implement merchant/payee aliasing and merchant-context mapping before any LLM prompt is sent.
- Implement accuracy evaluation report.
- Implement frontend flows and responsive UI.
- Add unit, integration, and evaluation tests mapped to acceptance criteria.
- Complete QA and security artifacts.

#### Phase 3: Deliver

- Document setup, environment variables, local run steps, and demo flow.
- Provide deployment guidance appropriate to capstone scope.
- Provide user guide in clear language.
- Confirm no secrets or real financial data are committed.

### Resource Requirements

- Product/requirements owner for artifact quality and scope decisions.
- System architect for SAD, data boundaries, and agent/service design.
- Frontend engineer for responsive web UI.
- Backend engineer for APIs, storage, classification, and LLM provider abstraction.
- Integration engineer for end-to-end flows.
- QA engineer for tests, golden dataset, and acceptance mapping.
- Security engineer for secret scanning, data handling, and LLM safety review.

### Risk Mitigation

| Risk | Mitigation |
| --- | --- |
| Incorrect classification harms trust | Use editable categories, correction history, confidence scores, review queues, and golden-dataset accuracy tests. |
| LLM produces financial advice | Restrict prompts, use deterministic inputs, QA safety tests, and fallback summaries. |
| Sensitive data exposure | Use local/demo data, no committed secrets, minimized logs, deletion/export, and security review. |
| CSV import inconsistency | Publish sample CSV schema, validate rows, and show actionable errors. |
| Scope creep into regulated features | Keep bank integration, credit, tax, investment, and production auth in Future Work. |
| Runtime overengineering | Use CrewAI only for clear agent responsibilities; keep core services deterministic and testable. |

### MVP Definition of Done

- P0 features are implemented or explicitly documented as scoped gaps.
- Golden dataset exists and classifier reaches at least 70% accuracy.
- CSV import, manual entry, category correction, dashboard, and insights/fallback flow work end to end.
- Unit and integration tests map to acceptance criteria.
- Security review confirms no committed secrets and documents residual risks.
- User-facing text is in pt-BR.
- Data export and deletion are available for local/demo data.

## 9. Launch & Go-to-Market Strategy

### Capstone Launch Strategy

The MVP launch is a controlled capstone/demo release, not a commercial public launch. The goal is to demonstrate feasibility, evaluate categorization accuracy, and validate whether Portuguese monthly insights are understandable and useful.

### Demo Flow

1. Start the local/demo application.
2. Open the demo household workspace.
3. Import the sample Brazilian household CSV dataset.
4. Review import validation results.
5. Show monthly dashboard totals and category breakdown.
6. Correct at least one category and show recalculated totals.
7. Generate or display monthly insights in pt-BR.
8. Drill into the source expenses supporting an insight.
9. Run categorization accuracy evaluation and show pass/fail against 70% threshold.
10. Export and delete demo data.

### Validation Plan

- Validate the concept with 3-5 Brazilian target users.
- Ask whether the dashboard answers monthly household spending questions clearly.
- Ask whether insights feel useful, grounded, and nonjudgmental.
- Record category correction pain points.
- Use feedback to prioritize P1 improvements.

### Commercial Go-to-Market

Commercial launch, monetization, and pricing are future work. Before public production launch, the project must complete production authentication, authorization, LGPD review, stronger security controls, incident response planning, and a validated retention/monetization hypothesis.

## Quality Assurance Checklist

- [x] Requirements traceable to MRD, system description, or recorded Assumptions.
- [x] Technical specifications feasible with the selected runtime adapter.
- [x] Success metrics aligned with stated objectives.
- [x] MVP vs Future Work boundaries explicit.
- [x] Market sections marked N/A when MRD was intentionally skipped. MRD was not skipped.

## Sources

- `project-context/1.define/mrd.md`
- IBGE, Pesquisa de Orcamentos Familiares (POF) 2017-2018.
- Banco Central do Brasil, Pix public information and statistics.
- Banco Central do Brasil, Open Finance public information.
- Banco Central do Brasil, Cidadania Financeira and Meu BC materials.
- Lei Geral de Protecao de Dados Pessoais (LGPD), Lei No. 13.709/2018.
- OWASP Application Security Verification Standard.
- OWASP Top 10 for Large Language Model Applications, 2025.
- OECD Recommendation on Financial Literacy.
- FEBRABAN financial education sources.
- Serasa household debt/financial education context.

## Assumptions

- The target geography is Brazil.
- The product language is Portuguese (pt-BR).
- CSV import and export use Portuguese column names: `data`, `descricao`, `valor`, `forma_pagamento`, `estabelecimento`, `categoria`, `recorrente`, and `observacoes`.
- CSV dates use `dd/mm/yyyy` format.
- The MVP uses local/demo access, but its domain model prepares for future login/password access.
- Future login/password includes email-based password recovery.
- Email verification is not required for now.
- Households can eventually include multiple members who live in the same home.
- Future household roles are admin, member, and viewer.
- MVP input methods are CSV import and manual expense entry.
- Bank integration and Open Finance aggregation are out of scope for MVP.
- Currency is BRL only.
- Demo payment methods are cash, debit, and credit; recurrence is an independent optional expense attribute.
- The MVP has one shared local/demo household workspace with no individual identities, invitations, role enforcement, or personal action history; production shared-household access is future work.
- Expenses are assigned to one active leaf category in a hierarchy; parent categories are roll-up groups only.
- Classifier confidence is a 0.0-1.0 heuristic; decisions below 0.70 are flagged for review.
- Insights are generated through the OpenAI API when configured, using `gpt-4o-mini` as the default model and deterministic fallback summaries when unavailable.
- Firebase Firestore free tier is the default remote database choice for the capstone MVP.
- Deterministic services own all totals, percentages, comparisons, and accuracy calculations.
- Categorization learning uses global category frequencies and household-specific history.
- Category restructuring includes create, rename, merge, and expense reassignment.
- The demo MVP acceptance threshold is 70% categorization accuracy on the golden dataset.
- The golden dataset should contain 30-50 anonymized Brazilian household sample expenses and be maintained in both CSV and JSON fixture formats.
- Merchant/payee names sent to LLM prompts are replaced by fictitious aliases and business-context descriptions by default, with reversible mapping only inside trusted backend services.
- Home Financial is an educational/personal finance awareness product, not a regulated financial adviser.
- Commercial market-size figures are not required for capstone MVP acceptance.

## Open Questions

- None at this stage.

## Audit

- Timestamp: 2026-09-25
- Persona id: product-mgr
- Action: create-prd
- Artifact: project-context/1.define/prd.md
- Resolved `AAMAD_TARGET_RUNTIME`: crewai
- Source artifact: project-context/1.define/mrd.md
- Timestamp: 2026-09-28
- Persona id: product-mgr
- Action: quality-review-fixes
- Artifact: clarified recurrence, shared-demo scope, classifier policy, taxonomy, and MRD traceability