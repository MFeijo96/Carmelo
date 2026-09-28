# Market Research Document (MRD): Home Financial

## Context & Instructions

Home Financial is a capstone project for a Brazilian personal finance awareness system that helps households understand expenses, classify spending, and generate monthly insights in Portuguese. The research below frames the opportunity for an MVP that combines expense input, categorization, household-level collaboration, monthly summaries, and LLM-generated educational insights.

This MRD is intended to support Phase 1 Define artifacts in AAMAD. It should inform the PRD, user stories, and later architecture decisions. Because this is a capstone project, recommendations favor an achievable MVP over a fully regulated financial-services product.

## Research Query Structure

**Primary Focus**: Brazilian household personal finance awareness system for monthly expense understanding, collaborative household expense registration, expense classification, and educational insight generation.

**Selected Runtime**: crewai, from `aamad.config.yml`. Runtime choice is treated as an implementation detail for the Build phase, not a market constraint.

**Target Geography**: Brazil.

**Product Language**: Portuguese (pt-BR).

**MVP Scope Decisions**:

- Product type: educational/personal finance awareness product, not regulated financial advice.
- Platform: primarily web; future mobile support should use non-native Android/iOS delivery, such as responsive web/PWA or hybrid wrapper.
- Access model: local/demo usage for MVP, with architecture prepared for future login/password authentication.
- MVP household model: provide one shared local/demo household workspace. People using that local/demo instance can view and register household expenses, but the MVP has no individual accounts, member identities, invitations, or per-person permissions/action history. Do not use it for real household financial data outside a controlled local/demo environment.
- Future household model: production login and multi-household membership with admin, member, and viewer roles; enforce authorization before enabling real external household sharing.
- Input methods: CSV import and manual expense entry.
- Payment methods for demo dataset: cash, debit, and credit. Recurrence is a separate expense attribute, not a payment method; demo records may independently be recurring or non-recurring.
- Currency: BRL only.
- Insights: generated through the OpenAI API using a cost-efficient GPT-4o mini-class model or the current equivalent available at implementation time, with deterministic calculations for totals and comparisons.
- Bank integration: explicitly out of scope for the MVP.
- Categorization: start from a hierarchical Brazilian household taxonomy, assign each expense to exactly one active leaf category, and let users restructure categories. Improve future classification using household correction history before global category frequencies.
- Primary success metric: categorization accuracy. For the demo MVP, 70% accuracy on the golden dataset is good enough for acceptance.
- Categorization measurement: the system should provide a repeatable way to measure accuracy whenever needed, using a curated golden dataset and a report comparing expected categories against predicted categories.
- Future password recovery: login/password should include password recovery by sending an email to the user.

## Executive Summary

Brazilian households face recurring pressure from essential expenses such as housing, food, transportation, utilities, health, education, communication, and debt payments. IBGE's Pesquisa de Orcamentos Familiares (POF) provides the strongest public baseline for common household expense categories in Brazil, while Banco Central do Brasil data shows a highly digital financial environment shaped by Pix and Open Finance. This creates a practical opportunity for a web-first system that helps people understand home expenses without requiring bank integration.

The market is crowded with spreadsheets, banking apps, digital wallets, and personal budget apps. However, many tools either focus on individual accounts, require heavy manual organization, or do not support a shared household view. Home Financial can differentiate as a Portuguese-language, education-oriented, household-aware expense intelligence tool that explains monthly spending, lets users correct/restructure categories, and uses those corrections to improve categorization accuracy over time.

Technical feasibility is high for an MVP if the system starts with CSV import and manual expense entry, then applies deterministic category rules, user correction history, global category frequencies, household-specific history, and LLM-generated educational summaries. Login/password can be deferred for MVP while the domain model is prepared for users, households, memberships, authentication, and admin/member/viewer roles. Automatic bank aggregation, financial advice, tax guidance, credit decisions, and investment recommendations should remain out of scope.

## Detailed Findings by Dimension

### 1. Market Analysis & Opportunity Assessment

#### Key Insights

- Personal finance pain is broad and recurring in Brazil, where households must manage frequent essential expenses, installments, Pix transfers, card payments, utilities, food, housing, and transport.
- Expense understanding is a high-frequency problem. Unlike tax filing or loan applications, categorizing and reviewing spending happens monthly or weekly, making it suitable for retention-oriented software.
- Users already use digital financial channels. Banco Central do Brasil reports Pix has reached more than 170 million individual users, about 80 percent of the Brazilian population, with billions of monthly transactions.
- The best initial target is not advanced investors; it is households that need spending clarity. The strongest capstone use case is explaining where household money went, what changed month over month, and which shared categories deserve attention.
- Willingness to pay is plausible but not proven. A capstone MVP should validate user value through engagement and insight usefulness before assuming subscription monetization.

#### Data Points

- IBGE POF 2017-2018 is the key public reference for Brazilian household budget composition and commonly used categories such as habitacao, alimentacao, transporte, assistencia a saude, educacao, vestuario, higiene/cuidados pessoais, recreacao/cultura, servicos pessoais, fumo, and outras despesas.
- Banco Central do Brasil describes Open Finance as a way for users to control financial data sharing and access services such as simplified financial management, but bank/Open Finance integration is out of MVP scope.
- Banco Central do Brasil reports Pix is used by more than 170 million individuals, with more than 7 billion transactions and more than R$3 trillion in volume in May 2026, indicating that Brazilian users are familiar with digital financial flows.
- The prevalence of Pix, cards, boletos, installments, and manual household payments makes CSV/manual input a reasonable MVP path before any regulated data integration.

#### Source Citations

- IBGE, Pesquisa de Orcamentos Familiares (POF) 2017-2018.
- Banco Central do Brasil, Pix and Open Finance public pages.
- Banco Central do Brasil, Cidadania Financeira and financial education materials.
- FEBRABAN and consumer finance sources for Brazilian household debt/financial education context.

#### Implications

- The MVP should prioritize Portuguese monthly household expense clarity, category explanations, and trend detection over complex financial planning.
- The product should support low-friction CSV/manual entry and a future-ready login/password model.
- Trust, privacy, and explainability are central to adoption; users need to understand why an expense was classified a certain way and be able to correct it.
- Use a shared local/demo workspace to demonstrate household-level visibility without implying that authenticated multi-member collaboration is available in the MVP.

### 2. Technical Feasibility & Requirements Analysis

#### Key Insights

- A practical MVP can be built without direct bank integrations by supporting CSV import and manual expense entry.
- Categorization can combine rules, merchant keyword mapping, user corrections, global category frequencies, household-specific history, and AI-assisted fallback classification.
- A multi-agent design is useful for separating ingestion, classification, insight generation, and user-facing explanation responsibilities.
- The selected `crewai` runtime can fit a capstone architecture where specialized agents coordinate data preparation, categorization review, and narrative insight generation.
- The largest technical risks are data privacy, hallucinated advice, poor categorization accuracy, leakage between household workspaces, and overclaiming financial recommendations.

#### Data Points

- Banco Central do Brasil's Pix data supports a digital-first Brazilian user context, even though bank integration is intentionally excluded from the MVP.
- Banco Central do Brasil's Open Finance materials identify simplified financial management as a consumer benefit, validating the problem space while reinforcing that consented bank-data integration should be future work only.
- IBGE POF organizes Brazilian household expenses into categories that can seed the initial Home Financial taxonomy.
- The project should use the OpenAI API for LLM-generated insights because it offers strong Portuguese support, mature structured-output patterns, broad SDK/tooling support, and a practical MVP path. The implementation should still wrap the provider behind an interface so the team can replace it later if cost, data-policy, or availability constraints change.

#### Source Citations

- Banco Central do Brasil, Pix public information and statistics.
- Banco Central do Brasil, Open Finance public information.
- IBGE, Pesquisa de Orcamentos Familiares (POF) 2017-2018.
- OWASP Top 10 for Large Language Model Applications, 2025.

#### Implications

- Initial data model should include household, member, future role, expense date, description, amount in BRL, merchant/payee, category, payment method, source, recurrence flag, confidence score, and user override flag.
- The system should store original user data separately from derived classifications and insights.
- AI-generated content should be constrained to educational insights, not regulated financial advice.
- The MVP should include a feedback loop so user corrections improve future category mapping.
- The architecture should be prepared for login/password registration, email-based password recovery, authentication, admin/member/viewer roles, and household membership even if MVP access runs in local/demo mode.

### 3. User Experience & Workflow Analysis

#### Key Insights

- The core user journey should answer three questions quickly in Portuguese: Quanto a casa gastou? Para onde foi o dinheiro? O que mudou neste mes?
- Classification must be editable. If users cannot fix a category, they will not trust the monthly insight layer.
- Monthly insights should be plain-language and comparative, not only chart-based.
- Human-in-the-loop review is required for ambiguous expenses, user-defined categories, recurring-expense detection, shared-workspace corrections, and LLM-generated insights.
- Success depends on reducing shame and cognitive load; the interface should explain spending without moralizing.

#### Data Points

- IBGE POF categories suggest a small number of major groups can explain much of a household budget, making monthly dashboard summaries viable.
- Banco Central do Brasil Pix statistics show Brazilian users are accustomed to digital payments, supporting web-first workflows and later responsive/mobile access.
- The household-sharing requirement means the UX must distinguish personal action history, role permissions, and shared household totals.
- In the MVP, shared totals and expense entry are available in one local/demo workspace; personal action history and role-based permissions are deferred until authenticated membership exists.
- Categorization accuracy is the most important success metric, so the UI must make category review, correction, and learning visible.

#### Source Citations

- IBGE, Pesquisa de Orcamentos Familiares (POF) 2017-2018.
- Banco Central do Brasil, Pix public information and statistics.
- Banco Central do Brasil, Open Finance public information.
- OWASP Top 10 for Large Language Model Applications, 2025.

#### Implications

- MVP screens should include a local/demo access state with no login controls, a current shared-household indicator, monthly overview, category breakdown, expense review, manual entry, CSV import, insights, and settings/categories.
- Insight cards should identify drivers in Portuguese, such as "os gastos com alimentacao aumentaram por causa de compras de mercado no fim do mes", and link back to underlying expenses.
- The product should avoid prescriptive claims like "you should invest" or "you can afford" unless future compliance review supports those features.
- The UI should be responsive for web and structured so a future PWA or hybrid mobile app can reuse the same flows.

### 4. Production & Operations Requirements

#### Key Insights

- Even a capstone MVP handles sensitive household financial data, so security and privacy requirements must be treated seriously.
- Deployment can be simple for capstone use, but architecture should avoid storing secrets in the repo and should support later migration to managed infrastructure.
- Observability should measure import success, categorization confidence, user edits, insight generation errors, latency, and data deletion events.
- If login/password and real household sharing are enabled later, authentication, authorization, invitation flow, admin/member/viewer role management, and household data isolation become mandatory.
- If real bank APIs are added later, compliance, vendor terms, consent flows, token security, and incident response requirements increase significantly; bank integration is out of MVP scope.
- The system should provide deletion/export capabilities early because personal finance data is highly sensitive.

#### Data Points

- Banco Central do Brasil reports Pix is available 24/7, widely used, and designed for several payment situations, implying household expenses may come from many digital and manual contexts.
- Banco Central do Brasil Open Finance materials emphasize consent, data choice, and secure sharing, which should guide any future data-sharing design even though bank integration is out of scope.
- The workspace configuration requires security assessment, forbids committed secrets, requires dependency audit, and requires tests mapped to acceptance criteria.

#### Source Citations

- Banco Central do Brasil, Pix public information and statistics.
- Banco Central do Brasil, Open Finance public information.
- Lei Geral de Protecao de Dados Pessoais (LGPD), Lei No. 13.709/2018.
- OWASP Application Security Verification Standard.
- OWASP Top 10 for Large Language Model Applications, 2025.

#### Implications

- MVP should use local/demo storage or a simple secured database with clear environment templates, while preserving entities for users, password-auth identities, households, memberships, and roles.
- Sensitive fields should not be logged in plaintext.
- AI prompts should exclude unnecessary personal identifiers and should use structured household expense summaries where possible.
- Later production hardening should include authentication, encryption at rest, authorization checks, audit logs, dependency scanning, backup/restore, and data retention policy.
- Future login/password should include clear household permissions before real shared household data is enabled.

### 5. Innovation & Differentiation Analysis

#### Key Insights

- The strongest differentiation is not "another budget tracker" but explainable monthly financial intelligence.
- AI can help translate raw spending into understandable narratives, but deterministic controls should govern totals, calculations, and category rules.
- A capstone product can stand out by showing evidence for every insight and allowing users to correct classifications.
- Privacy-first positioning is credible if the MVP avoids bank credentials, starts with CSV/manual input, and provides clear deletion/export options.
- Future integrations could include Open Finance providers, receipt scanning, Pix/payment statement import, PWA/mobile packaging, and educational content partnerships.

#### Data Points

- IBGE POF categories provide a Brazilian baseline taxonomy for spending analysis.
- Banco Central do Brasil Pix and Open Finance materials show Brazil has a mature digital-finance environment, supporting future multi-source import possibilities.
- The user requirement for shared household expenses creates a differentiator versus individual-only budgeting tools.
- The OpenAI API can improve Portuguese insight quality, but all numerical calculations and category accuracy measurements must remain deterministic and testable.

#### Source Citations

- IBGE, Pesquisa de Orcamentos Familiares (POF) 2017-2018.
- Banco Central do Brasil, Pix public information and statistics.
- Banco Central do Brasil, Open Finance public information.
- Lei Geral de Protecao de Dados Pessoais (LGPD), Lei No. 13.709/2018.
- OWASP Top 10 for Large Language Model Applications, 2025.

#### Implications

- Position Home Financial as an assistente de consciencia financeira domestica, not a financial adviser.
- Make insight explainability a product requirement: every generated insight should cite the categories, transactions, or date ranges that produced it.
- Build an extensible classification taxonomy based on Brazilian household categories, but keep the MVP category set small enough for users to understand and restructure.
- Treat categorization accuracy as the primary product KPI and the main QA/evaluation gate. For the demo MVP, the minimum acceptance threshold is 70% accuracy on the golden dataset.

## MRD-to-PRD Traceability Drivers

These decision-driving findings must be represented in the PRD or explicitly deferred:

- **MRD-01 Shared household clarity**: one household view and low-friction expense entry are MVP needs; authenticated member identities, invitations, and role enforcement are future work.
- **MRD-02 Low-friction input without bank access**: CSV and manual entry are MVP; direct bank/Open Finance integration is out of scope.
- **MRD-03 Classification trust**: users need editable, explainable categories and a repeatable accuracy measure.
- **MRD-04 Brazilian household taxonomy**: use familiar categories, permit household customization, and assign each expense to one leaf category so totals are unambiguous.
- **MRD-05 Grounded, nonjudgmental insight**: pt-BR explanations must cite supporting data and avoid financial advice.
- **MRD-06 Sensitive-data control**: minimize LLM disclosure and provide export/deletion; production security controls precede real shared household data.
- **MRD-07 Recurrence analysis**: recurrence is a separate expense attribute from cash/debit/credit payment method; detection can be simple in MVP and more advanced later.
- **MRD-08 Responsive web access**: support desktop and mobile web; native apps and PWA packaging are deferred.
- **MRD-09 Unproven willingness to pay**: validate usefulness with target users; commercial launch and monetization remain future work.

## Critical Decision Points

### Go/No-Go Factors

- Go if MVP scope is limited to expense classification, monthly summaries, trend detection, and educational insights.
- Go if sensitive-data handling, deletion, and no-secret repository practices are included from the start.
- Go if local/demo usage can preserve a future-ready model for users, households, memberships, and permissions.
- No-go for direct bank integration in MVP.
- No-go for regulated financial advice, credit recommendations, tax recommendations, or investment advice without legal/compliance review.
- Go if the system supports manual correction of categories and avoids opaque AI-only classification.
- Go if categorization accuracy can be measured against a golden dataset and reaches at least 70% for the demo MVP.

### Technical Architecture Choices

- Use a modular backend with clear services/agents for ingestion, normalization, categorization, aggregation, and insight generation.
- Use `crewai` for multi-agent orchestration only where it adds clarity, such as separating classifier, analyst, and explainer responsibilities.
- Use deterministic arithmetic for totals, month-over-month comparisons, and category percentages.
- Use the OpenAI API for narrative insight generation and ambiguous category suggestions, guarded by structured inputs, confidence thresholds, and no-advice constraints. Keep a provider abstraction so the system can switch LLM providers later.
- Start with CSV/manual entry; bank integration remains out of scope.
- Model users, future password credentials, password recovery flow, households, household memberships, admin/member/viewer roles, categories, expenses, imports, classification decisions, and insight generation runs from the start.

### Market Positioning

- Primary segment: Brazilian households that need simple monthly clarity over shared home expenses.
- Secondary segment: students, young professionals, couples, families, and shared homes learning budgeting habits.
- Value proposition: "Entenda os gastos da sua casa em portugues claro, com categorias editaveis e insights baseados nas suas despesas."
- Differentiator: transparent LLM-assisted insights with source expenses, household collaboration, and user-correctable classification.

### Resource Requirements

- Team: product/requirements owner, frontend engineer, backend engineer, integration engineer, QA engineer, and security reviewer per AAMAD workflow.
- MVP timeline: 2-4 weeks for capstone scope if limited to CSV/manual entry, dashboard, categorization, and monthly insights.
- Data requirements: sample CSV datasets, anonymized Brazilian household demo expenses in BRL, cash/debit/credit payment examples with an independent recurrence flag, and a hierarchical category taxonomy seeded from IBGE POF categories and common app-level categories.
- Budget: low for capstone/local deployment; higher if adding hosted database, authentication, LLM API usage, or production sharing.

## Risk Assessment Matrix

| Risk Level | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| High | Sensitive household financial data exposure | Loss of trust, privacy harm, LGPD risk, project failure | Avoid committing secrets, minimize stored data, redact logs, support deletion/export, run security review |
| High | AI hallucinated financial advice | User harm and compliance risk | Restrict outputs to observations and educational insights; add disclaimers; use deterministic calculations |
| High | Incorrect expense classification | Bad insights and low trust; failure against primary metric | Use confidence scores, editable categories, review queue, user correction history, golden-dataset tests, and repeatable accuracy reports |
| High | Household data isolation failure | Users may see or edit expenses from the wrong household | Design household membership and authorization boundaries before enabling real login/password |
| Medium | Data import inconsistency | Failed onboarding and inaccurate summaries | Support a documented CSV format, validation errors, and sample file templates |
| Medium | Scope creep into bank aggregation | Security/compliance complexity | Keep direct bank API integration out of MVP; document as future work only |
| Medium | User disengagement after first import | Low retention | Provide monthly comparison, recurring expense detection, and personalized but grounded insight cards |
| Medium | Bias or judgmental Portuguese language | User discomfort, abandonment | Use neutral pt-BR copy; avoid shame-based recommendations |
| Low | Market-size uncertainty for monetization | Weak business model assumptions | Treat monetization as validation item; measure activation and repeat use first |
| Low | Runtime overengineering | Slower delivery | Use multi-agent orchestration only for clear separations of responsibility |

## Actionable Recommendations

### Immediate Next Steps (48 Hours)

- Create `project-context/1.define/prd.md` from this MRD.
- Define MVP user personas for Brazilian households, shared homes, couples, and families.
- Define the CSV import format and sample file.
- Draft the hierarchical category taxonomy using IBGE POF-inspired categories plus common app-level categories. For example, place `mercado` and `restaurantes` under `alimentacao`, and `assinaturas` under `lazer`; assign expenses only to leaf categories.
- Define explicit non-goals: bank integration, investment advice, tax advice, credit decisions, automated bank connection, and real-time financial coaching.
- Create 30-50 anonymized Brazilian household sample expenses in BRL for design, QA, demo, and categorization accuracy testing. Include cash, debit, and credit payment methods, with recurrence represented independently as a true/false expense attribute.

### Short-Term Priorities (30 Days)

- Build MVP user stories for the shared local/demo workspace, future login/password readiness, deferred authenticated household sharing, CSV import, manual expense entry, category review, dashboard, monthly insights, and data deletion/export.
- Define evaluation criteria for categorization accuracy as the primary KPI, with 70% minimum accuracy for demo MVP acceptance and repeatable measurement on demand.
- Produce the SAD with security, privacy, storage, and LLM boundaries.
- Build a golden dataset with expected categories and expected insight examples in Portuguese.
- Validate the concept with 3-5 Brazilian target users by asking whether generated insights are understandable, useful, and trustworthy.

### Long-Term Strategy (6-12 Months)

- Add recurring-expense detection and anomaly detection after basic categorization is reliable.
- Add optional Open Finance/account aggregation only after security, consent, LGPD, and compliance review.
- Add production login/password registration, email-based password recovery, household invitations, admin/member/viewer roles, and audit logs.
- Add PWA or hybrid mobile delivery for Android and iOS.
- Add educational explanations tied to user behavior, such as cash-flow timing, category drift, and savings pressure.
- Explore freemium monetization only after measuring repeat monthly usage and user trust.

## Sources

1. IBGE, Pesquisa de Orcamentos Familiares (POF) 2017-2018, https://www.ibge.gov.br/estatisticas/sociais/populacao/24786-pesquisa-de-orcamentos-familiares-2.html
2. IBGE Biblioteca, POF 2017-2018 publicacao completa, https://biblioteca.ibge.gov.br/visualizacao/livros/liv101670.pdf
3. IBGE SIDRA, tabelas da Pesquisa de Orcamentos Familiares, https://sidra.ibge.gov.br/pesquisa/pof/tabelas
4. Banco Central do Brasil, Pix, https://www.bcb.gov.br/estabilidadefinanceira/pix
5. Banco Central do Brasil, Pix em numeros/estatisticas, https://www.bcb.gov.br/estabilidadefinanceira/pix-em-numeros-estatisticas
6. Banco Central do Brasil, Open Finance, https://www.bcb.gov.br/estabilidadefinanceira/openfinance
7. Banco Central do Brasil, Cidadania Financeira, https://www.bcb.gov.br/cidadaniafinanceira
8. Banco Central do Brasil, Meu BC, https://www.bcb.gov.br/meubc
9. Lei Geral de Protecao de Dados Pessoais (LGPD), Lei No. 13.709/2018, https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm
10. Governo Federal, Estrategia Nacional de Educacao Financeira (ENEF), https://www.gov.br/investidor/pt-br/educacional/programas/estrategia-nacional-de-educacao-financeira-enef
11. FEBRABAN, Meu Bolso em Dia, https://meubolsoemdia.com.br/
12. FEBRABAN, portal institucional e educacao financeira, https://portal.febraban.org.br/
13. Serasa, Mapa da Inadimplencia e Renegociacao de Dividas no Brasil, https://www.serasa.com.br/limpa-nome-online/blog/mapa-da-inadimplencia-e-renegociacao-de-dividas-no-brasil/
14. OECD, Recommendation on Financial Literacy, https://legalinstruments.oecd.org/en/instruments/OECD-LEGAL-0461
15. OWASP, Top 10 for Large Language Model Applications 2025, https://owasp.org/www-project-top-10-for-large-language-model-applications/
16. OWASP, Application Security Verification Standard, https://owasp.org/www-project-application-security-verification-standard/
17. Bank for International Settlements, Financial stability risks from cryptoassets in emerging market economies, August 2023, https://www.bis.org/publ/bppdf/bispap138.htm
18. Banco Central do Brasil, politica de privacidade, https://www.bcb.gov.br/acessoinformacao/politicaprivacidade

## Assumptions

- The target geography is Brazil.
- Home Financial is an educational/personal finance awareness product, not a regulated financial adviser.
- The MVP uses CSV/manual expense input.
- Bank integration is out of scope for MVP.
- The product language is Portuguese (pt-BR).
- Insights are generated by the OpenAI API, with deterministic calculations and source-expense grounding.
- MVP access is local/demo, but the system must be prepared for future login/password and shared household access.
- Future household roles are admin, member, and viewer.
- Categorization learning should use both global category frequencies and household-specific history.
- The system supports BRL only.
- Demo payment methods are cash, debit, and credit. Recurrence is a separate optional expense attribute.
- The primary product metric is categorization accuracy.
- The demo MVP acceptance threshold is 70% categorization accuracy on the golden dataset.
- The team needs a repeatable categorization accuracy measurement process that can be run whenever needed.
- Future login/password includes email-based password recovery.
- Email verification is not needed for now.
- Market-size figures from commercial analyst reports were not used as primary evidence because several pages are paywalled or blocked; public household finance and expenditure data is used instead.
- IBGE pages blocked automated extraction in this session, but POF remains the authoritative Brazilian household budget source and should be manually verified during PRD/SAD review.
- Source data was accessed through available web extraction on 2026-09-25; some source pages may change after this date.

## Open Questions

- None at this stage.

## Audit

- Timestamp: 2026-09-25
- Persona id: product-mgr
- Action: update-mrd
- Artifact: project-context/1.define/mrd.md
- Runtime noted: crewai from `aamad.config.yml`
- Source quality note: Brazilian government and standards sources are primary. Some IBGE pages blocked automated extraction but remain authoritative and should be manually verified before final PRD signoff.
- Timestamp: 2026-09-28
- Persona id: product-mgr
- Action: quality-review-fixes
- Artifact: clarified MVP household collaboration, payment/recurrence distinction, taxonomy, and PRD traceability drivers