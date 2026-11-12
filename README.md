# PaperLoop

PaperLoop is a Django application for educational institutions and recycling/collection partners to coordinate bulk paper recycling. This initial implementation covers **FR-01: User Registration and Role-Based Access Control**.

## Included in FR-01

- Organization registration as an Educational Institution or Recycling/Collection Partner.
- Email-based authentication and secure password hashing through Django authentication.
- A custom account model with organization name, contact person, phone, and role.
- Separate institution and partner dashboards, protected by server-side role checks.
- Responsive registration and sign-in pages using Bootstrap 5.3.9 with PaperLoop styles.
- Django administration for platform staff and superusers.
- SQLite for local development and PostgreSQL configuration through environment variables.

Organization verification and activation are intentionally separate and belong to FR-02. This initial registration flow creates active accounts; align activation behavior with FR-02 before implementing verification.

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set the values you need. The project loads this local file automatically; operating-system environment variables take precedence. Keep `.env` private and use a strong `DJANGO_SECRET_KEY` outside local development.
4. Apply migrations: `python manage.py migrate`.
5. Create a platform administrator: `python manage.py createsuperuser`.
6. Start the development server: `python manage.py runserver`.
7. Open `/accounts/register/` to register an institution or partner, `/accounts/login/` to sign in, or `/admin/` for the Django administration site.

Set `DATABASE_URL` to a PostgreSQL connection string, or set `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and optional `DB_SSLMODE`. A URL can include `?sslmode=require` when your database provider requires TLS. If `DATABASE_URL` and `DB_NAME` are both empty, the app uses local SQLite.

### Project-local PostgreSQL server

This workspace has a PostgreSQL 18.6 development server and database in the ignored `.local/` directory. Its connection settings and generated development credentials are in the ignored `.env` file. Keep both directories private; neither is committed to Git.

Start PostgreSQL from PowerShell before starting Django:

```powershell
.\.local\pgsql\bin\pg_ctl.exe --pgdata=".local/postgres-data" --log=".local/postgres-server.log" --options="-h 127.0.0.1 -p 5432" --wait --timeout=30 start
python manage.py runserver 127.0.0.1:8000
```

Stop PostgreSQL when you are finished:

```powershell
.\.local\pgsql\bin\pg_ctl.exe --pgdata=".local/postgres-data" --mode=fast stop
```

## Security and scope notes

- `DJANGO_DEBUG` defaults to `true` for local development. Set it to `false`, use a strong secret, configure allowed hosts, HTTPS, and deployment-specific security settings before exposing the application.
- Public registration cannot create platform administrator accounts. Create administrators with `createsuperuser` or through the Django admin.
- Partner and institution dashboards are placeholders for future FR modules; their distinct access boundaries are already enforced server-side.
- This is a prototype foundation. Email verification, rate limiting, organization verification, password reset flows, and FR-02 activation policy are not part of FR-01.
