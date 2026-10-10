"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { ErrorNote } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { OkNote, useSupplier } from "@/components/supplier/SupplierShell";
import { SUPPLIER } from "@/lib/constants";
import { fill, setSupplierId, supplierApi } from "@/lib/supplier";
import { useIsAuthenticated } from "@/lib/useAuth";

const J = SUPPLIER.join;

// Accepting an invitation (the link in the e-mail): signed in with the
// invited address, the person joins the supplier with the invited role.
export function JoinPanel() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const authed = useIsAuthenticated();
  const { reload } = useSupplier();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [joined, setJoined] = useState("");

  if (!token) return <p className="text-text-secondary">{J.missing}</p>;
  if (authed === null) return <p className="text-text-muted">…</p>;
  if (!authed) {
    const next = encodeURIComponent(`/supplier/join/?token=${token}`);
    return (
      <div className="space-y-4">
        <p className="text-text-secondary">{SUPPLIER.signup.signedOut}</p>
        <div className="flex flex-wrap gap-3">
          <Button href={`/signup/?next=${next}`}>{SUPPLIER.signup.createAccount}</Button>
          <Button href={`/login/?next=${next}`} variant="secondary">
            {SUPPLIER.signup.signIn}
          </Button>
        </div>
      </div>
    );
  }

  async function accept() {
    setBusy(true);
    setError("");
    try {
      const res = await supplierApi.acceptInvite(token);
      setSupplierId(res.supplier_id);
      await reload();
      setJoined(fill(J.done, { name: res.name ?? "" }));
      window.location.href = "/supplier/";
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {joined ? <OkNote message={joined} /> : null}
      {error && <ErrorNote message={error} />}
      <Button onClick={() => void accept()} disabled={busy}>
        {busy ? J.accepting : J.accept}
      </Button>
    </div>
  );
}
