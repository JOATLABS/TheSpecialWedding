# Messaging API Audit

## Overview
The current messaging stack introduces `MessagingService`, Pydantic models, and a FastAPI router to persist
conversation messages in MongoDB. While the endpoint enforces that the caller participates in the target
conversation, the implementation leaves several correctness, safety, and observability gaps that should be
addressed before promoting the feature to production.

## Findings

### 1. Conversation identifier typed inconsistently
- `MessagingService.get_conversation` requires a valid `ObjectId` and fetches the conversation by `_id`.
- `MessagingService.send_message` stores the `conversation_id` exactly as received (a stringified ObjectId) in the
  message document, rather than converting it back to an `ObjectId` or storing a distinct UUID.
- Any downstream query that tries to fetch messages using the actual `_id` value (as an `ObjectId`) will not match
the persisted `str` value, fragmenting referential integrity.
- **Recommendation:** normalize identifiers before persistence (e.g., convert to `ObjectId`) and keep the Pydantic
  model types aligned with the stored representation.

### 2. Service bypasses conversation existence checks
- `MessagingService.send_message` does not verify the referenced conversation. The router currently performs this
  check, but any other caller of the service (tests, background tasks, future endpoints) could insert dangling
  messages for conversations that do not exist or belong to a different wedding.
- **Recommendation:** allow `send_message` to accept a `Conversation` instance (or look it up internally) so that
  referential checks are enforced inside the service boundary.

### 3. Participants compared against email strings
- Conversation participants are modelled as a list of `str` values. The endpoint compares `current_user.email`
  against this list, assuming every participant entry is the user’s email address.
- If the data model eventually holds Mongo `_id` values or guest IDs (which is common for relational consistency),
  the authorization guard will silently reject legitimate users.
- **Recommendation:** document and enforce a single identifier type for conversation participants, or introduce an
  adapter layer that can reconcile `AuthUser` identities with stored participant IDs.

### 4. Messaging service instantiated as a module singleton
- `service = MessagingService()` executes at import time, binding a concrete Mongo connection into the router.
- This pattern complicates dependency injection for unit tests, makes it harder to swap in fakes, and prevents
  configuration tweaks per request.
- **Recommendation:** expose the service through a FastAPI dependency (e.g., `get_messaging_service`) so tests and
  other contexts can override the implementation.

### 5. Missing payload validation and sanitisation
- `SendMessageRequest` only requires a `body` field without length constraints or HTML/emoji handling.
- The API will accept arbitrarily large payloads, increasing the risk of resource exhaustion and inconsistent
  client behaviour.
- **Recommendation:** enforce maximum lengths (aligned with product requirements), strip disallowed markup, and
  reject empty/whitespace-only messages at the schema layer.

### 6. Limited error observability
- The service raises `HTTPException` directly from the data access layer, coupling persistence with HTTP semantics
  and constraining logging.
- No telemetry or logging is emitted when key failure modes occur (e.g., `InvalidId`, missing conversations,
  Mongo write failures), making operational debugging harder.
- **Recommendation:** translate database errors into domain exceptions in the service, then map them to HTTP errors
  inside the API router while recording structured logs or metrics.

## Next Steps
Prioritise the fixes above before adding more messaging features. Start with identifier normalisation and
service-level validation to keep persisted data internally consistent, then introduce improved validation and
observability to harden the API for production workloads.
