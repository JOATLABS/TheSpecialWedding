"use client";

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { DollarSign } from 'lucide-react';
import { CollectPaymentModal } from './CollectPaymentModal';

interface PaymentCollectionButtonProps {
  weddingId: string;
  weddingTitle: string;
  variant?: 'default' | 'outline' | 'ghost';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  className?: string;
}

export function PaymentCollectionButton({
  weddingId,
  weddingTitle,
  variant = 'default',
  size = 'default',
  className = '',
}: PaymentCollectionButtonProps) {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <Button
        variant={variant}
        size={size}
        className={className}
        onClick={() => setModalOpen(true)}
      >
        <DollarSign className="w-4 h-4 mr-2" />
        Collect Payment
      </Button>

      <CollectPaymentModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        weddingId={weddingId}
        weddingTitle={weddingTitle}
        onPaymentCreated={(payment) => {
          console.log('Payment created:', payment);
          // You can add additional handling here
        }}
      />
    </>
  );
}
