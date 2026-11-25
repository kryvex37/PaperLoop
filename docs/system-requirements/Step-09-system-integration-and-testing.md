# Step 9: System Integration & Comprehensive Testing

## Scope

Step 9 verifies that Django's workflows use PostgreSQL, saved PyTorch model artifacts, and protected media storage together. It also runs the role-based functional suite for FR-01 through FR-12.

## Integration coverage

- Django's AI recommendation, forecasting, and bulk aggregation services load the trained forecasting, recycler-ranking, and aggregation artifacts from `ml_engine/artifacts/`. Pilot artifacts and generated datasets are local runtime outputs under Git-ignored paths; `generate_pilot_data` and `train_ai_models` reproduce them.
- Institution paper photos are stored under `MEDIA_ROOT`. The listing-photo view serves them only to the owning institution, denies a different institution, and redirects anonymous users to sign-in. The test uses a temporary media root and generated image, so it leaves no uploaded test file in the project.
- `accounts/test_step9_integration.py` adds six acceptance tests covering registration for both organization roles, duplicate registration, admin verify/reject/suspend actions, listing create/edit/withdraw, category/date validation, and media persistence/access.
- Existing tests cover recycler profiles and discovery (FR-06/08), ranking and explanations (FR-07), collection decisions/status and final quantity (FR-09/10), and transaction history/digital impact records (FR-11/12).

## Verification results

The complete suite ran against the configured PostgreSQL test database using its existing test database:

```text
python manage.py test --verbosity 1 --keepdb
Found 67 test(s).
Ran 67 tests in 199.966s
OK
System check identified no issues (0 silenced).
```

`--keepdb` avoids deleting an existing local test database. PostgreSQL had already been created and migrated for this project. The six Step 9 tests also passed as a focused run, including the temporary-file media test.

The Django Client smoke check used PostgreSQL pilot records and returned HTTP 200 for the Admin, Institution, Recycler, AI recommendations, and Bulk aggregation pages. It rendered four-week forecasting results with source `pytorch`, one ranked candidate out of one, and one bulk bundle with score `0.6922`.

## Requirement status

All FR-01–FR-12 automated tests pass in the current local integration suite. This verifies application behavior and pipeline execution on synthetic/pilot data; it does not establish model quality on real-world outcomes. Step 9 is complete for local integration and verification. Production hosting, deployment security configuration, and real-data pilot evaluation remain release-readiness work.
