import type { ReactNode } from 'react';
import CommunicationsTabs from './components/CommunicationsTabs';

export default function CommunicationsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-6">
      <CommunicationsTabs />
      {children}
    </div>
  );
}
