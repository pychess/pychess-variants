# Admin-assisted account erasure

PyChess uses OAuth sign-in and has no local password to check before irreversible
deletion. OAuth consent is not proof of fresh credentials. Self-service erasure is
therefore disabled: `/account/delete` directs owners to `/contact`, and its POST
always rejects deletion. Reversible account closure is still available.

## Admin procedure

1. Independently verify the owner's request and the exact PyChess account being
   erased. A PyChess session, username, screenshot or OAuth consent alone is not
   sufficient ownership verification. Never ask for the owner's password or tokens.
2. Explain that erasure is irreversible and public game archives may remain.
3. With a signed-in, CSRF-protected admin session, POST to
   `/api/admin/users/{username}/delete` with these form fields:

   - `confirm_username`: the exact canonical username (case-sensitive).
   - `understand`: `on`.
   - `verified_request`: `on`, attesting that the owner's request was verified.

The endpoint is deliberately not offered as a one-click moderation action. It
rejects non-admins, protected accounts, missing confirmations and already-erased
accounts. It logs the requesting admin before erasure and completion afterwards.
It disables the target and revokes their sessions and live connections before
running the existing data cleanup, without logging out the admin.

The verification checkbox is an admin attestation, not automated identity proof.
If ownership cannot be independently established, do not invoke erasure.
If cleanup fails, the account stays disabled and the request log remains; inspect
and repair the failure rather than treating the request log as completed erasure.
