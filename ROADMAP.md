# PaperLoop Master Tracker and Roadmap

This document records the current checkout aligned to `origin/main` (`3241ef2`) as of 2026-11-24. “Implemented” reflects repository behavior and available automated checks; synthetic ML results do not establish production quality. Milestones 9–10 extend the supplied eight-step plan using the QA/deployment scope in `project/agents/qa-testing-devops.md`.

## Master Functional Requirements Tracker

| ID | Requirement | Django modules / key files | Test coverage status | Completion |
|---|---|---|---|---|
| FR-01 | Organization account registration, authentication, role-based permissions, and tenant data boundaries | `accounts/models.py`, `forms.py`, `authentication.py`, `decorators.py`, `views.py`, `urls.py`, `templates/accounts/register.html` | Role/access tests in `accounts/tests.py`; registration and duplicate-registration acceptance tests in `accounts/test_step9_integration.py` | Implemented; registration and role flows tested |
| FR-02 | Admin organization verification and account management | `accounts/admin.py`, `accounts/models.py`, `config/urls.py`, `templates/admin/` (Django admin) | Verify/reject/suspend actions tested in `AdminManagementIntegrationTests` in `accounts/test_step9_integration.py` | Implemented and tested; detailed FR-02 policy remains unspecified |
| FR-03 | Institution-owned paper listing create, edit, withdraw, and lifecycle restrictions | `accounts/models.py`, `listing_forms.py`, `views.py`, `urls.py`, `templates/accounts/listing_form.html`, `institution_dashboard.html` | Create/edit/withdraw and owner-scoped photo access tested in `ListingManagementIntegrationTests` and `MediaStorageIntegrationTests`; broader workflow tests also cover listing use | Implemented and tested |
| FR-04 | Paper category and positive estimated quantity with “other” details | `accounts/models.py`, `listing_forms.py`, `accounts/forms.py`, `templates/accounts/listing_form.html` | Category detail requirement and collection quantity persistence are covered by Step 9 integration and FR-09/10 workflow tests | Implemented and tested |
| FR-05 | Pickup address, collection dates, and private supporting photo upload | `accounts/models.py`, `listing_forms.py`, `views.py` (`listing_photo`), `templates/accounts/listing_form.html` | Date ordering, owner-only photo access, anonymous access control, and media persistence tested in `accounts/test_step9_integration.py` | Implemented and tested |
| FR-06 | Recycler profile, accepted categories, service area, availability, and capacity | `accounts/models.py`, `forms.py`, `views.py`, `matching.py`, partner templates | `TestRecyclerProfileFR06`, `RecyclingProfileFormTest`, `RecyclerDiscoveryFR08Tests` | Implemented; covered |
| FR-07 | Rank eligible recycler candidates for a listing with explainable factors | `accounts/matching.py`, `ml_engine/inference/partner_match.py`, model/training modules, recommendation template | Matching/recommendation tests and `MLTrainingPipelineTests`; fallback is also tested | Implemented; checkpoint and complete feature data required for learned ranking |
| FR-08 | Let institutions discover and select eligible recyclers | `accounts/matching.py`, `accounts/views.py`, `accounts/urls.py`, directory/recommendation templates | `TestRecyclerMatchingAndSelectionFR08`, `RecyclerDiscoveryFR08Tests`, template integration tests | Implemented; covered |
| FR-09 | Collection request submission, partner decisions, scheduling, cancellation, and status lifecycle | `accounts/models.py`, `accounts/views.py`, `accounts/urls.py`, collection templates | `CollectionWorkflowFR09FR10Tests` | Implemented; covered |
| FR-10 | Preserve estimated and final collected quantities | Collection model, completion views/forms/templates | `CollectionWorkflowFR09FR10Tests` | Implemented; covered |
| FR-11 | Persist and expose completed recycling transaction history | `accounts/models.py`, `accounts/views.py`, `accounts/urls.py`, transaction templates | `TransactionsFR11FR12Tests` | Implemented; covered |
| FR-12 | Generate digital recycling records and environmental impact summaries | `accounts/impact.py`, transaction model/views and digital-record templates | `TransactionsFR11FR12Tests` checks calculation, completion, access, and rendered record | Implemented; review impact assumptions before external claims |

## 10-Milestone Project Roadmap

| # | Milestone and deliverables | Current status | Verification / acceptance criteria |
|---:|---|---|---|
| 1 | Project initialization, agent ownership notes, requirements tracker, and roadmap | **Complete** — project structure and agent notes exist; this tracker now supplies the central FR and milestone status | `ROADMAP.md` contains FR-01–FR-12 and all ten milestones; repository structure is present |
| 2 | Django foundation, PostgreSQL configuration, ORM schema, registration/RBAC, admin verification | **Complete for local development** — PostgreSQL and migrations are configured; direct FR-01/02 acceptance coverage can improve | Django check, migration check, and full PostgreSQL test suite pass |
| 3 | Institution listing management (FR-03–FR-05) and dashboard forms/tables | **Implemented; verification coverage partial** | Listing create/edit/withdraw, category/quantity/date validation, photo privacy, and owner scoping pass dedicated acceptance checks |
| 4 | Recycler profiles/capacity (FR-06) and discovery/selection (FR-08) | **Implemented** | Profile authorization, capacity/category filtering, recommendation explanations, and partner selection tests pass |
| 5 | Synthetic data, PyTorch forecasting, recycler ranking, bulk aggregation, and saved artifacts (FR-07) | **Complete for synthetic pilot** — generated CSVs, checkpoints, and metadata are present locally and ignored by Git | Train and load all three models; live app scores require complete candidate inputs; real outcome validation remains future work |
| 6 | Collection requests, status tracking, estimated/final quantity (FR-09–FR-10) | **Implemented** | Lifecycle, permissions, validation, quantity persistence, and side effects pass workflow tests |
| 7 | Transaction history and digital recycling records (FR-11–FR-12) | **Implemented** | Completion, impact, authorization, transaction history, and record rendering pass workflow tests |
| 8 | Bootstrap dashboard integration and AI recommendation presentation | **Implemented** | Admin, institution, partner, recommendation, and aggregation pages smoke-check against PostgreSQL with model scores |
| 9 | Django, PyTorch, and media-storage integration; role-based functional verification for FR-01–FR-12 | **Complete for local integration and automated verification** — Django-backed workflows, saved model inference, and private media storage are exercised on PostgreSQL | All 67 tests pass on PostgreSQL; dashboard/AI smoke checks return HTTP 200; saved forecasting, ranking, and aggregation checkpoints load. Production deployment hardening remains for milestone 10 |
| 10 | Controlled pilot and release readiness | **Deployment configuration and evaluation documentation prepared; cloud deployment and pilot remain outstanding** | Render Blueprint, PostgreSQL wiring, production environment settings, and project evaluation materials are in place. Deploy and smoke-check on Render, capture real UI screenshots, validate model quality on real outcomes, approve impact benchmarks and FR-02 policy, and document support/rollback and sign-off |

## Current verification notes

- The local PostgreSQL target is `paperloop`; Django uses PostgreSQL settings from `.env` (`DATABASE_URL` takes precedence when present).
- Generated pilot CSVs and trained checkpoints live under ignored paths `ml_engine/datasets/data/` and `ml_engine/artifacts/`. They are local runtime outputs and should be regenerated in a fresh checkout.
- Synthetic training and held-out metrics only verify pipeline execution. They do not establish production recommendation or forecasting quality.
- The current automated suite contains 67 tests; the final PostgreSQL-backed run passed in 199.966 seconds (`python manage.py test --verbosity 1 --keepdb`).
- Step 9 details and role/FR verification evidence are recorded in [Step 9 integration and testing](docs/system-requirements/Step-09-system-integration-and-testing.md).
- Pilot records and all model evaluation labels are synthetic; they are for workflow checks, not real-world performance claims.
- Step 10 deployment configuration and evaluation materials are documented in [Step 10](docs/Step-10-deployment-and-final-documentation.md); no Render deployment has been launched from this checkout.
