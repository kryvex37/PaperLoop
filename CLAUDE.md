# PaperLoop Project Brief

## Product

PaperLoop is a digital bulk paper recycling platform for educational institutions. It helps schools, colleges, universities, coaching centers, libraries, and examination centers manage paper waste and connect with suitable recycling and collection partners.

Institutions may generate bulk quantities of examination scripts, question papers, assignments, outdated administrative documents, notebooks, books, photocopies, and other paper materials. Today, these materials may be handled through informal collection, individual scrap dealers, general waste collectors, or conventional disposal channels. This can make it difficult to find reliable partners, compare prices, coordinate bulk collection, track recycled quantities, and maintain dependable records.

PaperLoop focuses on bulk paper from educational institutions. It will support institution and recycler participation, paper availability planning, suitable recycling/collection recommendations, collection coordination, quantity tracking, and reliable digital records.

## Product goals

- Help educational institutions find and coordinate with reliable recycling partners for bulk paper.
- Make available paper quantities and collection needs easier to represent and manage.
- Support competitive and transparent recycling options, subject to product decisions about how offers and prices work.
- Use AI to predict paper availability and recommend suitable recycling or collection options.
- Track collection and recycled quantities and retain dependable transaction records.

## Domain guidance

- Design for institutional bulk quantities and recurring or scheduled availability, rather than assuming individual household recycling.
- Treat institutions, recyclers/collection partners, and platform administrators as distinct actors where the confirmed requirements call for them. Coordinate exact roles and permissions with the backend architect.
- Keep paper listings, partner recommendations, collection requests, fulfillment, quantities, and digital records connected through explicit lifecycle states and auditable events.
- AI predictions and recommendations support decision-making; they must not silently make binding price, acceptance, or collection commitments.
- Protect sensitive institutional material. In particular, examination scripts and administrative documents may contain confidential information. Collect only necessary data and do not assume the platform should inspect or store document contents.

## Decisions that remain open until requirements confirm them

Do not invent pricing or bidding rules, accepted paper grades, minimum bulk quantities, service areas, recycler verification standards, payment handling, collection SLAs, document destruction requirements, data retention periods, or regulatory obligations. Record assumptions and seek clarification when an open decision affects implementation.

## Shared agent instructions

All project agents must read and follow this brief before making product or architecture decisions. Inspect the repository for newer user-approved requirements and implementation conventions. Keep interfaces and terminology consistent across backend, marketplace workflows, AI/ML, frontend, and QA/DevOps. Update this brief only when the user confirms a product-level decision.
