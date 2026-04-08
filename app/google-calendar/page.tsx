export default function GoogleCalendarHelpPage() {
  return (
    <main className="min-h-screen bg-stone-100 px-6 py-16 text-slate-900">
      <div className="mx-auto max-w-4xl space-y-10">
        <header className="space-y-3">
          <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Google Calendar</p>
          <h1 className="text-4xl font-semibold tracking-tight">Google Calendar Integration</h1>
          <p className="max-w-3xl text-base text-slate-600">
            The planner calendar keeps internal meetings and tasks as the source of truth and
            uses connected Google calendars as explicit projections for shared scheduling.
          </p>
        </header>

        <section className="space-y-4 rounded-3xl border border-slate-200 bg-white p-8 text-sm leading-7 text-slate-700 shadow-sm">
          <p>Planner owners and permitted team members can connect Google calendars.</p>
          <p>
            Shared team visibility is opt-in per connection. Personal external calendars are
            busy/free only by default and show full details only when the planner owner
            enables detail sharing for that connection.
          </p>
          <p>
            Meetings created inside The Special Wedding can sync to explicit calendar targets.
            If no valid target is available, the meeting still exists internally and remains
            visible inside the planner workspace and couple portal.
          </p>
          <p>
            Couples do not connect Google Calendar through OAuth in v1. Couple invites are
            delivered by email plus ICS, and meetings remain visible inside the portal.
          </p>
          <p>
            If a valid calendar target is not available under the active sync policy, the
            meeting is still created internally and the external sync state is marked as not
            configured instead of guessing a different calendar.
          </p>
        </section>
      </div>
    </main>
  );
}
