import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Vendor Directory - The Special Wedding',
  description: 'Find and connect with wedding vendors',
};

export default function VendorsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
