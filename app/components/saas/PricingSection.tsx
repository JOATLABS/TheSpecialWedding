'use client';

import React, { useState, useEffect } from 'react';
import { GlassCard } from '../ui/GlassCard';
import { ThemeConfig } from '@/types/wedding';

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
  features: string[];
  is_featured: boolean;
  is_active: boolean;
  display_order: number;
}

interface PricingSectionProps {
  theme: ThemeConfig;
  onPlanSelect?: (planId: string) => void;
}

export const PricingSection: React.FC<PricingSectionProps> = ({ theme, onPlanSelect }) => {
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isYearly, setIsYearly] = useState(false);

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/public/subscription-plans`);
      
      if (response.ok) {
        const data = await response.json();
        // Sort by display_order and filter active plans
        const sortedPlans = data
          .filter((plan: SubscriptionPlan) => plan.is_active)
          .sort((a: SubscriptionPlan, b: SubscriptionPlan) => a.display_order - b.display_order);
        setPlans(sortedPlans);
      } else {
        setError('Failed to load pricing plans');
      }
    } catch (error) {
      setError('Failed to load pricing plans');
    } finally {
      setLoading(false);
    }
  };

  const formatPrice = (plan: SubscriptionPlan) => {
    if (plan.price_monthly === 0) return 'Free';
    const price = isYearly ? plan.price_yearly : plan.price_monthly;
    return `$${price}`;
  };

  const getDisplayLimit = (value: number) => {
    return value === -1 ? 'Unlimited' : value.toString();
  };

  const handleSelectPlan = (planId: string) => {
    if (onPlanSelect) {
      onPlanSelect(planId);
    }
  };

  if (loading) {
    return (
      <section className="py-16 px-4">
        <div className="max-w-6xl mx-auto text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 mx-auto mb-4" style={{ borderColor: theme.primary_color }}></div>
          <p className="text-gray-600">Loading pricing plans...</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="py-16 px-4">
        <div className="max-w-6xl mx-auto text-center">
          <p className="text-red-600">{error}</p>
        </div>
      </section>
    );
  }

  return (
    <section className="py-16 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Simple, Transparent Pricing
          </h2>
          <p className="text-xl text-gray-100 mb-8 max-w-3xl mx-auto">
            Choose the perfect plan for your wedding planning business. All plans include a free trial.
          </p>
          
          {/* Pricing Toggle */}
          <div className="flex items-center justify-center mb-8">
            <span className={`mr-3 transition-colors ${!isYearly ? 'text-white font-semibold' : 'text-gray-300'}`}>
              Monthly
            </span>
            <button
              onClick={() => setIsYearly(!isYearly)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                isYearly ? 'bg-white' : 'bg-gray-400'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  isYearly ? 'translate-x-6' : 'translate-x-1'
                }`}
                style={{ backgroundColor: isYearly ? theme.primary_color : 'white' }}
              />
            </button>
            <span className={`ml-3 transition-colors ${isYearly ? 'text-white font-semibold' : 'text-gray-300'}`}>
              Yearly
            </span>
            {isYearly && (
              <span className="ml-2 bg-green-500 text-white px-2 py-1 rounded text-xs font-medium">
                2 months free
              </span>
            )}
          </div>
        </div>

        {/* Pricing Cards */}
        <div className={`grid gap-6 mt-8 ${plans.length <= 3 ? 'md:grid-cols-3' : 'md:grid-cols-2 lg:grid-cols-4'}`}>
          {plans.map((plan) => (
            <GlassCard
              key={plan._id}
              depth={plan.is_featured ? 'near' : 'mid'}
              className={`p-6 text-center relative ${
                plan.is_featured ? 'ring-2 ring-white/50 scale-105' : ''
              }`}
              theme={theme}
            >
              {plan.is_featured && (
                <div 
                  className="absolute -top-5 left-1/2 transform -translate-x-1/2 px-4 py-1 rounded-full text-white text-sm font-medium"
                  style={{ backgroundColor: theme.secondary_color }}
                >
                  Most Popular
                </div>
              )}
              
              <div className="mb-6">
                <h3 className="text-xl font-bold text-gray-900 mb-2">{plan.name}</h3>
                <p className="text-gray-600 text-sm mb-4">{plan.description}</p>
                <div className="text-3xl font-bold text-gray-900 mb-1">
                  {formatPrice(plan)}
                  {plan.price_monthly > 0 && (
                    <span className="text-sm font-normal text-gray-500">
                      /{isYearly ? 'year' : 'month'}
                    </span>
                  )}
                </div>
                {isYearly && plan.price_monthly > 0 && (
                  <p className="text-sm text-gray-500">
                    ${(plan.price_monthly * 12).toFixed(0)}/year billed monthly
                  </p>
                )}
              </div>

              <div className="mb-6 space-y-3 text-left">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Weddings:</span>
                  <span className="font-medium text-gray-900">{getDisplayLimit(plan.max_weddings)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Guests per wedding:</span>
                  <span className="font-medium text-gray-900">{getDisplayLimit(plan.max_guests_per_wedding)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">AI credits/month:</span>
                  <span className="font-medium text-gray-900">{plan.ai_credits_monthly}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Storage:</span>
                  <span className="font-medium text-gray-900">{plan.storage_gb}GB</span>
                </div>
              </div>

              <div className="mb-6">
                <div className="text-left">
                  <h4 className="font-medium text-gray-900 mb-2">Features:</h4>
                  <ul className="space-y-1">
                    {Array.isArray(plan.features) ? plan.features.slice(0, 5).map((feature, index) => (
                      <li key={index} className="flex items-start text-sm text-gray-600">
                        <svg className="w-4 h-4 text-green-500 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        {feature}
                      </li>
                    )) : (
                      <li className="text-sm text-gray-600">No features listed</li>
                    )}
                    {Array.isArray(plan.features) && plan.features.length > 5 && (
                      <li className="text-sm text-gray-500 italic">
                        +{plan.features.length - 5} more features
                      </li>
                    )}
                  </ul>
                </div>
              </div>

              <button
                onClick={() => handleSelectPlan(plan._id)}
                className={`w-full py-3 px-4 rounded-lg font-medium transition-all duration-200 ${
                  plan.is_featured
                    ? 'text-white shadow-lg hover:shadow-xl transform hover:scale-105'
                    : 'border-2 text-gray-700 hover:text-white hover:shadow-lg'
                }`}
                style={{
                  backgroundColor: plan.is_featured ? theme.primary_color : 'transparent',
                  borderColor: plan.is_featured ? theme.primary_color : theme.primary_color,
                  ...(plan.is_featured ? {} : {
                    ':hover': {
                      backgroundColor: theme.primary_color
                    }
                  })
                }}
                onMouseEnter={(e) => {
                  if (!plan.is_featured) {
                    e.currentTarget.style.backgroundColor = theme.primary_color;
                    e.currentTarget.style.color = 'white';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!plan.is_featured) {
                    e.currentTarget.style.backgroundColor = 'transparent';
                    e.currentTarget.style.color = '#374151';
                  }
                }}
              >
                {plan.price_monthly === 0 ? 'Start Free Trial' : 'Choose Plan'}
              </button>
            </GlassCard>
          ))}
        </div>

        {/* Additional Information */}
        <div className="text-center mt-12">
          <p className="text-gray-100 mb-4">
            All plans include a 14-day free trial. No credit card required.
          </p>
          <p className="text-sm text-gray-300">
            Need something custom? <button className="underline hover:text-white transition-colors">Contact our sales team</button>
          </p>
        </div>
      </div>
    </section>
  );
};