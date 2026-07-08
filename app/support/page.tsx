import Link from 'next/link';
import SaasNav from '../components/saas/SaasNav';

export default function SupportPage() {
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-28 text-white sm:px-8 lg:px-12">
      <SaasNav />
      <div className="mx-auto max-w-4xl space-y-8">
        <header className="space-y-3">
          <p className="text-sm uppercase tracking-[0.24em] text-slate-400">Support</p>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <h1 className="text-4xl font-semibold tracking-tight">Support</h1>
            <Link
              href="/"
              className="inline-flex w-fit items-center rounded-full border border-white/15 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-white/30 hover:bg-white/10 hover:text-white"
            >
              Back to homepage
            </Link>
          </div>
          <p className="max-w-3xl text-base text-slate-300">
            Public support for planner accounts, external calendar connections (Google,
            Microsoft 365, iCloud, Exchange/EWS), shared calendar visibility, and couple
            meeting delivery.
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
