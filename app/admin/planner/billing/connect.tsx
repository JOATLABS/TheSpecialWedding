"use client";

import React, { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { useAdmin } from '@/contexts/AdminContext';
import { useStripeConnect } from '@/hooks/useStripeConnect';
import { Loader2, CheckCircle2, AlertCircle, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';
import { getApiBaseUrl } from '@/utils/env';

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
  const apiBaseUrl = getApiBaseUrl();
  // Connect status now lives in a shared hook so the parent page can read
  // the same state to gate the "Request payment" CTA. `onboarding` is the
  // local "starting Stripe onboarding" loading flag — kept separate from
  // the hook's `loading` so we don't unmount the card mid-redirect.
  const { status: connectStatus, loading: statusLoading } = useStripeConnect();
  const [onboarding, setOnboarding] = useState(false);
  const [selectedCountry, setSelectedCountry] = useState('US');

  const handleConnect = async () => {
    try {
      setOnboarding(true);
      const response = await fetch(`${apiBaseUrl}/stripe/connect/onboard`, {
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
      setOnboarding(false);
    }
  };

  if (statusLoading || onboarding) {
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
    // p-6 added — every other Card on this page wraps its CardHeader/Content
    // with that padding (see Subscription / Payment Method / Billing History).
    // Without it the title and bullets butt against the rounded edge.
    <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 p-6">
      <CardHeader className="pb-4">
        {/* Override CardTitle's default text-2xl font-elegant — that scale is
            for page-level cards. Inner card titles on the planner billing
            page render at text-base font-semibold (see Usage This Period /
            Plan Features cards). Keeps the visual hierarchy intact. */}
        <CardTitle className="text-base font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          Get paid through Stripe
          {isConnected && <CheckCircle2 className="w-5 h-5 text-green-500" />}
        </CardTitle>
        <CardDescription>
          Connect a Stripe account to invoice couples and receive payments
          directly to your bank.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isConnected ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 p-3 rounded-lg">
              <CheckCircle2 className="w-5 h-5" />
              <span className="font-medium">Stripe is connected. You can request payments from any couple.</span>
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
             {/* Rebuilt the "Why connect?" callout: dropped blue-on-blue text
                 (read as hyperlinks per the platform visual audit doc), used
                 neutral slate text with check icons matching the Plan Features
                 list. Also removed "Pay vendors directly" — vendor payouts are
                 in the separate vendor-portal scope, not this surface. */}
             <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/50">
               <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-2">What you get</h4>
               <ul className="space-y-2 text-sm text-slate-700 dark:text-slate-300">
                 <li className="flex items-start gap-2">
                   <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                   <span>Send branded payment links to couples</span>
                 </li>
                 <li className="flex items-start gap-2">
                   <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                   <span>Collect deposits, milestones, and final balances directly</span>
                 </li>
                 <li className="flex items-start gap-2">
                   <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                   <span>Automatic email receipts after every payment</span>
                 </li>
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
                 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-wedding-rose"
               >
                 {SUPPORTED_COUNTRIES.map((country) => (
                   <option key={country.code} value={country.code}>
                     {country.name}
                   </option>
                 ))}
               </select>
               <p id="country-help" className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                 Where your business is registered.
               </p>
             </div>

             {/* Replaced raw Stripe purple #635BFF with the planner brand
                 token used everywhere else (wedding-rose / wedding-gold
                 hover, same as profile page CTAs). */}
             <Button
               onClick={handleConnect}
               className="w-full bg-wedding-rose hover:bg-wedding-gold text-white font-medium"
             >
               Connect Stripe account
             </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
