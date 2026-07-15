'use client';

import { Loader2 } from 'lucide-react';

import { useAdmin } from '@/contexts/AdminContext';
import CommunicationsInboxView from './CommunicationsInboxView';
import RootSupportInboxView from './RootSupportInboxView';

export default function RoleScopedCommunicationsInboxView() {
  const { isLoading, userProfile } = useAdmin();

  if (isLoading || !userProfile) {
    return (
      <div className="flex min-h-[420px] items-center justify-center text-slate-500">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading inbox...
      </div>
    );
  }

  return userProfile.is_root_admin
    ? <RootSupportInboxView />
    : <CommunicationsInboxView />;
}
