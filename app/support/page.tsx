export default function SupportPage() {
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-16 text-white">
      <div className="mx-auto max-w-4xl space-y-8">
        <header className="space-y-3">
          <p className="text-sm uppercase tracking-[0.24em] text-slate-400">Support</p>
          <h1 className="text-4xl font-semibold tracking-tight">Support</h1>
          <p className="max-w-3xl text-base text-slate-300">
            Public support for planner accounts, Google Calendar connections, shared calendar
            visibility, and couple meeting delivery.
          </p>
        </header>

        <section className="space-y-4 rounded-3xl border border-white/10 bg-white/5 p-8 text-sm leading-7 text-slate-200">
          <p>Email: <a className="underline" href="mailto:support@thespecialwedding.io">support@thespecialwedding.io</a></p>
          <p>Sales and onboarding: <a className="underline" href="mailto:hello@thespecialwedding.io">hello@thespecialwedding.io</a></p>
          <p>Calendar help: <a className="underline" href="/google-calendar">Google Calendar integration</a></p>
          <p>Google data deletion: <a className="underline" href="/google-data-deletion">Google data deletion</a></p>
          <p>
            Include the workspace email, affected wedding, and whether the issue involved an
            owner calendar, team calendar, or couple invite so support can reproduce the flow.
          </p>
        </section>
      </div>
    </main>
  );
}
