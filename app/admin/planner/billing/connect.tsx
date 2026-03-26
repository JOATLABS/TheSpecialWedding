"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { useAdmin } from '@/contexts/AdminContext';
import { Loader2, CheckCircle2, AlertCircle, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';

// Stripe Connect supported countries for Express accounts
const SUPPORTED_COUNTRIES = [
  { code: 'US', name: 'United States' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'CA', name: 'Canada' },
  { code: 'AU', name: 'Australia' },
  { code: 'DE', name: 'Germany' },
  { code: 'FR', name: 'France' },
  { code: 'IT', name: 'Italy' },
  { code: 'ES', name: 'Spain' },
  { code: 'NL', name: 'Netherlands' },
  { code: 'IE', name: 'Ireland' },
  { code: 'AT', name: 'Austria' },
  { code: 'BE', name: 'Belgium' },
  { code: 'DK', name: 'Denmark' },
  { code: 'FI', name: 'Finland' },
  { code: 'NO', name: 'Norway' },
  { code: 'SE', name: 'Sweden' },
  { code: 'CH', name: 'Switzerland' },
  { code: 'PT', name: 'Portugal' },
  { code: 'LU', name: 'Luxembourg' },
  { code: 'NZ', name: 'New Zealand' },
  { code: 'SG', name: 'Singapore' },
  { code: 'HK', name: 'Hong Kong' },
  { code: 'JP', name: 'Japan' },
];

export default function StripeConnectCard() {
  const { token } = useAdmin();
  const [loading, setLoading] = useState(true);
  const [connectStatus, setConnectStatus] = useState<{
    status: string;
    charges_enabled: boolean;
    payouts_enabled: boolean;
    details_submitted: boolean;
  } | null>(null);
  const [selectedCountry, setSelectedCountry] = useState('US');

  const checkStatus = useCallback(async () => {
    try {
      if (!token) return;

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/stripe/connect/status`, {
        headers: {
          'Authorization': `Bearer ${token}`
        },
        credentials: 'include',
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
  }, [token]);

  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  const handleConnect = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/stripe/connect/onboard`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          country: selectedCountry,
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

             <div>
               <label htmlFor="country" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                 Country
               </label>
               <select
                 id="country"
                 value={selectedCountry}
                 onChange={(e) => setSelectedCountry(e.target.value)}
                 aria-describedby="country-help"
                 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-[#635BFF]"
               >
                 {SUPPORTED_COUNTRIES.map((country) => (
                   <option key={country.code} value={country.code}>
                     {country.name}
                   </option>
                 ))}
               </select>
               <p id="country-help" className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                 Select the country where your business is registered
               </p>
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
