import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Wedding Portal | The Special Wedding',
  description: 'Your personal wedding planning portal',
};

export default function CoupleLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#f8f6f3] via-white to-[#f5f0eb]">
      {children}
    </div>
  );
}
