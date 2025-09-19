'use client';

import { useState, useEffect } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';
import { Button } from '../../../components/ui/button';
import { Card } from '../../../components/ui/Card';
import { budgetApi } from '../../../services/budgetApi';
import type { BudgetTemplate } from '../../../types/budget';

interface Wedding {
  id?: string;
  _id?: string;
  couple_names: string;
  date: string;
  slug: string;
}

export default function BudgetTemplatesPage() {
  const { token } = useAdmin();
  const [templates, setTemplates] = useState<BudgetTemplate[]>([]);
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  
  // Apply template modal
  const [showApplyModal, setShowApplyModal] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<BudgetTemplate | null>(null);
  const [selectedWedding, setSelectedWedding] = useState<string>('');
  const [totalBudget, setTotalBudget] = useState<number>(0);

  useEffect(() => {
    if (token) {
      fetchTemplates();
      fetchWeddings();
    }
  }, [token]);

  const fetchTemplates = async () => {
    if (!token) return;
    
    setLoading(true);
    try {
      const templatesData = await budgetApi.getBudgetTemplates(token);
      setTemplates(templatesData);
      setError('');
    } catch (err: any) {
      setError(err.message || 'Failed to load budget templates');
      toast.error(err.message || 'Failed to load budget templates');
    } finally {
      setLoading(false);
    }
  };

  const fetchWeddings = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL!;
      const response = await fetch(`${baseUrl}/weddings`);
      const data = await response.json();
      setWeddings(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load weddings');
    }
  };

  const handleApplyTemplate = async () => {
    if (!token || !selectedTemplate || !selectedWedding || !totalBudget) {
      toast.error('Please fill in all required fields');
      return;
    }

    try {
      await budgetApi.applyBudgetTemplate(token, selectedWedding, selectedTemplate.id, totalBudget);
      toast.success('Budget template applied successfully');
      setShowApplyModal(false);
      resetApplyForm();
    } catch (err: any) {
      toast.error(err.message || 'Failed to apply budget template');
    }
  };

  const resetApplyForm = () => {
    setSelectedTemplate(null);
    setSelectedWedding('');
    setTotalBudget(0);
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const getWeddingTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      'traditional': 'bg-blue-100 text-blue-800',
      'modern': 'bg-purple-100 text-purple-800',
      'destination': 'bg-green-100 text-green-800',
      'intimate': 'bg-pink-100 text-pink-800',
      'outdoor': 'bg-yellow-100 text-yellow-800',
      'luxury': 'bg-indigo-100 text-indigo-800',
      'budget': 'bg-gray-100 text-gray-800',
    };
    return colors[type.toLowerCase()] || 'bg-gray-100 text-gray-800';
  };

  if (!token) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-wedding-navy mb-4">Access Denied</h2>
          <p>Please log in to access budget templates.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-heading font-bold text-wedding-navy">
            Budget Templates
          </h1>
          <p className="text-gray-600 mt-1">
            Pre-built budget templates for different wedding types and sizes
          </p>
        </div>
        
        <div className="flex gap-3">
          <Button className="bg-purple-600 hover:bg-purple-700">
            Create Custom Template
          </Button>
        </div>
      </div>

      {/* Templates Grid */}
      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-wedding-rose"></div>
          <p className="mt-2 text-gray-600">Loading budget templates...</p>
        </div>
      ) : error ? (
        <Card className="p-8 text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <Button onClick={fetchTemplates}>Retry</Button>
        </Card>
      ) : templates.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-gray-600 mb-4">
            No budget templates available at this time.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((template) => (
            <Card key={template.id} className="p-6">
              {/* Header */}
              <div className="flex justify-between items-start mb-4">
                <div className="flex-1">
                  <h3 className="font-semibold text-wedding-navy text-xl mb-2">
                    {template.name}
                  </h3>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getWeddingTypeColor(template.wedding_type)}`}>
                    {template.wedding_type.charAt(0).toUpperCase() + template.wedding_type.slice(1)}
                  </span>
                </div>
                
                {template.is_public && (
                  <div className="bg-green-100 text-green-800 px-2 py-1 rounded-full text-xs font-medium">
                    Public
                  </div>
                )}
              </div>

              {/* Description */}
              {template.description && (
                <p className="text-gray-600 text-sm mb-4">
                  {template.description}
                </p>
              )}

              {/* Budget Range */}
              <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                <div className="text-sm text-gray-600 mb-1">Recommended Budget Range</div>
                <div className="font-semibold text-wedding-navy">
                  {formatCurrency(template.target_budget_min)} - {formatCurrency(template.target_budget_max)}
                </div>
              </div>

              {/* Guest Count Range */}
              <div className="mb-4 p-3 bg-blue-50 rounded-lg">
                <div className="text-sm text-gray-600 mb-1">Guest Count Range</div>
                <div className="font-semibold text-blue-700">
                  {template.guest_count_range.min} - {template.guest_count_range.max} guests
                </div>
              </div>

              {/* Categories Preview */}
              <div className="mb-4">
                <h4 className="font-medium text-wedding-navy mb-2">Budget Categories</h4>
                <div className="space-y-2">
                  {template.categories.slice(0, 4).map((category, index) => (
                    <div key={index} className="flex justify-between items-center text-sm">
                      <span className="text-gray-700">{category.name}</span>
                      <div className="flex items-center">
                        <span className="font-medium text-wedding-rose mr-2">
                          {category.percentage}%
                        </span>
                        <div className="flex items-center">
                          {Array.from({ length: category.priority }, (_, i) => (
                            <svg key={i} className="w-3 h-3 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                            </svg>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                  {template.categories.length > 4 && (
                    <div className="text-xs text-gray-500 text-center">
                      +{template.categories.length - 4} more categories
                    </div>
                  )}
                </div>
              </div>

              {/* Apply Button */}
              <Button
                onClick={() => {
                  setSelectedTemplate(template);
                  setShowApplyModal(true);
                }}
                className="w-full"
              >
                Apply Template
              </Button>

              {/* Template Info */}
              <div className="mt-4 text-xs text-gray-500 text-center border-t border-gray-200 pt-3">
                {template.created_by && (
                  <div>Created by: {template.created_by}</div>
                )}
                <div>Created: {new Date(template.created_at).toLocaleDateString()}</div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Apply Template Modal */}
      {showApplyModal && selectedTemplate && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full">
            <h2 className="text-xl font-bold mb-4 text-wedding-navy">
              Apply Template: {selectedTemplate.name}
            </h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Select Wedding *
                </label>
                <select
                  value={selectedWedding}
                  onChange={(e) => setSelectedWedding(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  required
                >
                  <option value="">Choose a wedding...</option>
                  {weddings.map((wedding) => (
                    <option key={wedding._id || wedding.id} value={wedding._id || wedding.id}>
                      {wedding.couple_names} - {new Date(wedding.date).toLocaleDateString()}
                    </option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Total Budget Amount *
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={totalBudget}
                  onChange={(e) => setTotalBudget(parseFloat(e.target.value) || 0)}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  placeholder="Enter total budget amount..."
                  required
                />
                <div className="text-xs text-gray-500 mt-1">
                  Recommended: {formatCurrency(selectedTemplate.target_budget_min)} - {formatCurrency(selectedTemplate.target_budget_max)}
                </div>
              </div>
              
              {/* Template Preview */}
              <div className="border border-gray-200 rounded-lg p-3">
                <div className="text-sm font-medium text-gray-700 mb-2">Budget Breakdown Preview:</div>
                <div className="space-y-1 text-xs">
                  {selectedTemplate.categories.map((category, index) => (
                    <div key={index} className="flex justify-between">
                      <span>{category.name}</span>
                      <span className="font-medium">
                        {formatCurrency(totalBudget * (category.percentage / 100))} ({category.percentage}%)
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                <div className="flex items-start">
                  <svg className="w-5 h-5 text-yellow-600 mr-2 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <div className="text-yellow-800 text-sm">
                    <strong>Note:</strong> This will create new budget categories for the selected wedding. 
                    Existing categories will not be affected.
                  </div>
                </div>
              </div>
            </div>
            
            <div className="flex gap-3 mt-6">
              <Button 
                onClick={handleApplyTemplate} 
                className="flex-1"
                disabled={!selectedWedding || !totalBudget}
              >
                Apply Template
              </Button>
              <Button 
                variant="danger" 
                onClick={() => {
                  setShowApplyModal(false);
                  resetApplyForm();
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}