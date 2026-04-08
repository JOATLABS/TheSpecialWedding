export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-stone-50 px-6 py-16 text-slate-900">
      <div className="mx-auto max-w-4xl space-y-10">
        <header className="space-y-3">
          <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Privacy</p>
          <h1 className="text-4xl font-semibold tracking-tight">Privacy Policy</h1>
          <p className="max-w-3xl text-base text-slate-600">
            The Special Wedding is a planner platform. This policy covers planner accounts,
            team-member access, couple portals, and Google Calendar connections used for
            shared scheduling.
          </p>
        </header>

        <section className="space-y-4 rounded-3xl border border-slate-200 bg-white p-8 text-sm leading-7 text-slate-700 shadow-sm">
          <p>
            We collect planner account information, team-member account information, wedding
            metadata, couple contact details, meeting details, and external calendar
            connection metadata required to run the shared planner calendar.
          </p>
          <p>
            When a planner or permitted team member connects Google Calendar, we store
            encrypted OAuth tokens, the connected Google account email, selected calendar
            metadata, sync settings, health state, and timestamps needed to create, update,
            delete, and display calendar projections. Internal meetings remain the source of
            truth; connected calendars are projections of those internal records.
          </p>
          <p>
            OAuth callback state is signed and validated against the authenticated workspace
            user before a connection is created. Tokens are not returned in API responses and
            are not intended to be surfaced in logs.
          </p>
          <p>
            Couples do not connect their own calendars in v1. Couple meeting delivery uses
            email plus ICS attachments or links, and meetings are also shown in the couple
            portal.
          </p>
          <p>
            Shared external calendars are only shown in team views when the planner owner has
            explicitly enabled sharing. Personal external calendars default to busy/free only
            unless the planner owner explicitly enables full detail sharing for that
            connection.
          </p>
          <p>
            Disconnecting Google Calendar removes local connection records and, when
            applicable, revokes Google access for that connected account. Additional Google
            data deletion details are documented on the data deletion page.
          </p>
          <p>
            If a connection becomes expired or unhealthy, the app may stop projecting events
            until the user reconnects or refreshes the connection.
          </p>
          <p>
            Support: <a className="underline" href="/support">Visit support</a>. Data
            deletion: <a className="underline" href="/google-data-deletion">Google data deletion</a>.
          </p>
        </section>
      </div>
    </main>
  );
}
