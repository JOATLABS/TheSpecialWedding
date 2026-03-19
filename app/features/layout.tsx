import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Features — 13 Tools for Professional Wedding Planners',
  description:
    'Guest management, seating charts, AI contracts, vendor CRM, budget tracking, and more. See how The Special Wedding compares to HoneyBook, Aisle Planner, and Planning Pod.',
  openGraph: {
    title: 'Features — 13 Tools for Professional Wedding Planners | The Special Wedding',
    description:
      'Guest management, seating charts, AI contracts, vendor CRM, budget tracking, and more. See how we compare to HoneyBook and Aisle Planner.',
  },
};

export default function FeaturesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
