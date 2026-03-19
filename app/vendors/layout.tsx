import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Vendor Directory',
  description: 'Browse wedding vendors by category — photographers, caterers, florists, venues, and more. View profiles, pricing, and portfolios.',
};

export default function VendorsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
