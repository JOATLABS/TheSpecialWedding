# Firebase Messaging Operations Runbook

This runbook documents operational tasks for Firebase resources supporting the
messaging platform. It is designed to complement the implementation guidance in
`firebase_messaging_plan.md` and provide concrete procedures for on-call and
platform teams.

## Service Account Key Rotation

1. **Inventory the accounts** – Two dedicated service accounts must exist:
   - `messaging-admin@<project-id>.iam.gserviceaccount.com` for application
     runtime access.
   - `messaging-automation@<project-id>.iam.gserviceaccount.com` for background
     Gmail synchronisation and archival jobs.
2. **Schedule rotation** – Keys should be rotated every 90 days or immediately
   after any suspected compromise. Capture the rotation cadence in the security
   calendar and ticketing system.
3. **Create new key material** – Use `gcloud iam service-accounts keys create` to
   generate a new key for the account that requires rotation. Store the key in
   the central secrets manager with an expiration note.
4. **Update FastAPI configuration** – Inject the new key JSON via the
   configuration pipeline (`FIREBASE_SERVICE_ACCOUNT_JSON` or individual
   environment variables). Redeploy the FastAPI service to pick up the new key.
5. **Refresh GitHub Actions secrets** – Update CI/CD secrets that reference the
   service account JSON. Trigger a CI dry run to confirm the emulator can still
   initialise the Firebase Admin SDK.
6. **Decommission old keys** – Once the deployment is verified, delete the old
   key material with `gcloud iam service-accounts keys delete` and update the
   runbook log.

## Emulator and Initialization Health Checks

- **Local validation** – Run `npx firebase emulators:start --only firestore`
  locally and execute `pytest tests/backend/test_firestore_repository_emulator.py`
  to verify the repository interacts with the emulator and respects schema
  expectations.
- **CI validation** – The GitHub Actions workflow runs `firebase
  emulators:exec` against the same test suite to surface initialisation issues
  whenever messaging code changes.
- **Troubleshooting** – If tests fail to connect, confirm that
  `FIRESTORE_EMULATOR_HOST` is present and that no stale background emulator
  process occupies port `8080`.

## Failure Recovery

1. **Admin SDK initialisation failures** – Investigate logs for
   `FirebaseInitializationError`. Typical causes are malformed service account
   JSON or revoked keys. Validate secrets via the `firebase-admin` Python REPL:
   `python -m app.services.firebase.client`.
2. **Security rule violations** – If clients report permission errors, deploy
   the latest `firebase/firestore.rules` using `firebase deploy --only
   firestore:rules` and re-run the rules test suite (`npm run test --
   tests/firebase/firestore.rules.test.ts`).
3. **Firestore data corruption** – Use the scheduled exports (see disaster
   recovery documentation) to restore affected collections. Replay conversation
   mutations through the messaging repository to maintain domain invariants.
4. **Gmail sync degradation** – Re-authenticate the planner via the FastAPI
   integration endpoints, confirm the automation service account still holds the
   correct OAuth scopes, and monitor retry queues. Escalate to Google support if
   the Gmail API reports sustained 5xx errors.

## Documentation Hygiene

- Record every rotation, deployment of rules, and incident response in the
  shared operations journal.
- Keep emulator host and project identifiers aligned with
  `firebase.json` to avoid drift between local environments and CI.
- Review this runbook quarterly alongside the messaging service retro to ensure
  procedures stay in sync with implementation changes.
