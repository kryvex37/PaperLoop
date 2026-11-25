# Step 8: Frontend UI/UX Polish and Dashboard Integration

## Implementation status

Bootstrap-based templates are used by the institution and recycler dashboards, and the admin landing page now presents model operations in responsive Bootstrap cards. This documents template implementation; browser-level visual review remains outstanding because no browser renderer is available in the development environment.

### Dashboard workflows

- **Admin (`/admin/`)**: Django admin branding and account verification, rejection, and suspension actions are configured. The landing page groups authorized model operations into responsive cards and retains Django's permission-aware links.
- **Institution (`/accounts/institution/`)**: Listing metrics and actions, forecast summary, recycling records, bulk aggregation, and partner directory links are present.
- **Partner (`/accounts/partner/`)**: Profile/capacity summary and collection request actions are present.

### Recommendation workflows

- Partner recommendation cards show paper category, available capacity, service-area fit, verification status, marketplace history, and a collection request form. Ranking scores are labeled by source: model output on a 0–1 scale, or the rules-based service-area score on a 0–100 scale.
- The page distinguishes eligibility-based recommendations from trained-model ranking. It shows a model score only when the trained ranker actually produced one.
- Bulk aggregation cards show bundle participants and available distance, transport, and capacity factors.

### Verification status

The FR-03/FR-05 listing and FR-09/FR-10 collection workflows use `TransactionTestCase` so requests run under PostgreSQL autocommit behavior. The full suite passes all 87 tests, including assertions for the Bootstrap admin dashboard and recommendation card output. Browser-level visual review remains outstanding because no local browser renderer is installed. See [the master roadmap](../project-roadmap.md).
