import { ClientOnly } from "../../components/common/client-only";
import DashboardClient from "../../components/dashboard/dashboard-client";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClientOnly fallback={<div className="p-6 text-slate-500">Loading workspace...</div>}>
      <DashboardClient>{children}</DashboardClient>
    </ClientOnly>
  );
}
