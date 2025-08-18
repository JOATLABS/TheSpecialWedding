'use client';

import React, { useState } from 'react';
import { Card } from '../components/ui/Card';

interface SubscriptionPlan {
  id: string;
  name: string;
  price: number;
  features: string[];
  maxWeddings: number;
  aiCreditsMonthly: number;
  storageGb: number;
  vendorSeats: number;
  isActive: boolean;
}

interface SaasContent {
  hero: {
    title: string;
    subtitle: string;
    description: string;
    ctaText: string;
  };
  features: Array<{
    id: string;
    title: string;
    description: string;
    icon: string;
  }>;
  testimonials: Array<{
    id: string;
    name: string;
    company: string;
    role: string;
    text: string;
    avatar: string;
  }>;
}

const SaasLandingPage = () => {
  const [isYearly, setIsYearly] = useState(false);
  const [showSignupForm, setShowSignupForm] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<string>('');

  // Default content (will be fetched from API in real implementation)
  const content: SaasContent = {
    hero: {
      title: "Welcome to Special Wedding",
      subtitle: "Wedding Planning Made Simple",
      description: "The ultimate wedding planning platform for professional wedding planners. Manage multiple weddings, coordinate with vendors, and create beautiful wedding websites with AI-powered tools.",
      ctaText: "Start Free Trial"
    },
    features: [
      {
        id: "wedding_management",
        title: "Complete Wedding Management",
        description: "Manage multiple weddings with ease. Track guests, RSVPs, vendors, and timelines all in one place.",
        icon: ""
      },
      {
        id: "ai_presentation",
        title: "AI Presentation Generator",
        description: "Create stunning wedding presentations in minutes with our AI-powered tools.",
        icon: ""
      },
      {
        id: "smart_email",
        title: "Smart Email Assistant",
        description: "Send professional emails with embedded reports and updates using AI.",
        icon: ""
      },
      {
        id: "budget_optimization",
        title: "Budget Optimization Engine",
        description: "Calculate optimal spending for maximum impact on your client's special day.",
        icon: ""
      },
      {
        id: "design_research",
        title: "Design Research AI",
        description: "Get color palettes, themes, and design inspiration tailored to your clients.",
        icon: ""
      },
      {
        id: "vendor_management",
        title: "Vendor Collaboration",
        description: "Give vendors access to update their portions of the wedding checklist.",
        icon: ""
      }
    ],
    testimonials: [
      {
        id: "testimonial_1",
        name: "Sarah Johnson",
        company: "Elegant Events Planning",
        role: "Senior Wedding Planner",
        text: "Special Wedding has revolutionized how I manage my clients' weddings. The AI tools save me hours every week!",
        avatar: "/images/testimonial-1.jpg"
      },
      {
        id: "testimonial_2",
        name: "Michael Chen",
        company: "Dream Day Weddings",
        role: "Wedding Coordinator",
        text: "The vendor collaboration features are game-changing. Everyone stays on the same page effortlessly.",
        avatar: "/images/testimonial-2.jpg"
      },
      {
        id: "testimonial_3",
        name: "Emily Rodriguez",
        company: "Perfect Moments",
        role: "Lead Planner",
        text: "My clients love their custom wedding websites, and I love how easy they are to create and manage.",
        avatar: "/images/testimonial-3.jpg"
      }
    ]
  };

  const plans: SubscriptionPlan[] = [
    {
      id: "plan_starter",
      name: "Starter",
      price: 0,
      features: [
        "1 Wedding",
        "Basic RSVP Management",
        "Simple Wedding Website",
        "Guest List Management",
        "Email Notifications"
      ],
      maxWeddings: 1,
      aiCreditsMonthly: 10,
      storageGb: 1,
      vendorSeats: 0,
      isActive: true
    },
    {
      id: "plan_professional",
      name: "Professional",
      price: 49,
      features: [
        "Up to 5 Weddings",
        "Advanced RSVP Management",
        "Custom Wedding Websites",
        "Vendor Management",
        "AI-Powered Tools",
        "Advanced Reporting",
        "SMS Notifications",
        "Priority Support"
      ],
      maxWeddings: 5,
      aiCreditsMonthly: 100,
      storageGb: 10,
      vendorSeats: 10,
      isActive: true
    },
    {
      id: "plan_enterprise",
      name: "Enterprise",
      price: 149,
      features: [
        "Unlimited Weddings",
        "White-label Solution",
        "Advanced AI Features",
        "Custom Integrations",
        "Dedicated Support",
        "Advanced Analytics",
        "Multi-user Collaboration",
        "API Access"
      ],
      maxWeddings: -1,
      aiCreditsMonthly: 500,
      storageGb: 100,
      vendorSeats: 50,
      isActive: true
    }
  ];

  const handleStartTrial = (planId: string) => {
    setSelectedPlan(planId);
    setShowSignupForm(true);
  };

  const getPrice = (plan: SubscriptionPlan) => {
    if (plan.price === 0) return 'Free';
    const price = isYearly ? plan.price * 10 : plan.price; // 2 months free on yearly
    return `$${price}${isYearly ? '/year' : '/month'}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Hero Section */}
      <section className="relative py-20 px-4 text-center bg-gradient-to-r from-blue-600 to-purple-600 text-white">
        <div className="max-w-6xl mx-auto">
          <div className="mb-6">
            <h1 className="text-5xl font-bold mb-4">{content.hero.title}</h1>
            <h2 className="text-2xl font-light mb-6">{content.hero.subtitle}</h2>
          </div>
          <p className="text-xl mb-8 max-w-3xl mx-auto opacity-90">
            {content.hero.description}
          </p>
          <button
            onClick={() => handleStartTrial('plan_starter')}
            className="bg-white text-blue-600 px-8 py-4 rounded-lg font-semibold text-lg hover:bg-gray-100 transition-colors shadow-lg"
          >
            {content.hero.ctaText}
          </button>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-4xl font-bold text-center mb-16 text-gray-800">
            Powerful Features for Wedding Professionals
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {content.features.map((feature) => (
              <Card key={feature.id} className="p-6 hover:shadow-lg transition-shadow">
                <h3 className="text-xl font-semibold mb-3 text-gray-800">{feature.title}</h3>
                <p className="text-gray-600">{feature.description}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="py-20 px-4 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4 text-gray-800">Simple, Transparent Pricing</h2>
            <p className="text-xl text-gray-600 mb-8">
              Choose the perfect plan for your wedding planning business. All plans include a free trial.
            </p>
            
            {/* Pricing Toggle */}
            <div className="flex items-center justify-center mb-8">
              <span className={`mr-3 ${!isYearly ? 'text-blue-600 font-semibold' : 'text-gray-500'}`}>
                Monthly
              </span>
              <button
                onClick={() => setIsYearly(!isYearly)}
                className="relative inline-flex h-6 w-11 items-center rounded-full bg-gray-300 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    isYearly ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
              <span className={`ml-3 ${isYearly ? 'text-blue-600 font-semibold' : 'text-gray-500'}`}>
                Yearly
              </span>
              {isYearly && (
                <span className="ml-2 bg-green-100 text-green-800 text-sm px-2 py-1 rounded-full">
                  Save 20%
                </span>
              )}
            </div>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {plans.map((plan, index) => (
              <Card
                key={plan.id}
                className={`p-8 relative ${
                  index === 1 ? 'border-2 border-blue-500 transform scale-105' : ''
                }`}
              >
                {index === 1 && (
                  <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                    <span className="bg-blue-500 text-white px-4 py-1 rounded-full text-sm font-semibold">
                      Most Popular
                    </span>
                  </div>
                )}
                
                <div className="text-center mb-6">
                  <h3 className="text-2xl font-bold mb-2">{plan.name}</h3>
                  <p className="text-gray-600 mb-4">
                    {plan.name === 'Starter' && 'Perfect for getting started'}
                    {plan.name === 'Professional' && 'Essential features for small to medium planners'}
                    {plan.name === 'Enterprise' && 'Advanced features for large planning businesses'}
                  </p>
                  <div className="text-4xl font-bold text-blue-600 mb-1">
                    {getPrice(plan)}
                  </div>
                  {plan.price > 0 && (
                    <p className="text-sm text-gray-500">
                      {isYearly ? '2 months free' : 'per planner'}
                    </p>
                  )}
                </div>

                <ul className="space-y-3 mb-8">
                  {plan.features.map((feature, idx) => (
                    <li key={idx} className="flex items-center">
                      <span className="text-green-500 mr-3">✓</span>
                      <span className="text-gray-700">{feature}</span>
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => handleStartTrial(plan.id)}
                  className={`w-full py-3 px-6 rounded-lg font-semibold transition-colors ${
                    index === 1
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                  }`}
                >
                  {plan.price === 0 ? 'Start Free Trial' : 'Choose Plan'}
                </button>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="py-20 px-4 bg-gray-50">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-4xl font-bold text-center mb-16 text-gray-800">
            What Wedding Planners Are Saying
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            {content.testimonials.map((testimonial) => (
              <Card key={testimonial.id} className="p-6">
                <div className="flex items-center mb-4">
                  <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mr-4">
                    <span className="text-blue-600 font-bold text-lg">
                      {testimonial.name.split(' ').map(n => n[0]).join('')}
                    </span>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-800">{testimonial.name}</h4>
                    <p className="text-sm text-gray-600">{testimonial.role}</p>
                    <p className="text-sm text-blue-600">{testimonial.company}</p>
                  </div>
                </div>
                <p className="text-gray-700 italic">"{testimonial.text}"</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4 bg-blue-600 text-white text-center">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-4xl font-bold mb-4">Ready to Transform Your Wedding Planning?</h2>
          <p className="text-xl mb-8 opacity-90">
            Join thousands of wedding planners already using our platform to create unforgettable experiences.
          </p>
          <button
            onClick={() => handleStartTrial('plan_professional')}
            className="bg-white text-blue-600 px-8 py-4 rounded-lg font-semibold text-lg hover:bg-gray-100 transition-colors shadow-lg"
          >
            Start Your Free Trial Today
          </button>
        </div>
      </section>

      {/* Signup Form Modal */}
      {showSignupForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <Card className="w-full max-w-md p-8">
            <h3 className="text-2xl font-bold mb-6 text-center">Get Started</h3>
            <p className="text-gray-600 mb-6 text-center">
              You selected the <strong>{plans.find(p => p.id === selectedPlan)?.name}</strong> plan.
              Sign up to begin your journey!
            </p>
            
            <form className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Company Name</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Your Planning Company"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="planner@yourcompany.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                <input
                  type="password"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Minimum 8 characters"
                />
              </div>
              
              <div className="flex space-x-4 mt-6">
                <button
                  type="button"
                  onClick={() => setShowSignupForm(false)}
                  className="flex-1 py-2 px-4 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Start Free Trial
                </button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
};

export default SaasLandingPage;