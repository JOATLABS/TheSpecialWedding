export default function TermsPage() {
  return (
    <main className="min-h-screen bg-white px-6 py-16 text-slate-900">
      <div className="mx-auto max-w-4xl space-y-10">
        <header className="space-y-3">
          <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Terms</p>
          <h1 className="text-4xl font-semibold tracking-tight">Terms of Service</h1>
          <p className="max-w-3xl text-base text-slate-600">
            These terms govern planner accounts, team-member access, couple portals, shared
            planner calendars, and connected Google Calendar integrations on The Special
            Wedding.
          </p>
        </header>

        <section className="space-y-4 rounded-3xl border border-slate-200 bg-slate-50 p-8 text-sm leading-7 text-slate-700">
          <p>
            Planner accounts are responsible for the meetings, tasks, staff assignments, and
            external calendar connections created within their workspace. Team members may
            access shared calendar features only to the extent permitted by the planner
            owner’s role and visibility settings.
          </p>
          <p>
            Internal schedule items stored in The Special Wedding are the canonical records.
            External calendars, including Google Calendar, are downstream projections used for
            visibility and coordination.
          </p>
          <p>
            Couples do not authorize their personal calendars through OAuth in v1. Meeting
            invites are delivered through the platform, including email plus ICS delivery
            where enabled, and meetings remain visible inside the couple portal.
          </p>
          <p>
            If you connect Google Calendar, you authorize the app to read calendar metadata
            and manage calendar events for the calendars you connect so the product can sync
            planner-side meetings and display shared availability according to your selected
            sharing settings.
          </p>
          <p>
            The app does not treat external calendar data as the source of truth for planner
            scheduling. If a projection fails or a connection is revoked, the internal meeting
            record remains authoritative inside the workspace.
          </p>
          <p>
            Questions about these terms can be sent through the public support page at{' '}
            <a className="underline" href="/support">/support</a>.
          </p>
        </section>
      </div>
    </main>
  );
}
