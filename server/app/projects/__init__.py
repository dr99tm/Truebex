"""The project service (PF4, contract project-log v1.0): projects as an
append-only log of operations in server order, snapshots, named versions and
restore, members with roles, presence and quotas per tier.

Modules: `service` (records, roles, quotas' callers), `ops` (validation, the
§6.3 push rule, pulls), `waiters` (long-poll wake-ups), `snapshots`,
`versions`, `members`, `presence`, `hooks` (`on_ops_accepted`), `quotas`,
`caller` (who is calling), `jobs` (prune, purge, presence sweep).
"""
