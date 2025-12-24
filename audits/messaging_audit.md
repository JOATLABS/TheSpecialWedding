# Messaging API Audit

> **Status:** ARCHIVED - Legacy MongoDB implementation has been removed.
> **Current Implementation:** See `messaging_phase0_audit.md` for the active Firestore-based messaging system.

## Historical Context

This document originally covered the MongoDB-backed messaging implementation that was deprecated in favor of the Firestore-based system. The legacy `app/services/messaging_service.py` file has been removed from the codebase.

## Migration Summary

The messaging system was migrated from MongoDB to Firestore to provide:
- Real-time synchronization via Firestore listeners
- Simplified security rules aligned with Firebase Authentication
- Better integration with the existing Firebase infrastructure
- Reduced operational overhead for the messaging subsystem

## Current Architecture

For the current messaging implementation details, refer to:
- `audits/messaging_phase0_audit.md` - Phase 0 audit and implementation status
- `docs/messaging/firebase_messaging_plan.md` - Full roadmap and technical specifications
- `app/services/messaging/` - Firestore-based repository and service layer
- `app/api/messaging.py` - FastAPI router with auth enforcement
- `app/models/messaging.py` - Pydantic models with validation

## Original Findings (Historical)

The following issues were identified in the legacy MongoDB implementation and have been addressed by the migration:

1. **Conversation identifier typed inconsistently** - Resolved: Firestore uses string document IDs consistently
2. **Service bypasses conversation existence checks** - Resolved: Repository validates conversation existence
3. **Participants compared against email strings** - Resolved: Participant IDs are consistently handled
4. **Messaging service instantiated as module singleton** - Resolved: Service uses dependency injection
5. **Missing payload validation and sanitisation** - Resolved: Pydantic models enforce constraints
6. **Limited error observability** - Resolved: Structured logging added to repository layer
