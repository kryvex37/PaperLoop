# FR-03 to FR-05: Institution Paper Listings

## Source and scope

This implementation follows the Step 3 request and the functional requirements in the PaperLoop project proposal. The proposal defines the capabilities; the user's Step 3 task explicitly assigns implementation of those capabilities and the Bootstrap institution dashboard.

## Requirements

- **FR-03 — Paper-waste listing management:** verified educational institutions can create and update their own listings and withdraw draft or available listings. Listings are retained after withdrawal. A listing cannot be edited or withdrawn after a non-cancelled collection record exists.
- **FR-04 — Paper category and estimated quantity:** each listing has one paper category and an estimated quantity greater than zero, recorded in kilograms. The initial category choices are office paper, books and notebooks, newspapers and magazines, cardboard, mixed paper, and other paper. Selecting “Other” requires a description.
- **FR-05 — Location, collection period, and photo:** each listing requires pickup address, city/town, and country. Preferred collection start and end dates are optional; when both are provided, end must not precede start. One optional image up to 5 MB can be uploaded as supporting information.

## Access and data handling

The institution dashboard supports saving a listing as a draft, publishing it, editing it, and withdrawing it. A rejected collection request leaves the listing available for another partner selection, but its non-cancelled collection record locks edits and withdrawal. A cancelled collection record does not lock the listing.

All create, edit, withdraw, dashboard, and photo requests require an authenticated, verified institution role. Queries bind listing operations and photo access to the signed-in institution. Uploaded photos use Django image validation and are returned through an authenticated owner-only endpoint; photo-based recognition is outside scope.

The initial category set is a product vocabulary assumption because the proposal does not enumerate categories. The list can be updated as the marketplace's paper taxonomy is confirmed.
