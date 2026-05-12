export default function GoogleDataDeletionPage() {
  return (
    <main className="min-h-screen bg-white px-6 py-16 text-slate-900">
      <div className="mx-auto max-w-4xl space-y-10">
        <header className="space-y-3">
          <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Data Deletion</p>
          <h1 className="text-4xl font-semibold tracking-tight">Google Data Deletion</h1>
          <p className="max-w-3xl text-base text-slate-600">
            To stop using Google Calendar with The Special Wedding, disconnect the calendar
            from the planner calendar settings. When the last connected calendar for that
            Google account is removed, the app revokes Google access and deletes local
            connection records used for calendar sync.
          </p>
        </header>

        <section className="space-y-4 rounded-3xl border border-slate-200 bg-slate-50 p-8 text-sm leading-7 text-slate-700">
          <p>
            Internal meetings and tasks remain inside The Special Wedding as canonical records
            even after Google access is revoked. They are no longer projected to Google once
            the connection is removed.
          </p>
          <p>
            Calendar connections are removed from the workspace, and future sync attempts will
            fail closed until a user reconnects a valid writable calendar.
          </p>
          <p>
            If you need manual assistance, contact{' '}
            <a className="underline" href="mailto:support@thespecialwedding.io">
              support@thespecialwedding.io
            </a>.
          </p>
        </section>
      </div>
    </main>
  );
}
