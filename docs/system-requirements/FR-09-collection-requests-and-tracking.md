# FR-09 & FR-10: Collection Requests and Status Tracking

## Source and scope

This implementation delivers **Step 6** of the PaperLoop platform based on the project proposal:
- **FR-09 — Collection Request and Status Management:** The system allows educational institutions to submit collection requests, while collection partners can accept or reject requests and update the collection status through explicit lifecycle stages.
- **FR-10 — Collection Quantity Tracking:** The system records the estimated quantity at request time and the final collected quantity upon completion for each collection.

## Collection Lifecycle & State Machine

1. **Submission (`requested`):**
   - An educational institution selects a recommended recycling partner for an active listing.
   - The system creates a `Collection` with `status = REQUESTED` and captures `estimated_quantity_kg = listing.quantity_kg`.
   - The associated `PaperListing` transitions to `RESERVED`.
   - The institution can cancel a pending request, which resets the listing status back to `AVAILABLE`.

2. **Review & Decision:**
   - **Accept (`accepted`):** The assigned partner accepts the incoming request with optional preparatory notes.
   - **Reject (`rejected`):** The assigned partner rejects the request with a mandatory `rejection_reason`. The associated `PaperListing` is released back to `AVAILABLE` so the institution can request another partner.

3. **Scheduling (`scheduled`):**
   - The partner sets a validated future pickup date and time (`scheduled_for`) and optional logistics instructions.

4. **Completion & Final Quantity Recording (`collected`):**
   - Upon pickup and weighing, the partner records the verified `final_collected_quantity_kg` (must be > 0) and optional completion notes.
   - The collection transitions to `COLLECTED` with `collected_at = timezone.now()`.
   - The `PaperListing` transitions to `COMPLETED`.
   - An associated `Transaction` record is automatically initialized with the final quantity and unique reference code (`TXN-YYYYMMDD-XXXXX`) for digital record generation (FR-11/12).

## Quantity Tracking (FR-10)

- Every collection stores both `estimated_quantity_kg` and `final_collected_quantity_kg`.
- Database check constraints enforce that both quantities, when present, must be strictly greater than zero (`> 0`).
- The collection detail view and dashboards surface comparison metrics between estimated and final weights.

## Access Control and Endpoints

- All collection actions require role verification. Only the owning institution or the assigned partner can access `collection_detail` or perform their respective lifecycle transitions.
- Key endpoints:
  - `accounts:collection_detail` (`/accounts/collections/<id>/`)
  - `accounts:partner_accept_collection` (`/accounts/collections/<id>/accept/`)
  - `accounts:partner_reject_collection` (`/accounts/collections/<id>/reject/`)
  - `accounts:partner_schedule_collection` (`/accounts/collections/<id>/schedule/`)
  - `accounts:partner_complete_collection` (`/accounts/collections/<id>/complete/`)
  - `accounts:institution_cancel_collection` (`/accounts/collections/<id>/cancel/`)
