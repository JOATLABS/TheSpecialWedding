
'use client';

import React from 'react';
import Messaging from '../../components/messaging/Messaging';
import { useParams } from 'next/navigation';

const MessagingPage = () => {
  const params = useParams();
  const weddingId = params.weddingId as string;

  if (!weddingId) {
    return <div>Loading...</div>;
  }

  return <Messaging weddingId={weddingId} />;
};

export default MessagingPage;
