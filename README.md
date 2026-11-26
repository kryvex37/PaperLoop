# PaperLoop

PaperLoop is a Django application for educational institutions and recycling/collection partners to coordinate bulk paper recycling. It covers **FR-01: User Registration and Role-Based Access Control**, the verification foundation of **FR-02**, and institution paper listings for **FR-03, FR-04, and FR-05**.

## Included in FR-01

- Organization registration as an Educational Institution or Recycling/Collection Partner. New organizations start in pending review; they can sign in but cannot use role-specific features until verified.
- Email-based authentication and secure password hashing through Django authentication.
- A custom account model with organization name, contact person, phone, and role.
- Separate institution and partner dashboards, protected by server-side role checks.
- Responsive registration and sign-in pages using Bootstrap 5.3.9 with PaperLoop styles.
- Django administration for platform staff and superusers, including verification, rejection, and suspension actions.
- Initial ORM records for educational institutions, recycling profiles, paper listings, collections, and completed transactions.
- Bootstrap institution dashboard with create, edit, and withdraw listing flows; listings capture paper category, estimated kilograms, pickup location, collection window, and an optional private photo upload.
- PostgreSQL configured through environment variables.

Verification policy assumption: registrations remain enabled for authentication so users can see review status, while protected organization pages require verified status. Rejection retains the account for audit and support; suspension also disables sign-in. The schema models one organization profile per account for this initial milestone.

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set the values you need. The project loads this local file automatically; operating-system environment variables take precedence. Keep `.env` private and use a strong `DJANGO_SECRET_KEY` outside local development.
4. Create the PostgreSQL database configured by `DB_NAME` (default `paperloop`) with owner `DB_USER` if it does not already exist. With a local `postgres` role, connect to the maintenance database and run `CREATE DATABASE paperloop OWNER postgres;`. Django migrations create tables but do not create the database.
5. Apply migrations: `python manage.py migrate`.
6. Create a platform administrator: `python manage.py createsuperuser`.
7. Start the development server: `python manage.py runserver`.
8. Open `/accounts/register/` to register an institution or partner, `/accounts/login/` to sign in, or `/admin/` for the Django administration site.

**Database:** PaperLoop uses PostgreSQL exclusively. Copying `.env.example` to `.env` with the `DB_*` values set (defaults point at `paperloop_db` on `127.0.0.1:5432`) configures PostgreSQL. If `DB_NAME` is left empty, Django silently falls back to a local `db.sqlite3` file — this is not recommended. You can also set `DATABASE_URL` to a `postgres://` or `postgresql://` connection string instead of the individual `DB_*` fields. A URL can include `?sslmode=require` when your database provider requires TLS.
Set `DATABASE_URL` to a PostgreSQL connection string, or set `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and optional `DB_SSLMODE`. A URL can include `?sslmode=require` when your database provider requires TLS. PostgreSQL is required; Django reports a configuration error if it is not configured.

## AI pilot pipeline

The `ml_engine` package contains a seeded NumPy/pandas pilot generator, a next-week paper-waste forecaster, a grouped pairwise recycler ranker, and a spatial-temporal bulk aggregation scorer. The generator writes synthetic institutions and recyclers, 24 months of calendar-aware weekly waste records, transaction and pickup history, geo-clustered pickup requests, labeled recycler candidates, and aggregation proposals. It does not create or mutate Django production rows. Synthetic records and labels exist to exercise the pipeline and do not represent observed marketplace behavior.

The forecaster uses weekly lags, institution size, paper-category shares, and calendar features; it returns a point estimate and an approximate 90% prediction interval. The ranker uses distance, capacity utilization, paper compatibility, fulfillment, ratings, and price competitiveness, and explains each score through feature perturbation. Django recommendations enforce FR-06 eligibility before ranking. Optional location and ranking signals may be missing on real profiles, in which case the safe baseline is used. The pilot seeder adds clearly synthetic values to exercise live ranking; missing or invalid artifacts also use the fallback.

Institution and recycler profiles now store nullable latitude/longitude. Institutions also store student count; `WasteRecord` stores weekly weights by paper grade. Institutions can update size and location at `/accounts/institution/profile/`; partner profile forms accept coordinates. The institution dashboard shows four forecast weeks when at least four recorded weeks exist, with an exam-season alert and a calendar-adjusted baseline fallback if no checkpoint is available. `/accounts/ai/bulk-aggregation/` lists feasible bundles across geocoded active listings and verified recyclers. New or un-geocoded profiles receive explanatory empty states. Existing FR-07 recommendations render reason factors at `/accounts/institution/listings/<id>/recommendations/`.

`ml_engine.services.forecast_week()` exposes inference for a validated feature row; `forecast_institution()` derives rows from persisted `WasteRecord`s. `recommend_bulk_aggregations()` accepts pickup requests with coordinates/windows and recycler capacity/type/location data; it filters radius, window overlap, per-load dispatch threshold, truck capacity, paper compatibility, service area, and recycler capacity before scoring bundles. It returns participants, combined kg, savings, transport cost per kg, explanation factors, and the best capacity-compatible recycler.

After configuring `DATABASE_URL` for PostgreSQL in the ignored `.env`, run `python manage.py migrate` and `python manage.py seed_pilot_data`. The seeder creates idempotent Dhaka pilot organizations, geo coordinates, 104 weeks of synthetic grade-level weights with academic-cycle effects, and active listings only where pilot records are insufficient. Seeded data is marked synthetic and never overwrites non-pilot organizations or waste rows.

From the `PaperLoop` directory, run:

```powershell
python manage.py generate_pilot_data --institutions 80 --requests 1500 --months 24 --seed 42
python manage.py train_ai_models --seed 42 --epochs 35
```

Pilot CSV data and `.pt`/`.json` checkpoints are generated under `ml_engine/datasets/data/` and `ml_engine/artifacts/` and are excluded from Git. Training uses a chronological holdout for forecasting, request-group holdout for ranking, and a seeded shuffled holdout for aggregation. JSON sidecars record metrics, seed, feature schema, feature scaling, and configuration. Metrics evaluate synthetic data only; validate with appropriate historical outcomes and compare to a baseline before drawing conclusions about real marketplace performance. The full suite contains 67 tests; run `python manage.py test --verbosity 1` to execute it.

### PostgreSQL database setup

Set `DB_NAME=paperloop`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` in `.env`, or provide a PostgreSQL `DATABASE_URL` (which takes precedence). Start PostgreSQL using the method for your installation. If the database is missing, use pgAdmin or connect with `psql -h 127.0.0.1 -p 5432 -U <database_admin_role> -d postgres` and run `CREATE DATABASE paperloop OWNER <application_role>;`. The application role needs database-creation permission, or an administrator can create it. Then run `python manage.py migrate`. Never commit `.env` or credentials.

See [ROADMAP.md](ROADMAP.md) for the FR-01–FR-12 tracker, test coverage, and 10-milestone status.

Step 9 integration and end-to-end verification results are documented in [docs/system-requirements/Step-09-system-integration-and-testing.md](docs/system-requirements/Step-09-system-integration-and-testing.md).

## Render deployment

The repository includes a Render Blueprint in [`render.yaml`](render.yaml), a pinned Python runtime in [`.python-version`](.python-version), and the [build script](build.sh). The Blueprint creates a Django web service and a PostgreSQL database, connects them through Render's internal database URL, collects static files with WhiteNoise, and runs migrations during each build.

1. Push this repository to a Git provider connected to Render.
2. In Render, create a Blueprint deployment from the repository and review the proposed resources before applying it. The checked-in Blueprint uses free plans for a demo deployment; select a paid persistent database plan before storing pilot or production data.
3. Wait for the build to finish. The generated `DJANGO_SECRET_KEY` stays in Render environment settings. To use a custom domain, update `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to match it.
4. Create the first staff account from the service's Render Shell with `python manage.py createsuperuser`.
5. Open the service URL and check the home/dashboard route, `/admin/`, and static styles. Add evaluation screenshots under `docs/project-evaluation/screenshots/` using the capture list in that directory's README.

Deployment commands and variables are described in [Step 10 deployment and evaluation](docs/Step-10-deployment-and-final-documentation.md). The free database plan is intended only for a disposable demonstration; confirm current Render retention, pricing, and service limits before choosing a production plan.

## Security and scope notes

- `DJANGO_DEBUG` defaults to `true` for local development. Set it to `false`, use a strong secret, configure allowed hosts, HTTPS, and deployment-specific security settings before exposing the application.
- Public registration cannot create platform administrator accounts. Create administrators with `createsuperuser` or through the Django admin.
- Institution and partner dashboards include listing, profile, recommendation, collection, and transaction workflows described above. Admin verification is implemented with the initial policy documented in `docs/system-architecture-and-schema.md`; confirm that policy against the canonical proposal before production use.
- Email address confirmation, rate limiting, and password reset flows are not implemented. AI artifacts are generated locally and are not committed; generate them with the documented training command before expecting trained-model ranking. Synthetic-data metrics are not production validation.
