# System Architecture and Initial Schema

## Runtime architecture

- Django 5.2 is the application framework and ORM. `AUTH_USER_MODEL` points to the email-based `accounts.User` model.
- PostgreSQL is required and selected through `DATABASE_URL` or the `DB_*` environment variables; `psycopg` is the PostgreSQL driver. Django raises a configuration error if neither connection method is configured.
- The `accounts` app owns authentication, organization profiles, role checks, listings, collections, and transaction records. Schema changes are versioned in Django migrations.
- Django admin is the initial platform management interface. Staff can review and manage organization accounts and inspect domain records.

## Model contract

| Model | Purpose and relationships |
| --- | --- |
| `User` | Unique normalized email, password hash, role, contact details, verification state, and reviewer/verifier actor and timestamps. Public roles are institution and recycling partner; platform admins are provisioned separately. |
| `EducationalInstitution` | One-to-one organization details for an institution account. Owns its paper listings. |
| `RecyclingProfile` | One-to-one partner capabilities, accepted paper types, service area, monthly capacity, and collection availability. |
| `PaperListing` | Institution-owned category, estimated quantity in kg, pickup address/city/country, preferred collection start/end dates, optional supporting photo, and listing status. Quantity must be positive and the date window ordered. |
| `Collection` | A partner request against a paper listing, with request, schedule, completion, and cancellation status/timestamps. At most one requested, accepted, or scheduled collection can exist for a listing at a time. |
| `Transaction` | One record per collection, storing transferred quantity and completion/reference details. Payment processing is not modeled. |

Operational foreign keys use `PROTECT` where deleting an organization or listing would invalidate records. Profile rows cascade with their account. Account email uniqueness is case-insensitive.

## FR-01 and FR-02 behavior

- Registration accepts only the two public organization roles. In one database transaction it creates the account and its matching profile, with status `pending`.
- Pending and rejected users may authenticate to view the account review status. Only verified users can access institution and partner dashboard views. The role and verification checks run on the server.
- Django staff manage accounts in `/admin/`. The account list supports filtering by role/status and bulk verify, reject, and suspend actions. Verification records the verifier and timestamp; all three review actions record the latest reviewer and review timestamp. Verification status is read-only in the admin form so staff use these actions and preserve the audit fields.
- Initial FR-02 policy: pending and rejected users may sign in to view their status; only verified, active users can use organization workflows; suspension disables sign-in. This is the implemented initial policy because the detailed FR-02 policy is not included in the available proposal text. One organization maps to one account in this milestone; shared organization membership is future schema work.
- Institution listing routes are scoped to the current user's institution profile. Institutions can save a complete listing as a draft or publish it; draft and available listings can be edited or withdrawn before collection activity. Create and edit validate category, positive estimated kilograms, required pickup details, date order, and an optional image limited to 5 MB. Withdrawn listings remain stored for history.
- Listing photos are served through an authenticated owner-only view and are not exposed through a public media route. Photos are supporting evidence only; image recognition and quantity estimation are outside the proposal's initial scope.
- A listing cannot be edited or withdrawn after any non-cancelled collection record exists. A rejected request leaves the listing available for partner reselection, while edit and withdrawal remain locked; cancelled collection records do not lock the listing. Collection selection and tracking flows are implemented in later milestones.

Apply the schema with `python manage.py migrate`. Configure PostgreSQL before running the command when the target database should be PostgreSQL.
