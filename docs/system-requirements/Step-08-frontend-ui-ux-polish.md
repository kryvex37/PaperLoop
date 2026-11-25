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

- **Partner Recommendations (`/institution/listings/<id>/recommendations/`):**
  - **Match Score Bar & Pill:** Features visual match percentage indicators (e.g. `98% Match`, `AI Rank Score`).
  - **Structured 4-Factor Reason Cards:**
    1. **Material Grade Match:** Confirms accepted paper categories.
    2. **Capacity Match:** Displays exact available capacity vs. listing load.
    3. **Location & Service Area:** Clear proximity and service coverage indicator.
    4. **Reliability & History:** Partner ratings, fulfillment statistics, and verified credentials.
  - **Explainability Breakdown:** Detailed decision attribution box showing exact positive model factors.
  - **Direct Request Integration:** Inline collection request form with optional pickup notes.
- **AI Bulk Pickup Bundles (`/ai/bulk-aggregation/`):**
  - Visual candidate cards with 4 key metrics: **Truck Utilization %**, **Distance Saved (km)**, **Transport Cost / kg**, and **Optimization Score**.
  - Clear participants breakdown table and decision explanation factors.

---

### 3. Automated Test Verification

The original Step 8 verification passed 61 tests. Step 9 added six registration, admin, listing, and media integration tests; the current 67-test PostgreSQL result is recorded in [Step 9 integration and testing](Step-09-system-integration-and-testing.md).
