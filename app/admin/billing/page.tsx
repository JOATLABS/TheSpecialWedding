"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Loader2, CreditCard, ExternalLink, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { toast } from 'sonner';

interface SubscriptionPlan {
  _id: string;
  name: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  max_weddings: number;
  max_guests_per_wedding: number;
  ai_credits_monthly: number;
  storage_gb: number;
  staff_seats: number;
  features: Record<string, boolean>;
  is_featured: boolean;
}

interface UserSubscription {
  _id: string;
  plan_id: string;
  status: string;
  billing_interval: string;
  current_period_start: string;
  current_period_end: string;
  stripe_subscription_id?: string;
  stripe_customer_id?: string;
  payment_status?: string;
}

export default function BillingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [processingCheckout, setProcessingCheckout] = useState(false);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [currentSubscription, setCurrentSubscription] = useState<UserSubscription | null>(null);
  const [selectedBillingInterval, setSelectedBillingInterval] = useState<'monthly' | 'yearly'>('monthly');
  const [currentPlan, setCurrentPlan] = useState<SubscriptionPlan | null>(null);
  const [preSelectedPlanId, setPreSelectedPlanId] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);

      // Load available plans
      let fetchedPlans: SubscriptionPlan[] = [];
      const plansResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/public/subscription-plans`,
        {
          credentials: 'include'
        }
      );

      if (plansResponse.ok) {
        fetchedPlans = await plansResponse.json();
        setPlans(fetchedPlans);
      }

      // Load current subscription
      const token = localStorage.getItem('authToken');
      const userId = localStorage.getItem('userId');

      if (token && userId) {
        const subResponse = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/users/${userId}/subscription`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            credentials: 'include'
          }
        );

        if (subResponse.ok) {
          const subData = await subResponse.json();
          setCurrentSubscription(subData);

          // Find the current plan details
          const planSource = fetchedPlans;
          const planDetail = planSource.find((p: SubscriptionPlan) => p._id === subData.plan_id);
          setCurrentPlan(planDetail || null);
          setSelectedBillingInterval(subData.billing_interval || 'monthly');
        }
      }
    } catch (error) {
      console.error('Error loading billing data:', error);
      toast.error('Failed to load billing information');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Check for pre-selected plan from URL
    const planParam = searchParams.get('plan');
    const intervalParam = searchParams.get('interval');

    if (planParam) {
      setPreSelectedPlanId(planParam);
    }
    if (intervalParam && (intervalParam === 'monthly' || intervalParam === 'yearly')) {
      setSelectedBillingInterval(intervalParam);
    }

    loadData();
  }, [searchParams, loadData]);

  const handleSubscribe = async (planId: string) => {
    try {
      setProcessingCheckout(true);

      const token = localStorage.getItem('authToken');
      if (!token) {
        toast.error('Please log in to subscribe');
        router.push('/admin/login');
        return;
      }

      // Create checkout session
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/stripe/create-checkout-session`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
          body: JSON.stringify({
            plan_id: planId,
            billing_interval: selectedBillingInterval,
            success_url: `${window.location.origin}/admin/billing/success?session_id={CHECKOUT_SESSION_ID}`,
            cancel_url: `${window.location.origin}/admin/billing`,
            trial_days: 0 // Set to 0 for immediate billing, or 14 for trial
          })
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create checkout session');
      }

      const data = await response.json();

      // Redirect to Stripe Checkout
      if (data.checkout_session?.url) {
        window.location.href = data.checkout_session.url;
      } else {
        throw new Error('No checkout URL received');
      }
    } catch (error: any) {
      console.error('Checkout error:', error);
      toast.error(error.message || 'Failed to start checkout process');
      setProcessingCheckout(false);
    }
  };

  const handleManageBilling = async () => {
    try {
      const token = localStorage.getItem('authToken');
      if (!token) {
        toast.error('Please log in to manage billing');
        return;
      }

      // Create portal session
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/stripe/create-portal-session`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
          body: JSON.stringify({
            return_url: `${window.location.origin}/admin/billing`
          })
        }
      );

      if (!response.ok) {
        throw new Error('Failed to create portal session');
      }

      const data = await response.json();

      // Redirect to Stripe Customer Portal
      if (data.portal_url) {
        window.location.href = data.portal_url;
      }
    } catch (error) {
      console.error('Portal error:', error);
      toast.error('Failed to open billing portal');
    }
  };

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
      active: {
        color: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
        icon: <CheckCircle2 className="w-4 h-4" />,
        label: 'Active'
      },
      trial: {
        color: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
        icon: <Clock className="w-4 h-4" />,
        label: 'Trial'
      },
      cancelled: {
        color: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300',
        icon: <XCircle className="w-4 h-4" />,
        label: 'Cancelled'
      },
      past_due: {
        color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300',
        icon: <Clock className="w-4 h-4" />,
        label: 'Past Due'
      }
    };

    const config = statusConfig[status] || statusConfig.active;

    return (
      <Badge className={`${config.color} flex items-center gap-1`}>
        {config.icon}
        {config.label}
      </Badge>
    );
  };

  const formatPrice = (price: number, interval: string) => {
    return `$${price.toFixed(2)}/${interval === 'monthly' ? 'mo' : 'yr'}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="container max-w-7xl mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Billing & Subscription</h1>
        <p className="text-gray-600 dark:text-gray-400">
          Manage your subscription plan and payment methods
        </p>
      </div>

      {/* Current Subscription */}
      {currentSubscription && currentPlan && (
        <Card className="mb-8">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Current Subscription</CardTitle>
                <CardDescription>Your active plan and billing details</CardDescription>
              </div>
              {getStatusBadge(currentSubscription.status)}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h3 className="font-semibold text-lg">{currentPlan.name}</h3>
              <p className="text-gray-600 dark:text-gray-400">{currentPlan.description}</p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Price</p>
                <p className="font-semibold">
                  {formatPrice(
                    currentSubscription.billing_interval === 'yearly'
                      ? currentPlan.price_yearly
                      : currentPlan.price_monthly,
                    currentSubscription.billing_interval
                  )}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Renewal Date</p>
                <p className="font-semibold">
                  {new Date(currentSubscription.current_period_end).toLocaleDateString()}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Weddings</p>
                <p className="font-semibold">
                  {currentPlan.max_weddings === -1 ? 'Unlimited' : currentPlan.max_weddings}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Storage</p>
                <p className="font-semibold">{currentPlan.storage_gb} GB</p>
              </div>
            </div>
          </CardContent>
          <CardFooter>
            <Button onClick={handleManageBilling} variant="outline" className="w-full sm:w-auto">
              <ExternalLink className="w-4 h-4 mr-2" />
              Manage Billing
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* Billing Interval Toggle */}
      <div className="flex justify-center mb-8">
        <div className="inline-flex rounded-lg border border-gray-200 dark:border-gray-700 p-1">
          <button
            onClick={() => setSelectedBillingInterval('monthly')}
            className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${
              selectedBillingInterval === 'monthly'
                ? 'bg-primary text-primary-foreground'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            }`}
          >
            Monthly
          </button>
          <button
            onClick={() => setSelectedBillingInterval('yearly')}
            className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${
              selectedBillingInterval === 'yearly'
                ? 'bg-primary text-primary-foreground'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            }`}
          >
            Yearly
            <span className="ml-1 text-xs">(Save 20%)</span>
          </button>
        </div>
      </div>

      {/* Available Plans */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {plans.map((plan) => {
          const price =
            selectedBillingInterval === 'yearly' ? plan.price_yearly : plan.price_monthly;
          const isCurrentPlan = currentSubscription?.plan_id === plan._id;
          const isPreSelected = preSelectedPlanId === plan._id;

          return (
            <Card
              key={plan._id}
              className={`relative ${
                plan.is_featured
                  ? 'border-primary shadow-lg ring-2 ring-primary'
                  : isPreSelected
                  ? 'border-green-500 shadow-lg ring-2 ring-green-500 animate-pulse'
                  : ''
              }`}
            >
              {plan.is_featured && !isPreSelected && (
                <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                  <Badge className="bg-primary text-primary-foreground">Popular</Badge>
                </div>
              )}
              {isPreSelected && (
                <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                  <Badge className="bg-green-500 text-white">Selected from Pricing</Badge>
                </div>
              )}
              <CardHeader>
                <CardTitle>{plan.name}</CardTitle>
                <CardDescription>{plan.description}</CardDescription>
                <div className="mt-4">
                  <span className="text-4xl font-bold">${price.toFixed(0)}</span>
                  <span className="text-gray-600 dark:text-gray-400">
                    /{selectedBillingInterval === 'monthly' ? 'mo' : 'yr'}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  <li>
                    {plan.max_weddings === -1 ? 'Unlimited' : plan.max_weddings} wedding
                    {plan.max_weddings !== 1 ? 's' : ''}
                  </li>
                  <li>
                    Up to {plan.max_guests_per_wedding === -1 ? 'unlimited' : plan.max_guests_per_wedding} guests
                  </li>
                  <li>{plan.ai_credits_monthly} AI credits/month</li>
                  <li>{plan.storage_gb} GB storage</li>
                  {plan.staff_seats > 0 && <li>{plan.staff_seats} staff seats</li>}
                </ul>
              </CardContent>
              <CardFooter>
                {isCurrentPlan ? (
                  <Button disabled className="w-full">
                    Current Plan
                  </Button>
                ) : (
                  <Button
                    onClick={() => handleSubscribe(plan._id)}
                    disabled={processingCheckout}
                    className={`w-full ${isPreSelected ? 'bg-green-600 hover:bg-green-700' : ''}`}
                  >
                    {processingCheckout ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <CreditCard className="w-4 h-4 mr-2" />
                        {isPreSelected ? 'Subscribe to Selected Plan' : 'Subscribe'}
                      </>
                    )}
                  </Button>
                )}
              </CardFooter>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
