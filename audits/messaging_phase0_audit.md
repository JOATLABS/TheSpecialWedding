# Messaging Phase 0 Audit

_Last updated: 2025-10-28T23:30:14Z_

## Branch synchronisation
- Local `messaging` branch is currently at commit `be9c2a4` ("Document read receipt completion and stabilize emulator tooling"), with no Git remotes configured in this workspace to fetch additional updates.

## Phase 0 guardrail verification

### Roadmap and deliverable tracking
- `docs/messaging/firebase_messaging_plan.md` records Phase 0 scope, the completed checklist, and supporting artefacts that were delivered to close the milestone.

### Firebase configuration ownership
- `app/services/firebase/client.py` centralises Firebase Admin SDK initialisation behind `Settings.is_firebase_configured()` and surfaces consistent errors when credentials are missing or invalid.
- `app/services/firebase/auth.py` wraps custom token minting against the cached Admin SDK app so downstream services can rely on backend-owned credentials.

### Firestore security posture
- Firestore security rules enforce participant-only access, wedding scoping, and channel-based email restrictions.
- Security rules are covered by `tests/firebase/firestore.rules.test.ts`, which exercises participant access, wedding membership, email channel restrictions, and sender identity requirements.

### Repository and service orchestration
- `app/services/messaging/repository.py` persists conversations, participants, and messages in Firestore with pagination, read-receipt updates, and defensive logging.
- `app/services/messaging/service.py` exposes async-safe adapters around the repository and translates repository exceptions into HTTP errors for the FastAPI layer.
- The FastAPI router in `app/api/messaging.py` injects the messaging service, enforces participant membership, and normalises request payloads before invoking the service.

### Data validation and test coverage
- `app/models/messaging.py` constrains message bodies, participant metadata, and read receipt payloads via Pydantic validators.
- `tests/backend/test_messaging_service.py` verifies body trimming, validation failures, and service-to-repository orchestration.
- `tests/backend/test_firestore_repository_emulator.py` runs against the Firestore emulator to confirm repository CRUD behaviour and read-receipt monotonicity.

### Continuous integration safety nets
- `.github/workflows/ci.yml` runs Firebase emulator-backed integration tests and unit coverage for the messaging service after Node tests succeed, ensuring Phase 0 guardrails stay enforced in CI.

### Operational readiness
- `docs/messaging/firebase_operations_runbook.md` documents service-account rotation, emulator validation, incident recovery, and runbook hygiene for Firebase resources.

## Additional observations
- `app/services/messaging_service.py` (the legacy Mongo-backed implementation) remains in the repository but is unused by the current Firestore-driven stack; consider removing or archiving it to avoid confusion for new contributors.
- Phase 1 follow-ups (Firebase custom token endpoints, audit logging, and conversation indexing) remain outstanding per the roadmap and should be prioritised after Phase 0 sign-off.
