# System Architecture and Initial Schema

## Runtime architecture

- Django 5.2 is the application framework and ORM. `AUTH_USER_MODEL` points to the email-based `accounts.User` model.
- PostgreSQL is selected through `DATABASE_URL` or the `DB_*` environment variables; `psycopg` is the PostgreSQL driver. SQLite remains the local fallback when neither connection method is configured.
- The `accounts` app owns authentication, organization profiles, role checks, listings, collections, and transaction records. Schema changes are versioned in Django migrations.
- Django admin is the initial platform management interface. Staff can review and manage organization accounts and inspect domain records.

## Model contract

| Model | Purpose and relationships |
| --- | --- |
| `User` | Unique normalized email, password hash, role, contact details, and verification status/audit fields. Public roles are institution and recycling partner; platform admins are provisioned separately. |
| `EducationalInstitution` | One-to-one organization details for an institution account. Owns its paper listings. |
| `RecyclingProfile` | One-to-one partner capabilities, accepted paper types, service area, monthly capacity, and collection availability. |
| `PaperListing` | Institution-owned category, estimated quantity in kg, pickup address/city/country, preferred collection start/end dates, optional supporting photo, and listing status. Quantity must be positive and the date window ordered. |
| `Collection` | A partner request against a paper listing, with request, schedule, completion, and cancellation status/timestamps. At most one requested, accepted, or scheduled collection can exist for a listing at a time. |
| `Transaction` | One record per collection, storing transferred quantity and completion/reference details. Payment processing is not modeled. |

Operational foreign keys use `PROTECT` where deleting an organization or listing would invalidate records. Profile rows cascade with their account. Account email uniqueness is case-insensitive.

## FR-01 and FR-02 behavior

- Registration accepts only the two public organization roles. In one database transaction it creates the account and its matching profile, with status `pending`.
- Pending and rejected users may authenticate to view the account review status. Only verified users can access institution and partner dashboard views. The role and verification checks run on the server.
- Django staff manage accounts in `/admin/`. The account list supports filtering by role/status and bulk verify, reject, and suspend actions. Verification records the staff user and timestamp; rejection keeps the account for audit; suspension also disables sign-in.
- This is the initial FR-02 policy pending a detailed FR-02 specification. Registration remains enabled for login while pending so users can see status. One organization maps to one account in this milestone; shared organization membership is future schema work.
- Institution listing routes are scoped to the current user's institution profile. Create and edit validate category, positive estimated kilograms, pickup details, date order, and an optional image limited to 5 MB. Withdrawn listings remain stored for history.
- Listing photos are served through an authenticated owner-only view and are not exposed through a public media route. Photos are supporting evidence only; image recognition and quantity estimation are outside the proposal's initial scope.
- A listing cannot be edited or withdrawn after collection activity is recorded. Collection partner discovery and collection request flows belong to later requirements.

Apply the schema with `python manage.py migrate`. Configure PostgreSQL before running the command when the target database should be PostgreSQL.
