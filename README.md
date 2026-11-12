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
3. Copy `.env.example` to `.env` and provide a strong `DJANGO_SECRET_KEY` for any shared environment. Export the variables in your shell; Django does not load `.env` files automatically.
4. Apply migrations: `python manage.py migrate`.
5. Create a platform administrator: `python manage.py createsuperuser`.
6. Start the development server: `python manage.py runserver`.
7. Open `/accounts/register/` to register an institution or partner, `/accounts/login/` to sign in, or `/admin/` for the Django administration site.

When `DB_NAME` is set, the app uses PostgreSQL and reads `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`. With `DB_NAME` unset, it uses the local SQLite database.

## Security and scope notes

- `DJANGO_DEBUG` defaults to `true` for local development. Set it to `false`, use a strong secret, configure allowed hosts, HTTPS, and deployment-specific security settings before exposing the application.
- Public registration cannot create platform administrator accounts. Create administrators with `createsuperuser` or through the Django admin.
- Partner and institution dashboards are placeholders for future FR modules; their distinct access boundaries are already enforced server-side.
- This is a prototype foundation. Email verification, rate limiting, organization verification, password reset flows, and FR-02 activation policy are not part of FR-01.
