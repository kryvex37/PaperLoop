# FR-01 - User Registration and Role-Based Access Control

## Requirement

**ID:** FR-01  
**Priority:** Must have  
**Actors:** Educational institution user; recycling/collection partner user

**The system shall allow educational institutions and recycling/collection partners to create accounts and shall provide role-based access according to their user type.**

## Description

PaperLoop shall let a representative register an organization under one of two account types: **Educational Institution** or **Recycling/Collection Partner**. The selected type shall determine the user's role and the system capabilities available to that account. The system shall enforce role permissions on the server for protected pages and actions, and shall restrict each account to data it is authorized to access.

The platform administrator and institution administrator are stakeholders in the proposal. Their account provisioning and administrative permissions are not defined by this requirement; they must be specified separately and coordinated with FR-02 (Organization Verification and Management).

## Preconditions

- The user can access PaperLoop's registration page.
- The user is not authenticated with an existing session.

## Main flow

1. The user chooses **Educational Institution** or **Recycling/Collection Partner** as the organization type.
2. The user provides the registration information required by the system and submits the form.
3. The system validates the submitted information and creates the account with the selected user type.
4. The system confirms successful registration and associates the account with the selected role.
5. On authentication, the system grants only the permissions associated with that role and limits access to authorized data and actions.

## Functional details

- The registration form shall present the two organization types as distinct choices.
- The system shall reject a submission if required fields are missing or invalid, and shall identify the fields that need correction.
- The system shall prevent duplicate account identifiers according to the identifier policy configured for the project.
- The assigned role shall be stored and checked by the server; changing a client-side value or URL shall not grant additional permissions.
- Institution users shall be authorized for institution-facing functions. Partner users shall be authorized for partner-facing functions. Exact function lists shall be defined by the relevant functional requirements and interface contracts.
- A user shall not be able to view or modify another organization's restricted account or operational data unless an explicit permission allows it.
- Authentication credentials shall be stored using secure password hashing, consistent with the proposal's security requirements.
- Registration shall not itself verify an organization or activate/deactivate it. Those lifecycle actions belong to FR-02. Access available before verification or activation must follow the status policy defined with FR-02.

## Acceptance criteria

1. Given a visitor selects **Educational Institution** and submits valid required information, when registration succeeds, then the created account has the Educational Institution role.
2. Given a visitor selects **Recycling/Collection Partner** and submits valid required information, when registration succeeds, then the created account has the Recycling/Collection Partner role.
3. Given a visitor omits a required field or submits invalid data, when registration is submitted, then the account is not created and the system identifies the validation error.
4. Given an account is assigned one organization role, when it requests a protected function reserved for the other organization role, then the server denies the request and does not disclose restricted data.
5. Given an account requests data belonging to another organization without permission, when the request is processed, then the system denies access.
6. Given a registered user authenticates, when the user opens the application, then the system exposes only pages and actions permitted for that user's role and account status.
7. Given a registration uses an account identifier that already exists, when the submission is processed, then the system does not create a duplicate account and returns a clear validation message.

## Dependencies and boundary

- **FR-02:** Defines organization verification, management, activation, and deactivation. The access behavior for unverified or inactive accounts must be aligned with FR-02.
- The specific registration fields, account identifier policy, and exact role-permission matrix require confirmation during detailed design. They are intentionally not fixed here because the proposal does not specify them.
- This requirement covers account creation and role-based authorization. Paper listings, recycler profiles, collection transactions, and other role-specific workflows are specified by their respective requirements.

## Source

Derived from the PaperLoop project proposal, Section 2 (System Requirements, FR-01), Section 1.5 (Stakeholders), and the Security non-functional requirements.
