import { Suspense } from "react";

import { InvitationAcceptanceClient } from "./invitation-acceptance-client";

export default function AcceptInvitationPage() {
  return (
    <Suspense fallback={<main style={{ padding: 32 }}>Loading invitation…</main>}>
      <InvitationAcceptanceClient />
    </Suspense>
  );
}
