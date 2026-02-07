## 2024-05-22 - Authentication Timing Attack Mitigation
**Vulnerability:** User enumeration was possible via timing attacks on the login endpoint. Invalid emails returned ~0.0001s, while valid emails with invalid passwords returned ~0.3s (bcrypt verification time).
**Learning:** Even with async/await, computational delays like bcrypt are blocking or at least significant enough to be measurable. The `AuthService` logic allowed early exit for non-existent users.
**Prevention:** Always perform a dummy password verification when a user is not found or has no password set. Added `DUMMY_PASSWORD_HASH` and updated `AuthService.authenticate_user` to ensure constant-time(ish) responses for all failure modes.
