"use client";

import { UserProfilePanel } from "../../../components/home/user-profile-panel";
import { ManageBillingButton } from "../../../components/billing/manage-billing-button";
import { useSession } from "../../../hooks/useSession";

export default function SettingsPage() {
  const { data: session } = useSession();

  return (
    <section className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Account Settings
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Manage your profile, billing, and subscription settings.
        </p>
      </header>

      {/* Profile Settings */}
      <UserProfilePanel />

      {/* Billing & Subscription */}
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Billing & Subscription
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Manage your subscription tier, payment method, and billing history.
          </p>
        </div>
        <div className="mt-6">
          <ManageBillingButton
            scope="user"
            scopeId={session?.id ?? null}
            description="Access your billing portal to update payment methods, view invoices, and manage your subscription tier. Higher tiers unlock additional roles (GM, Admin) and features."
            buttonLabel="Manage Billing & Subscription"
            disabledLabel="Loading user information..."
          />
        </div>
      </section>
    </section>
  );
}
