# PaperLoop Project Evaluation Presentation

## Slide 1 — PaperLoop

Connecting educational institutions with recycling partners to coordinate paper recovery.

## Slide 2 — Problem and goal

- Institutions need a clear way to list recyclable paper and arrange pickup.
- Partners need structured requests that reflect paper type, quantity, location, and capacity.
- PaperLoop provides a role-based workflow to coordinate those steps and preserve completion records.

## Slide 3 — User roles and workflow

1. An institution creates and manages a paper listing.
2. It finds an eligible recycling partner and sends a collection request.
3. The partner accepts or rejects, schedules a pickup, and records collected quantity.
4. PaperLoop records the completed transaction and digital recycling summary.
5. Platform staff verify organization accounts through Django admin.

## Slide 4 — Architecture

- Django 5.2 application and ORM, with PostgreSQL for operational data.
- `accounts` owns authentication, organization profiles, listings, collections, and transactions.
- Django templates and Bootstrap provide the web UI; WhiteNoise serves deployed static assets.
- `ml_engine` contains prototype forecasting, recycler ranking, and bulk aggregation workflows.

## Slide 5 — Functional scope

- FR-01–FR-05: registration, role boundaries, verification, and institution listings.
- FR-06–FR-08: partner profiles, eligibility, discovery, and explainable recommendations.
- FR-09–FR-10: request lifecycle and estimated/final quantity tracking.
- FR-11–FR-12: transaction records and impact summaries.

## Slide 6 — Verification evidence

- Existing Step 9 report records 67 PostgreSQL-backed tests passing.
- Existing Django Client smoke checks returned HTTP 200 for Admin, Institution, Recycler, recommendation, and bulk aggregation pages.
- The test suite verifies role boundaries and core workflow behavior; ML pilot data and model labels are synthetic.

## Slide 7 — Deployment

- Render Blueprint provisions the web service and PostgreSQL database.
- Build installs dependencies, collects static files, and migrates the database.
- Gunicorn runs the Django WSGI app; WhiteNoise serves static files.
- Production secrets and hosts are supplied through Render environment variables.
- The checked-in free-plan configuration is for a disposable demonstration, not persistent pilot data.

## Slide 8 — Limitations and next steps

- Deploy and capture the live application; verify it against the PostgreSQL service.
- Configure persistent object storage for uploaded listing photos before a pilot.
- Select persistent database/service plans and establish backup and restore procedures.
- Validate recommendation/forecast quality with real outcomes and approve impact assumptions with stakeholders.

## Slide 9 — Demonstration

Use the screenshots listed in `screenshots/README.md` once captured from the live service. Keep credentials and personal information out of the presentation.
