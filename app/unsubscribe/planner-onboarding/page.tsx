import type { Metadata } from 'next';
import SaasNav from '@/components/saas/SaasNav';
import PlannerOnboardingUnsubscribeClient from './PlannerOnboardingUnsubscribeClient';

export const metadata: Metadata = {
  title: 'Planner Onboarding Email Preferences',
  description: 'Manage your planner onboarding email preference for The Special Wedding.',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function PlannerOnboardingUnsubscribePage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />
      <PlannerOnboardingUnsubscribeClient token={token ?? ''} />
    </main>
  );
}
