"use client";

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Loader2, CheckCircle2, AlertCircle, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';

export default function StripeConnectCard() {
  const [loading, setLoading] = useState(true);
  const [connectStatus, setConnectStatus] = useState<{
    status: string;
    charges_enabled: boolean;
    payouts_enabled: boolean;
    details_submitted: boolean;
  } | null>(null);

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      const token = localStorage.getItem('admin_token');
      if (!token) return;

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/stripe/connect/status`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setConnectStatus(data);
      }
    } catch (error) {
      console.error('Failed to check connect status', error);
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('admin_token');

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/stripe/connect/onboard`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          country: 'US',
          return_url: `${window.location.origin}/admin/planner/billing`,
          refresh_url: `${window.location.origin}/admin/planner/billing`
        })
      });

      if (!response.ok) throw new Error('Failed to start onboarding');

      const data = await response.json();
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (error) {
      console.error('Connect error:', error);
      toast.error('Failed to connect with Stripe');
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="py-6 flex justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
        </CardContent>
      </Card>
    );
  }

  const isConnected = connectStatus?.details_submitted && connectStatus?.charges_enabled;

  return (
    <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700">
      <CardHeader>
        <CardTitle className="text-gray-900 dark:text-gray-100 flex items-center gap-2">
          Stripe Connect
          {isConnected && <CheckCircle2 className="w-5 h-5 text-green-500" />}
        </CardTitle>
        <CardDescription>
          Connect your account to receive payments from clients and pay vendors.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isConnected ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 p-3 rounded-lg">
              <CheckCircle2 className="w-5 h-5" />
              <span className="font-medium">Your account is connected and ready to process payments.</span>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="flex justify-between p-2 bg-gray-50 dark:bg-gray-700 rounded">
                <span className="text-gray-500 dark:text-gray-400">Payouts</span>
                <span className={connectStatus.payouts_enabled ? "text-green-600" : "text-yellow-600"}>
                  {connectStatus.payouts_enabled ? "Enabled" : "Pending"}
                </span>
              </div>
              <div className="flex justify-between p-2 bg-gray-50 dark:bg-gray-700 rounded">
                <span className="text-gray-500 dark:text-gray-400">Charges</span>
                <span className={connectStatus.charges_enabled ? "text-green-600" : "text-yellow-600"}>
                  {connectStatus.charges_enabled ? "Enabled" : "Pending"}
                </span>
              </div>
            </div>

            {!connectStatus.payouts_enabled && (
               <div className="flex items-start gap-2 text-yellow-600 dark:text-yellow-400 text-sm mt-2">
                 <AlertCircle className="w-4 h-4 mt-0.5" />
                 <span>Your account is connected but payouts are currently disabled. Please check your Stripe dashboard for any required actions.</span>
               </div>
            )}

            <Button onClick={handleConnect} variant="outline" className="w-full mt-2">
              Update Account Settings <ExternalLink className="w-4 h-4 ml-2" />
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
             <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
               <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-1">Why connect?</h4>
               <ul className="text-sm text-blue-700 dark:text-blue-300 space-y-1 list-disc list-inside">
                 <li>Receive direct payments from couples</li>
                 <li>Pay vendors directly from the platform</li>
                 <li>Automated invoicing and receipts</li>
               </ul>
             </div>

             <Button
               onClick={handleConnect}
               className="w-full bg-[#635BFF] hover:bg-[#534be0] text-white font-medium"
             >
               Connect with Stripe
             </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
