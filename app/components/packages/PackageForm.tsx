'use client';

import { useState } from 'react';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import {
  Plus,
  Trash2,
  GripVertical,
  ChevronDown,
  ChevronUp,
  Calendar,
  DollarSign,
  Percent,
  AlertCircle
} from 'lucide-react';
import AIPricingSuggestion from './AIPricingSuggestion';

// Types
export interface ServiceItem {
  name: string;
  description: string;
  included: boolean;
}

export interface ScheduleItem {
  name: string;
  trigger: 'on_signing' | 'days_after_signing' | 'days_before_wedding' | 'fixed_date';
  days_after?: number;
  days_before?: number;
  fixed_date?: string;
  amount?: number;
  percentage?: number;
}

export interface PackageFormData {
  name: string;
  description: string;
  services: ServiceItem[];
  total_amount: number;
  currency: string;
  payment_schedule: ScheduleItem[];
  cancellation_policy: string;
  late_payment_policy: string;
  custom_terms: string;
  is_template: boolean;
}

interface PackageFormProps {
  initialData?: Partial<PackageFormData>;
  onSubmit: (data: PackageFormData, status: 'draft' | 'active') => Promise<void>;
  token?: string;
  isSubmitting: boolean;
  mode: 'create' | 'edit';
}

const CANCELLATION_PRESETS = [
  { value: '', label: 'Select a policy...' },
  { value: 'flexible', label: 'Flexible - Full refund up to 30 days before' },
  { value: 'moderate', label: 'Moderate - 50% refund up to 14 days before' },
  { value: 'strict', label: 'Strict - No refunds after signing' },
  { value: 'custom', label: 'Custom policy' }
];

const TRIGGER_OPTIONS = [
  { value: 'on_signing', label: 'On signing' },
  { value: 'days_after_signing', label: 'Days after signing' },
  { value: 'days_before_wedding', label: 'Days before wedding' },
  { value: 'fixed_date', label: 'Fixed date' }
];

const defaultFormData: PackageFormData = {
  name: '',
  description: '',
  services: [],
  total_amount: 0,
  currency: 'usd',
  payment_schedule: [],
  cancellation_policy: '',
  late_payment_policy: '',
  custom_terms: '',
  is_template: false
};

export default function PackageForm({ initialData, onSubmit, isSubmitting, mode, token }: PackageFormProps) {
  const [formData, setFormData] = useState<PackageFormData>({
    ...defaultFormData,
    ...initialData
  });

  const [expandedSections, setExpandedSections] = useState({
    services: true,
    schedule: true,
    terms: false
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  // Toggle section expansion
  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Service handlers
  const addService = () => {
    setFormData(prev => ({
      ...prev,
      services: [...prev.services, { name: '', description: '', included: true }]
    }));
  };

  const updateService = (index: number, field: keyof ServiceItem, value: string | boolean) => {
    setFormData(prev => ({
      ...prev,
      services: prev.services.map((s, i) =>
        i === index ? { ...s, [field]: value } : s
      )
    }));
  };

  const removeService = (index: number) => {
    setFormData(prev => ({
      ...prev,
      services: prev.services.filter((_, i) => i !== index)
    }));
  };

  // Schedule handlers
  const addScheduleItem = () => {
    setFormData(prev => ({
      ...prev,
      payment_schedule: [
        ...prev.payment_schedule,
        { name: '', trigger: 'on_signing', percentage: 0 }
      ]
    }));
  };

  const updateScheduleItem = (index: number, field: keyof ScheduleItem, value: string | number) => {
    setFormData(prev => ({
      ...prev,
      payment_schedule: prev.payment_schedule.map((item, i) =>
        i === index ? { ...item, [field]: value } : item
      )
    }));
  };

  const removeScheduleItem = (index: number) => {
    setFormData(prev => ({
      ...prev,
      payment_schedule: prev.payment_schedule.filter((_, i) => i !== index)
    }));
  };

  // Calculate schedule total percentage
  const scheduleTotal = formData.payment_schedule.reduce((sum, item) => {
    return sum + (item.percentage || 0);
  }, 0);

  // Validation
  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Package name is required';
    }

    if (formData.total_amount <= 0) {
      newErrors.total_amount = 'Total amount must be greater than 0';
    }

    if (formData.payment_schedule.length > 0 && Math.abs(scheduleTotal - 100) > 0.01) {
      newErrors.schedule = `Schedule percentages must add up to 100% (currently ${scheduleTotal}%)`;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (status: 'draft' | 'active') => {
    if (!validate()) return;
    await onSubmit(formData, status);
  };

  return (
    <div className="space-y-6">
      {/* Basic Info */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
          Basic Information
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Package Name *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              placeholder="e.g., Full Wedding Planning Package"
              className={`w-full px-4 py-2 rounded-lg border ${errors.name ? 'border-red-500' : 'border-slate-200 dark:border-slate-700'} bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500`}
            />
            {errors.name && (
              <p className="mt-1 text-sm text-red-500 flex items-center gap-1">
                <AlertCircle size={14} /> {errors.name}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="Describe what's included in this package..."
              rows={3}
              className="w-full px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Total Amount *
              </label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="number"
                  value={formData.total_amount || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, total_amount: parseFloat(e.target.value) || 0 }))}
                  placeholder="0.00"
                  min="0"
                  step="0.01"
                  className={`w-full pl-10 pr-4 py-2 rounded-lg border ${errors.total_amount ? 'border-red-500' : 'border-slate-200 dark:border-slate-700'} bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500`}
                />
              </div>
              {errors.total_amount && (
                <p className="mt-1 text-sm text-red-500 flex items-center gap-1">
                  <AlertCircle size={14} /> {errors.total_amount}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Currency
              </label>
              <select
                value={formData.currency}
                onChange={(e) => setFormData(prev => ({ ...prev, currency: e.target.value }))}
                className="w-full px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500"
              >
                <option value="usd">USD ($)</option>
                <option value="eur">EUR (&euro;)</option>
                <option value="gbp">GBP (&pound;)</option>
              </select>
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.is_template}
              onChange={(e) => setFormData(prev => ({ ...prev, is_template: e.target.checked }))}
              className="w-4 h-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm text-slate-600 dark:text-slate-400">
              Save as template for future use
            </span>
          </label>
        </div>
      </Card>

      {/* AI Pricing Suggestion */}
      {token && formData.services.length > 0 && (
        <AIPricingSuggestion
          token={token}
          services={formData.services}
          currentPrice={formData.total_amount}
          currency={formData.currency}
          onApplyPrice={(price) => setFormData(prev => ({ ...prev, total_amount: price }))}
          onApplySchedule={(schedule) => setFormData(prev => ({
            ...prev,
            payment_schedule: schedule.map(s => ({
              name: s.name,
              trigger: s.trigger as ScheduleItem['trigger'],
              percentage: s.percentage,
              days_after: s.days_after,
              days_before: s.days_before
            }))
          }))}
        />
      )}

      {/* Services Section */}
      <Card className="overflow-hidden">
        <button
          type="button"
          onClick={() => toggleSection('services')}
          className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-50 dark:hover:bg-slate-800/50"
        >
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
            Services ({formData.services.length})
          </h2>
          {expandedSections.services ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>

        {expandedSections.services && (
          <div className="p-4 pt-0 space-y-4">
            {formData.services.map((service, index) => (
              <div
                key={index}
                className="flex gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg"
              >
                <GripVertical className="w-5 h-5 text-slate-400 mt-2 cursor-move" />

                <div className="flex-1 space-y-3">
                  <input
                    type="text"
                    value={service.name}
                    onChange={(e) => updateService(index, 'name', e.target.value)}
                    placeholder="Service name"
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm"
                  />
                  <input
                    type="text"
                    value={service.description}
                    onChange={(e) => updateService(index, 'description', e.target.value)}
                    placeholder="Description (optional)"
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm"
                  />
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={service.included}
                      onChange={(e) => updateService(index, 'included', e.target.checked)}
                      className="w-4 h-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-sm text-slate-600 dark:text-slate-400">
                      Included in package
                    </span>
                  </label>
                </div>

                <button
                  type="button"
                  onClick={() => removeService(index)}
                  className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg h-fit"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            ))}

            <Button
              type="button"
              variant="outline"
              onClick={addService}
              className="w-full flex items-center justify-center gap-2"
            >
              <Plus size={18} />
              Add Service
            </Button>
          </div>
        )}
      </Card>

      {/* Payment Schedule Section */}
      <Card className="overflow-hidden">
        <button
          type="button"
          onClick={() => toggleSection('schedule')}
          className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-50 dark:hover:bg-slate-800/50"
        >
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
              Payment Schedule ({formData.payment_schedule.length})
            </h2>
            {formData.payment_schedule.length > 0 && (
              <p className={`text-sm ${Math.abs(scheduleTotal - 100) < 0.01 ? 'text-green-600' : 'text-amber-600'}`}>
                Total: {scheduleTotal}%
              </p>
            )}
          </div>
          {expandedSections.schedule ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>

        {expandedSections.schedule && (
          <div className="p-4 pt-0 space-y-4">
            {errors.schedule && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm flex items-center gap-2">
                <AlertCircle size={16} />
                {errors.schedule}
              </div>
            )}

            {formData.payment_schedule.map((item, index) => (
              <div
                key={index}
                className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg space-y-3"
              >
                <div className="flex gap-3">
                  <div className="flex-1">
                    <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                      Payment Name
                    </label>
                    <input
                      type="text"
                      value={item.name}
                      onChange={(e) => updateScheduleItem(index, 'name', e.target.value)}
                      placeholder="e.g., Deposit, Final Payment"
                      className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm"
                    />
                  </div>

                  <div className="w-32">
                    <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                      Percentage
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        value={item.percentage || ''}
                        onChange={(e) => updateScheduleItem(index, 'percentage', parseFloat(e.target.value) || 0)}
                        placeholder="0"
                        min="0"
                        max="100"
                        className="w-full px-3 py-2 pr-8 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm"
                      />
                      <Percent className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => removeScheduleItem(index)}
                    className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg h-fit mt-5"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                      When Due
                    </label>
                    <select
                      value={item.trigger}
                      onChange={(e) => updateScheduleItem(index, 'trigger', e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm"
                    >
                      {TRIGGER_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>

                  {item.trigger === 'days_after_signing' && (
                    <div>
                      <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                        Days After Signing
                      </label>
                      <input
                        type="number"
                        value={item.days_after || ''}
                        onChange={(e) => updateScheduleItem(index, 'days_after', parseInt(e.target.value) || 0)}
                        placeholder="0"
                        min="0"
                        className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm"
                      />
                    </div>
                  )}

                  {item.trigger === 'days_before_wedding' && (
                    <div>
                      <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                        Days Before Wedding
                      </label>
                      <input
                        type="number"
                        value={item.days_before || ''}
                        onChange={(e) => updateScheduleItem(index, 'days_before', parseInt(e.target.value) || 0)}
                        placeholder="0"
                        min="0"
                        className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm"
                      />
                    </div>
                  )}

                  {item.trigger === 'fixed_date' && (
                    <div>
                      <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                        Due Date
                      </label>
                      <div className="relative">
                        <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input
                          type="date"
                          value={item.fixed_date || ''}
                          onChange={(e) => updateScheduleItem(index, 'fixed_date', e.target.value)}
                          className="w-full pl-10 pr-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm"
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Calculated amount preview */}
                {formData.total_amount > 0 && item.percentage !== undefined && item.percentage > 0 && (
                  <div className="text-sm text-slate-600 dark:text-slate-400">
                    Amount: ${((formData.total_amount * item.percentage) / 100).toFixed(2)}
                  </div>
                )}
              </div>
            ))}

            <Button
              type="button"
              variant="outline"
              onClick={addScheduleItem}
              className="w-full flex items-center justify-center gap-2"
            >
              <Plus size={18} />
              Add Payment
            </Button>

            {formData.payment_schedule.length === 0 && (
              <p className="text-sm text-slate-500 dark:text-slate-400 text-center py-4">
                No payment schedule defined. The full amount will be due on signing.
              </p>
            )}
          </div>
        )}
      </Card>

      {/* Terms Section */}
      <Card className="overflow-hidden">
        <button
          type="button"
          onClick={() => toggleSection('terms')}
          className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-50 dark:hover:bg-slate-800/50"
        >
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
            Terms & Policies
          </h2>
          {expandedSections.terms ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>

        {expandedSections.terms && (
          <div className="p-4 pt-0 space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Cancellation Policy
              </label>
              <select
                value={CANCELLATION_PRESETS.find(p => p.label.includes(formData.cancellation_policy.split(' - ')[0]))?.value || (formData.cancellation_policy ? 'custom' : '')}
                onChange={(e) => {
                  const preset = CANCELLATION_PRESETS.find(p => p.value === e.target.value);
                  if (preset && preset.value !== 'custom') {
                    setFormData(prev => ({ ...prev, cancellation_policy: preset.label }));
                  }
                }}
                className="w-full px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500 mb-2"
              >
                {CANCELLATION_PRESETS.map(preset => (
                  <option key={preset.value} value={preset.value}>{preset.label}</option>
                ))}
              </select>
              <textarea
                value={formData.cancellation_policy}
                onChange={(e) => setFormData(prev => ({ ...prev, cancellation_policy: e.target.value }))}
                placeholder="Enter your cancellation policy..."
                rows={3}
                className="w-full px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Late Payment Policy
              </label>
              <textarea
                value={formData.late_payment_policy}
                onChange={(e) => setFormData(prev => ({ ...prev, late_payment_policy: e.target.value }))}
                placeholder="e.g., A 5% late fee will be applied to payments more than 7 days overdue..."
                rows={2}
                className="w-full px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Custom Terms
              </label>
              <textarea
                value={formData.custom_terms}
                onChange={(e) => setFormData(prev => ({ ...prev, custom_terms: e.target.value }))}
                placeholder="Any additional terms and conditions..."
                rows={4}
                className="w-full px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>
        )}
      </Card>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-3 justify-end">
        <Button
          type="button"
          variant="outline"
          onClick={() => handleSubmit('draft')}
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Saving...' : 'Save as Draft'}
        </Button>
        <Button
          type="button"
          onClick={() => handleSubmit('active')}
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Saving...' : mode === 'create' ? 'Create & Activate' : 'Save & Activate'}
        </Button>
      </div>
    </div>
  );
}
