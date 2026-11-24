# PaperLoop Master Roadmap and Functional Tracker

This tracker is the project status source of truth for the FRs and ten milestones. Status reflects code and checks currently present in this repository; it does not imply production readiness.

## Project objectives and boundaries

- Connect educational institutions with verified recycling and collection partners for paper-waste listings and collections.
- Support organization registration, role-based access, administrator verification, listing and partner profiles, recommendations, collection tracking, transactions, and recycling impact records.
- Use Django and its ORM with PostgreSQL as the configured relational database. SQLite remains available for local development.
- Use PyTorch forecasting, partner ranking, and bulk aggregation models where trained artifacts and required data are available. Synthetic pilot data is for development and is not evidence of real-world model performance.
- Payment processing, production deployment, real-data model validation, and any organization policies beyond the documented initial verification behavior are outside the verified scope of this tracker.

The full proposal was not present in the repository during this audit. These objectives and boundaries are taken from the supplied Step 1-8 plan and existing repository documentation; confirm them against the canonical proposal when it is added.

## Functional requirements tracker

| FR | Scope | Status | Evidence / remaining work |
| --- | --- | --- | --- |
| FR-01 | Registration and role-based access | Implemented and verified | Email-based account, organization roles, protected views, case-insensitive duplicate handling (including concurrent submissions), and matching profile creation are covered by tests. |
| FR-02 | Admin verification and management | Implemented and verified under the documented initial policy | Admin actions verify, reject, and suspend organizations; status is read-only outside those actions, and reviewer/time audit fields are recorded. Confirm final policy against the canonical proposal when available. |
| FR-03 | Institution paper listings | Implemented and verified | Institutions can save drafts, publish, edit, and withdraw their own listings. Any non-cancelled collection record locks edit/withdraw; cancelled records do not. |
| FR-04 | Category and estimated quantity | Implemented and verified | Category choices, required details for Other, and positive quantity validation are covered by tests. |
| FR-05 | Location, period, and photo | Implemented and verified | Required pickup address/city/country, ordered optional dates, a 5 MB image limit, and owner-only photo delivery are covered by tests. |
| FR-06 | Recycler profile and capacity | Implemented | Partner profile form and capacity/service-area eligibility are present. |
| FR-07 | Recycler recommendation | Implemented; synthetic model validated | Live ranking derives smoothed fulfillment from resolved collection outcomes, supplies explicit neutral priors for unavailable optional rating/price/history, and uses geocoded distance plus capacity. The explanation identifies priors and model factors. Missing coordinates/artifact use the rules-based fallback. Validate ranking on real outcomes before operational use. |
| FR-08 | Partner selection | Implemented | Institution can select an eligible recommendation; server rechecks eligibility when creating a request. |
| FR-09 | Collection request and status | Implemented and verified | Request, accept/reject, scheduling, completion, and cancel transitions are enforced server-side; scheduling requires acceptance and completion requires a scheduled pickup. Listing status updates are transactionally locked. |
| FR-10 | Estimated and final quantities | Implemented and verified | Estimated kg is snapshotted when requested; final kg is validated as positive and stored only on completion. Rejected/invalid transitions cannot create final quantities or transactions. |
| FR-11 | Transaction history | Implemented | Role-scoped transaction history and detail pages exist. |
| FR-12 | Digital recycling record and impact summary | Implemented | Completion creates a reference and an impact record page with print/save-to-PDF. Impact values are benchmark estimates, not independent measurement. |

## Ten milestone tracker

| Milestone | Related plan step | Outcome / acceptance criteria | Status |
| --- | --- | --- | --- |
| M1. Repository and roadmap | Step 1 | Git repository, project layout, project boundaries, FR-01 to FR-12 tracker, and ten milestone tracker are present. | In progress - tracker added; canonical proposal still needed. |
| M2. Django architecture and schema | Step 2 | Django project, PostgreSQL configuration, ORM models, and versioned migrations are available. | Implemented; additive reviewer audit migration applied to the local PostgreSQL database. |
| M3. Registration and admin verification | Step 2 | Public roles can register; protected routes enforce role/verification; staff can review accounts. | Implemented and covered by FR-01/FR-02 tests under the documented initial verification policy. |
| M4. Institution listings | Step 3 | Institutions save drafts, publish, edit, and withdraw categorized listings with pickup details, dates, and optional private photos; collection history controls editing/withdrawal. | Implemented and verified with PostgreSQL-backed listing workflow tests. |
| M5. Recycler profiles and selection | Step 4 | Partners manage capabilities; institutions discover eligible partners and submit a selection. | Implemented; rule-based ranking is the safe fallback. |
| M6. AI and pilot data | Step 5 | Synthetic data generation, PyTorch training/inference, forecasting, ranking, and bulk aggregation are available. | Implemented and pipeline verified; generated local checkpoints are synthetic pilot artifacts. Real-data validation remains outstanding. Forecasting requires four recent consecutive weekly observations and will not fill missing weeks with zero. |
| M7. Collection lifecycle | Step 6 | Collection requests can be accepted/rejected, scheduled, cancelled, completed, and quantities recorded. | Implemented and verified by PostgreSQL-backed `TransactionTestCase` tests, including guards against scheduling before acceptance and completion before scheduling. |
| M8. Transactions and impact records | Step 7 | Completion creates transaction history and a digital impact record. | Implemented. |
| M9. Dashboard and UI integration | Step 8 | Admin, institution, and partner workflows render with Bootstrap; recommendation method and score source are clear. | Implemented and template-tested; browser-level visual review remains outstanding because no local browser renderer is installed. |
| M10. Integrated quality and release readiness | Cross-cutting | PostgreSQL workflow tests, security/configuration review, documentation, and deployment checks are complete. | In progress - tests pass; browser visual review, broader security/configuration review, and deployment checks remain. |

## Verification record

- Current verification: `python manage.py test` ran 87 tests successfully; the Step 6 PostgreSQL-backed workflow suite ran 13 tests, including guards against scheduling before acceptance and completion before scheduling. Step 8 includes an admin dashboard render assertion and recommendation card score/factor assertions. `generate_pilot_data --institutions 80 --requests 1500 --months 24 --seed 42` generated the pilot dataset; `train_ai_models --seed 42 --epochs 35` trained all three models and wrote local checkpoints. Metrics use synthetic labels and do not establish real-world quality. The reviewer audit migration was applied to local PostgreSQL; browser-level visual review, broader security/configuration review, and deployment checks remain before M10 is complete.
- The FR-09/FR-10 workflow tests use `TransactionTestCase`, exercising requests without `TestCase`'s outer transaction. Browser-level UI review, broader security/configuration review, and deployment checks remain before M10 is complete.
