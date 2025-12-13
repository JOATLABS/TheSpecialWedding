"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Loader2, CreditCard, ExternalLink, CheckCircle2, XCircle, Clock, Check } from 'lucide-react';
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

export default function PlannerBillingPage() {
  const router = useRouter();
  const { userProfile } = useAdmin();
  const [loading, setLoading] = useState(true);
  const [processingCheckout, setProcessingCheckout] = useState(false);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [currentSubscription, setCurrentSubscription] = useState<UserSubscription | null>(null);
  const [selectedBillingInterval, setSelectedBillingInterval] = useState<'monthly' | 'yearly'>('monthly');
  const [currentPlan, setCurrentPlan] = useState<SubscriptionPlan | null>(null);

  // Access control - only for wedding planners
  useEffect(() => {
    if (userProfile && !userProfile.is_wedding_planner && !userProfile.is_root_admin) {
      router.push('/admin');
    }
  }, [userProfile, router]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

      // Load available plans
      let fetchedPlans: SubscriptionPlan[] = [];
      const plansResponse = await fetch(
        `${baseUrl}/public/subscription-plans`,
        { credentials: 'include' }
      );

      if (plansResponse.ok) {
        fetchedPlans = await plansResponse.json();
        setPlans(fetchedPlans);
      }

      // Load current subscription
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
      const userId = userProfile?.id;

      if (token && userId) {
        const subResponse = await fetch(
          `${baseUrl}/users/${userId}/subscription`,
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
          const planDetail = fetchedPlans.find((p: SubscriptionPlan) => p._id === subData.plan_id);
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
  }, [userProfile]);

  useEffect(() => {
    if (userProfile) {
      loadData();
    }
  }, [userProfile, loadData]);

  const handleSubscribe = async (planId: string) => {
    try {
      setProcessingCheckout(true);
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

      if (!token) {
        toast.error('Please log in to subscribe');
        router.push('/admin/login');
        return;
      }

      // Create checkout session
      const response = await fetch(
        `${baseUrl}/admin/stripe/create-checkout-session`,
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
            success_url: `${window.location.origin}/admin/planner/billing?success=true`,
            cancel_url: `${window.location.origin}/admin/planner/billing`,
            trial_days: 14
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
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

      if (!token) {
        toast.error('Please log in to manage billing');
        return;
      }

      // Create portal session
      const response = await fetch(
        `${baseUrl}/admin/stripe/create-portal-session`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
          body: JSON.stringify({
            return_url: `${window.location.origin}/admin/planner/billing`
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
        color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
        icon: <CheckCircle2 className="w-4 h-4" />,
        label: 'Active'
      },
      trialing: {
        color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
        icon: <Clock className="w-4 h-4" />,
        label: 'Trial'
      },
      cancelled: {
        color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
        icon: <XCircle className="w-4 h-4" />,
        label: 'Cancelled'
      },
      past_due: {
        color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
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
    return `$${price.toFixed(0)}/${interval === 'monthly' ? 'mo' : 'yr'}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen dark:bg-slate-700">
      {/* Header */}
      <div className="bg-white dark:bg-slate-800 shadow-sm border-b dark:border-slate-700">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-6">
            <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Billing & Subscription</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage your subscription plan and payment methods
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">{currentPlan.name}</h3>
                <p className="text-gray-600 dark:text-gray-400">{currentPlan.description}</p>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Price</p>
                  <p className="font-semibold text-gray-900 dark:text-gray-100">
                    {formatPrice(
                      currentSubscription.billing_interval === 'yearly'
                        ? currentPlan.price_yearly
                        : currentPlan.price_monthly,
                      currentSubscription.billing_interval
                    )}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Renewal Date</p>
                  <p className="font-semibold text-gray-900 dark:text-gray-100">
                    {new Date(currentSubscription.current_period_end).toLocaleDateString()}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Weddings</p>
                  <p className="font-semibold text-gray-900 dark:text-gray-100">
                    {currentPlan.max_weddings === -1 ? 'Unlimited' : currentPlan.max_weddings}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Storage</p>
                  <p className="font-semibold text-gray-900 dark:text-gray-100">{currentPlan.storage_gb} GB</p>
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

        {/* No Subscription Banner */}
        {!currentSubscription && (
          <div className="mb-8 p-6 bg-gradient-to-r from-blue-500 to-purple-600 rounded-xl text-white">
            <h2 className="text-2xl font-bold mb-2">Start Your Free Trial</h2>
            <p className="text-blue-100 mb-4">
              Get 14 days free access to all features. No credit card required to start.
            </p>
          </div>
        )}

        {/* Billing Interval Toggle */}
        <div className="flex justify-center mb-8">
          <div className="inline-flex rounded-lg border border-gray-200 dark:border-gray-700 p-1 bg-white dark:bg-slate-800">
            <button
              onClick={() => setSelectedBillingInterval('monthly')}
              className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${
                selectedBillingInterval === 'monthly'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setSelectedBillingInterval('yearly')}
              className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${
                selectedBillingInterval === 'yearly'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              Yearly
              <span className="ml-1 text-xs opacity-75">(Save 20%)</span>
            </button>
          </div>
        </div>

        {/* Available Plans */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {plans.map((plan) => {
            const price = selectedBillingInterval === 'yearly' ? plan.price_yearly : plan.price_monthly;
            const isCurrentPlan = currentSubscription?.plan_id === plan._id;
            const features = Object.entries(plan.features || {})
              .filter(([_, enabled]) => enabled)
              .map(([key]) => key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()));

            return (
              <Card
                key={plan._id}
                className={`relative ${
                  plan.is_featured
                    ? 'border-blue-500 dark:border-blue-400 shadow-lg ring-2 ring-blue-500 dark:ring-blue-400'
                    : isCurrentPlan
                    ? 'border-green-500 dark:border-green-400'
                    : ''
                }`}
              >
                {plan.is_featured && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                    <Badge className="bg-blue-600 text-white">Most Popular</Badge>
                  </div>
                )}
                {isCurrentPlan && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                    <Badge className="bg-green-600 text-white">Current Plan</Badge>
                  </div>
                )}
                <CardHeader className="pt-8">
                  <CardTitle className="text-xl">{plan.name}</CardTitle>
                  <CardDescription>{plan.description}</CardDescription>
                  <div className="mt-4">
                    <span className="text-4xl font-bold text-gray-900 dark:text-gray-100">${price.toFixed(0)}</span>
                    <span className="text-gray-500 dark:text-gray-400">
                      /{selectedBillingInterval === 'monthly' ? 'mo' : 'yr'}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3 text-sm">
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500" />
                      <span className="text-gray-700 dark:text-gray-300">
                        {plan.max_weddings === -1 ? 'Unlimited' : plan.max_weddings} wedding{plan.max_weddings !== 1 ? 's' : ''}
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500" />
                      <span className="text-gray-700 dark:text-gray-300">
                        Up to {plan.max_guests_per_wedding === -1 ? 'unlimited' : plan.max_guests_per_wedding} guests
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500" />
                      <span className="text-gray-700 dark:text-gray-300">{plan.ai_credits_monthly} AI credits/month</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500" />
                      <span className="text-gray-700 dark:text-gray-300">{plan.storage_gb} GB storage</span>
                    </li>
                    {plan.staff_seats > 0 && (
                      <li className="flex items-center gap-2">
                        <Check className="w-4 h-4 text-green-500" />
                        <span className="text-gray-700 dark:text-gray-300">{plan.staff_seats} staff seats</span>
                      </li>
                    )}
                    {features.slice(0, 3).map((feature, idx) => (
                      <li key={idx} className="flex items-center gap-2">
                        <Check className="w-4 h-4 text-green-500" />
                        <span className="text-gray-700 dark:text-gray-300">{feature}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
                <CardFooter>
                  {isCurrentPlan ? (
                    <Button disabled className="w-full bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      Current Plan
                    </Button>
                  ) : (
                    <Button
                      onClick={() => handleSubscribe(plan._id)}
                      disabled={processingCheckout}
                      className={`w-full ${plan.is_featured ? 'bg-blue-600 hover:bg-blue-700' : ''}`}
                    >
                      {processingCheckout ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        <>
                          <CreditCard className="w-4 h-4 mr-2" />
                          {currentSubscription ? 'Switch Plan' : 'Start Free Trial'}
                        </>
                      )}
                    </Button>
                  )}
                </CardFooter>
              </Card>
            );
          })}
        </div>

        {/* FAQ Section */}
        <div className="mt-12">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6 text-center">
            Frequently Asked Questions
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            <Card className="p-6">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Can I cancel anytime?</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                Yes! You can cancel your subscription at any time. Your access will continue until the end of your billing period.
              </p>
            </Card>
            <Card className="p-6">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">What happens after the trial?</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                After your 14-day trial, you&apos;ll be charged based on your selected plan. You can upgrade, downgrade, or cancel before the trial ends.
              </p>
            </Card>
            <Card className="p-6">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Can I change my plan later?</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                Absolutely! You can upgrade or downgrade your plan at any time. Changes take effect immediately with prorated billing.
              </p>
            </Card>
            <Card className="p-6">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">What payment methods do you accept?</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                We accept all major credit cards (Visa, MasterCard, American Express) through our secure Stripe payment processing.
              </p>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
