"""Webhooks (PF12): endpoints registered per account, events signed per the
Standard Webhooks specification, retried on its schedule, a delivery log,
re-send, and endpoints disabled after five days of failures (with an e-mail).

* `models`: endpoints (secrets sealed with Fernet), events (kept 30 days),
  deliveries (one row per attempt), the 30 s debounce of pushed operations.
* `signing`: `whsec_` secrets, `v1,<base64 HMAC-SHA256 of id.timestamp.body>`.
* `urls`: https only, public addresses only (checked again at each delivery).
* `events`: the event types and `emit`, which writes an event and one pending
  delivery per subscribed endpoint of each account.
* `observe`: where events come from, without touching the features that cause
  them: PF4's push hook (debounced), and a session observer that sees a job
  end, a share go live, a version named, a member invited, an order change
  state and a feed run end, and emits after the commit.
* `delivery`: sends due deliveries; `jobs`: deliver (5 s), the daily visits
  digest (00:10 UTC), disable (1 h) and purge (24 h).
"""
