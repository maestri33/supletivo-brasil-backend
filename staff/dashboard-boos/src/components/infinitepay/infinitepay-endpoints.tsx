"use client";

import { HealthBadges } from "./health-badges";
import { CheckoutTable } from "./checkout-table";
import { CreateCheckoutForm } from "./create-checkout-form";
import { ConfigEditor } from "./config-editor";
import { WebhookTester } from "./webhook-tester";
import { CheckoutStatusLookup } from "./checkout-status-lookup";
import { AiChat } from "./ai-chat";
import { AiReports } from "./ai-reports";

export function InfinitePayEndpoints() {
  return (
    <div className="space-y-6">
      {/* Row 0: Health + Status Lookup */}
      <div className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white px-5 py-3 dark:border-zinc-800 dark:bg-zinc-950">
        <HealthBadges />
        <CheckoutStatusLookup />
      </div>

      {/* Row 1: Checkout List + Create Form */}
      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <CheckoutTable />
        </div>
        <div className="lg:col-span-2">
          <CreateCheckoutForm />
        </div>
      </div>

      {/* Row 2: Config + Webhook */}
      <div className="grid gap-6 lg:grid-cols-2">
        <ConfigEditor />
        <WebhookTester />
      </div>

      {/* Row 3: AI Chat + Reports */}
      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <AiChat />
        </div>
        <div className="lg:col-span-2">
          <AiReports />
        </div>
      </div>
    </div>
  );
}
