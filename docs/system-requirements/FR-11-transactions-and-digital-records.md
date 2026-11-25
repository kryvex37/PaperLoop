# FR-11 & FR-12: Transactions & Digital Recycling Records

## Scope & Implementation Overview

This implementation delivers **Step 7** of the PaperLoop platform based on the system proposal:

- **FR-11 — Transaction History Management:** Comprehensive audit history and listing of completed paper collections, scoped securely by actor (Educational Institutions see their recycled volumes; Recycling Partners see their processed collections; Admins see system-wide transactions).
- **FR-12 — Digital Recycling Records & Environmental Impact Summaries:** Verifiable circular economy certificates and real-time environmental impact calculations derived from EPA and Environmental Paper Network benchmarks.

---

## 1. Scientific Environmental Impact Engine (FR-12)

Implemented in [`accounts.impact.calculate_impact_metrics`](file:///c:/Users/sajed/PaperLoop/accounts/impact.py), converting verified paper weights into ecological savings:

| Metric | Conservation Ratio (per 1,000 kg / 1 MT paper) |
| --- | --- |
| **Trees Saved** | ~17.0 trees saved |
| **Water Conserved** | ~26,000 Liters |
| **Electricity Saved** | ~4,000 kWh |
| **CO₂e Emissions Avoided** | ~1,500 kg CO₂ equivalent |
| **Landfill Space Conserved** | ~3.0 cubic meters |

---

## 2. Completed Transaction Records & Endpoints (FR-11)

When a recycling partner completes a collection via `accounts:partner_complete_collection`, the system:

1. Locks the collection and sets status to `COLLECTED` with `collected_at = timezone.now()`.
2. Sets `PaperListing.status = COMPLETED`.
3. Creates or updates the associated `Transaction` record with a unique immutable reference: `TXN-YYYYMMDD-XXXXX`.
4. Attaches environmental impact indicators accessible via `transaction.impact_metrics`.

### Key Endpoints and Routes

- **Transaction History:** `accounts:transaction_history` (`/accounts/transactions/`)
  - Displays cumulative weight and total ecological savings.
  - Role-scoped table with individual transaction links.
- **Transaction Details:** `accounts:transaction_detail` (`/accounts/transactions/<id>/`)
  - Full audit trail, linking institution, partner, pickup address, and net weight.
- **Formal Digital Certificate:** `accounts:digital_record` (`/accounts/transactions/<id>/record/`)
  - Print and PDF-ready digital certificate with platform verification and badges.

---

## 3. Automated Verification

- Transaction workflow coverage passes in the 67-test PostgreSQL-backed suite; see [Step 9 integration and testing](Step-09-system-integration-and-testing.md) for the final run output.
- Specific test suite: [`accounts.test_transactions_workflow.py`](file:///c:/Users/sajed/PaperLoop/accounts/test_transactions_workflow.py).
