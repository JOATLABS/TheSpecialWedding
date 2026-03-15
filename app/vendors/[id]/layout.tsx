import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Vendor Profile - The Special Wedding',
  description: 'View vendor profile and get in touch with wedding vendors',
};

export default function VendorProfileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
