export default function DashboardHome() {
  return (
    <section className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Welcome to TTRPG Center
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Choose a role-specific workspace from the sidebar to get started.
        </p>
      </header>
      <div className="grid gap-4 md:grid-cols-3">
        <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-lg font-medium text-slate-800 dark:text-slate-100">
            Player Mode
          </h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Track characters, party progress, and session highlights.
          </p>
        </article>
        <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-lg font-medium text-slate-800 dark:text-slate-100">
            GM Mode
          </h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Orchestrate encounters, manage sources, and monitor events.
          </p>
        </article>
        <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-lg font-medium text-slate-800 dark:text-slate-100">
            Admin Mode
          </h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Review usage meters, billing links, and workspace configuration.
          </p>
        </article>
      </div>
    </section>
  );
}
