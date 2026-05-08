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
            The Google connection is brokered through our calendar aggregator (Aurinko).
            Aurinko holds the Google OAuth credentials on our behalf; The Special Wedding
            stores only an aggregator-account access token and does not store Google OAuth
            tokens directly. The same product surface also supports Microsoft 365, iCloud,
            and Exchange via the same aggregator.
          </p>
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

        <section className="space-y-4 rounded-3xl border border-slate-200 bg-white p-8 text-sm leading-7 text-slate-700 shadow-sm">
          <h2 className="text-xl font-semibold tracking-tight text-slate-900">
            How we use Google data (per scope)
          </h2>
          <p>
            We request the minimum scopes necessary to operate the planner calendar features
            described above. Data obtained through these scopes is used only inside the
            connected planner&rsquo;s workspace to power calendar features and is never sold,
            shared with third parties for unrelated purposes, or used to serve advertisements.
          </p>
          <dl className="space-y-4">
            <div>
              <dt className="font-mono text-xs text-slate-600">
                https://www.googleapis.com/auth/calendar.events
              </dt>
              <dd className="mt-1">
                Used to create, read, update and delete calendar events on the calendar(s)
                the user has explicitly connected, so the planner can sync internal meetings
                (consultations, vendor reviews, day-of timeline events) and detect conflicts
                with existing events before writing. Read access is required for conflict
                detection and free/busy projection; write access is required to create the
                events the planner has authored inside our product.
              </dd>
            </div>
            <div>
              <dt className="font-mono text-xs text-slate-600">
                https://www.googleapis.com/auth/calendar.calendarlist.readonly
              </dt>
              <dd className="mt-1">
                Used to list the calendars on the connected user&rsquo;s Google account so the
                planner can choose which calendar(s) to read availability from and write
                events to. Read-only &mdash; we never modify the calendar list itself.
              </dd>
            </div>
            <div>
              <dt className="font-mono text-xs text-slate-600">
                https://www.googleapis.com/auth/userinfo.email
              </dt>
              <dd className="mt-1">
                Used to confirm the email address of the connected Google account matches
                the planner&rsquo;s account in our product, preventing connection mix-ups
                when a user is signed into multiple Google accounts.
              </dd>
            </div>
          </dl>
          <p>
            Disconnect at any time from your workspace settings; the aggregator-side grant
            for that account is revoked (which terminates the underlying Google OAuth grant
            held by the aggregator) and the local connection record is removed. Full data
            deletion instructions are at{' '}
            <a className="underline" href="/google-data-deletion">
              /google-data-deletion
            </a>
            .
          </p>
        </section>
      </div>
    </main>
  );
}
