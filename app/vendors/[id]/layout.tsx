import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Vendor Profile',
  description: 'View this wedding vendor\u2019s services, pricing, portfolio, and contact details.',
};

export default function VendorProfileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
