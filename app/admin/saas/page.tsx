'use client';

import React, { useState, useEffect } from 'react';
import { Card } from '@/app/components/ui/Card';

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

interface SaasContentSection {
  id: string;
  section: string;
  content: any;
  isActive: boolean;
  displayOrder: number;
  updatedBy: string;
  updatedAt: string;
}

interface WeddingPlanner {
  id: string;
  email: string;
  companyName: string;
  subscriptionPlanId: string;
  subscriptionStatus: string;
  maxWeddings: number;
  isActive: boolean;
  createdAt: string;
  lastLogin?: string;
}

const SaasAdminDashboard = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'plans' | 'content' | 'planners'>('overview');
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [contentSections, setContentSections] = useState<SaasContentSection[]>([]);
  const [planners, setPlanners] = useState<WeddingPlanner[]>([]);
  const [loading, setLoading] = useState(true);

  // Mock data for now - will be replaced with API calls
  useEffect(() => {
    // Simulate API loading
    setTimeout(() => {
      setPlans([
        {
          id: "plan_starter",
          name: "Starter",
          price: 0,
          features: ["1 Wedding", "Basic RSVP Management", "Simple Wedding Website"],
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
          features: ["Up to 5 Weddings", "Advanced RSVP Management", "AI-Powered Tools"],
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
          features: ["Unlimited Weddings", "White-label Solution", "Advanced AI Features"],
          maxWeddings: -1,
          aiCreditsMonthly: 500,
          storageGb: 100,
          vendorSeats: 50,
          isActive: true
        }
      ]);

      setContentSections([
        {
          id: "hero_section",
          section: "hero",
          content: {
            title: "Welcome to Special Wedding",
            subtitle: "Wedding Planning Made Simple",
            description: "The ultimate wedding planning platform..."
          },
          isActive: true,
          displayOrder: 1,
          updatedBy: "thedeveloper@thespecialwedding.com",
          updatedAt: "2024-08-18T00:00:00Z"
        },
        {
          id: "features_section",
          section: "features",
          content: {
            title: "Powerful Features for Wedding Professionals",
            features: []
          },
          isActive: true,
          displayOrder: 2,
          updatedBy: "thedeveloper@thespecialwedding.com",
          updatedAt: "2024-08-18T00:00:00Z"
        }
      ]);

      setPlanners([
        {
          id: "planner_001",
          email: "sarah@elegantevents.com",
          companyName: "Elegant Events Planning",
          subscriptionPlanId: "plan_professional",
          subscriptionStatus: "active",
          maxWeddings: 5,
          isActive: true,
          createdAt: "2024-08-15T00:00:00Z",
          lastLogin: "2024-08-17T14:30:00Z"
        }
      ]);

      setLoading(false);
    }, 1000);
  }, []);

  const handleCreatePlan = () => {
    // TODO: Implement plan creation
    console.log('Create new subscription plan');
  };

  const handleEditContent = (sectionId: string) => {
    // TODO: Implement content editing
    console.log('Edit content section:', sectionId);
  };

  const handleCreatePlanner = () => {
    // TODO: Implement planner creation
    console.log('Create new wedding planner');
  };

  const handleTogglePlannerStatus = (plannerId: string) => {
    setPlanners(prev => prev.map(planner => 
      planner.id === plannerId 
        ? { ...planner, isActive: !planner.isActive }
        : planner
    ));
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading SAAS Dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">SAAS Admin Dashboard</h1>
              <p className="text-gray-600">Manage your wedding planning platform</p>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-500">ROOT_ADMIN</span>
              <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
                <span className="text-white font-semibold">TD</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-8">
            {[
              { key: 'overview', label: 'Overview', icon: '📊' },
              { key: 'plans', label: 'Subscription Plans', icon: '💳' },
              { key: 'content', label: 'SAAS Content', icon: '✏️' },
              { key: 'planners', label: 'Wedding Planners', icon: '👥' }
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as any)}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.key
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span className="mr-2">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <Card className="p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-blue-100 rounded-md flex items-center justify-center">
                      <span className="text-blue-600">👥</span>
                    </div>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">Total Planners</dt>
                      <dd className="text-lg font-medium text-gray-900">{planners.length}</dd>
                    </dl>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-green-100 rounded-md flex items-center justify-center">
                      <span className="text-green-600">💳</span>
                    </div>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">Active Plans</dt>
                      <dd className="text-lg font-medium text-gray-900">{plans.filter(p => p.isActive).length}</dd>
                    </dl>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-purple-100 rounded-md flex items-center justify-center">
                      <span className="text-purple-600">💍</span>
                    </div>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">Total Weddings</dt>
                      <dd className="text-lg font-medium text-gray-900">12</dd>
                    </dl>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-yellow-100 rounded-md flex items-center justify-center">
                      <span className="text-yellow-600">💰</span>
                    </div>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">Monthly Revenue</dt>
                      <dd className="text-lg font-medium text-gray-900">$247</dd>
                    </dl>
                  </div>
                </div>
              </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card className="p-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Signups</h3>
                <div className="space-y-3">
                  {planners.slice(0, 3).map((planner) => (
                    <div key={planner.id} className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-900">{planner.companyName}</p>
                        <p className="text-sm text-gray-500">{planner.email}</p>
                      </div>
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        Active
                      </span>
                    </div>
                  ))}
                </div>
              </Card>

              <Card className="p-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Plan Distribution</h3>
                <div className="space-y-3">
                  {plans.map((plan) => (
                    <div key={plan.id} className="flex items-center justify-between">
                      <span className="text-sm text-gray-900">{plan.name}</span>
                      <span className="text-sm text-gray-500">
                        {plan.name === 'Professional' ? '1 user' : '0 users'}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        )}

        {activeTab === 'plans' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold text-gray-900">Subscription Plans</h2>
              <button
                onClick={handleCreatePlan}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
              >
                Create New Plan
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {plans.map((plan) => (
                <Card key={plan.id} className="p-6">
                  <div className="flex justify-between items-start mb-4">
                    <h3 className="text-xl font-semibold">{plan.name}</h3>
                    <span className={`px-2 py-1 rounded text-xs ${
                      plan.isActive ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {plan.isActive ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  
                  <div className="text-3xl font-bold text-blue-600 mb-4">
                    {plan.price === 0 ? 'Free' : `$${plan.price}/month`}
                  </div>
                  
                  <ul className="space-y-2 mb-6">
                    {plan.features.slice(0, 3).map((feature, idx) => (
                      <li key={idx} className="text-sm text-gray-600 flex items-center">
                        <span className="text-green-500 mr-2">✓</span>
                        {feature}
                      </li>
                    ))}
                    {plan.features.length > 3 && (
                      <li className="text-sm text-gray-500">
                        +{plan.features.length - 3} more features
                      </li>
                    )}
                  </ul>
                  
                  <div className="text-xs text-gray-500 space-y-1 mb-4">
                    <p>Max Weddings: {plan.maxWeddings === -1 ? 'Unlimited' : plan.maxWeddings}</p>
                    <p>AI Credits: {plan.aiCreditsMonthly}/month</p>
                    <p>Storage: {plan.storageGb}GB</p>
                  </div>
                  
                  <button className="w-full bg-gray-100 text-gray-800 py-2 px-4 rounded hover:bg-gray-200 transition-colors">
                    Edit Plan
                  </button>
                </Card>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'content' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold text-gray-900">SAAS Landing Page Content</h2>
              <button className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
                Add New Section
              </button>
            </div>

            <div className="space-y-4">
              {contentSections.map((section) => (
                <Card key={section.id} className="p-6">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center mb-2">
                        <h3 className="text-lg font-semibold capitalize">{section.section.replace('_', ' ')}</h3>
                        <span className={`ml-3 px-2 py-1 rounded text-xs ${
                          section.isActive ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {section.isActive ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                      <p className="text-gray-600 text-sm mb-2">
                        {typeof section.content === 'object' && section.content.title 
                          ? section.content.title 
                          : `${section.section} section content`}
                      </p>
                      <p className="text-xs text-gray-500">
                        Last updated: {new Date(section.updatedAt).toLocaleDateString()} by {section.updatedBy}
                      </p>
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => handleEditContent(section.id)}
                        className="bg-blue-100 text-blue-700 px-3 py-1 rounded text-sm hover:bg-blue-200 transition-colors"
                      >
                        Edit
                      </button>
                      <button className="bg-gray-100 text-gray-700 px-3 py-1 rounded text-sm hover:bg-gray-200 transition-colors">
                        Preview
                      </button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'planners' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold text-gray-900">Wedding Planners</h2>
              <button
                onClick={handleCreatePlanner}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
              >
                Create New Planner
              </button>
            </div>

            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Company & Email
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Plan
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Last Login
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {planners.map((planner) => (
                      <tr key={planner.id}>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900">{planner.companyName}</div>
                            <div className="text-sm text-gray-500">{planner.email}</div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            {plans.find(p => p.id === planner.subscriptionPlanId)?.name || 'Unknown'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            planner.isActive && planner.subscriptionStatus === 'active'
                              ? 'bg-green-100 text-green-800'
                              : 'bg-red-100 text-red-800'
                          }`}>
                            {planner.isActive && planner.subscriptionStatus === 'active' ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {planner.lastLogin 
                            ? new Date(planner.lastLogin).toLocaleDateString()
                            : 'Never'
                          }
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                          <button
                            onClick={() => handleTogglePlannerStatus(planner.id)}
                            className={`${
                              planner.isActive ? 'text-red-600 hover:text-red-900' : 'text-green-600 hover:text-green-900'
                            }`}
                          >
                            {planner.isActive ? 'Deactivate' : 'Activate'}
                          </button>
                          <button className="text-blue-600 hover:text-blue-900">
                            Edit
                          </button>
                          <button className="text-gray-600 hover:text-gray-900">
                            View Weddings
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};

export default SaasAdminDashboard;