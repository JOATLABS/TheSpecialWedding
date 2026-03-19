'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useParams, useSearchParams } from 'next/navigation';

interface FormField {
  id: string;
  label: string;
  type: 'text' | 'email' | 'phone' | 'textarea' | 'number' | 'date' | 'select' | 'checkbox' | 'file';
  required: boolean;
  options?: string[];
  placeholder?: string;
}

interface VendorForm {
  _id: string;
  form_name: string;
  vendor_name: string;
  vendor_type: string;
  fields: FormField[];
  status: string;
  wedding: {
    couple_names: string;
    date: string;
  };
}

export default function PublicVendorFormPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const formId = params.form_id as string;
  const token = searchParams.get('token');

  const [form, setForm] = useState<VendorForm | null>(null);
  const [formData, setFormData] = useState<{[key: string]: any}>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const fetchForm = useCallback(async (id: string, inviteToken: string) => {
    const baseUrl = getApiBaseUrl();
    const response = await fetch(`${baseUrl}/vendor-form/${id}/public?token=${inviteToken}`);

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Form not found or link has expired.');
      }
      throw new Error('Failed to load form.');
    }

    return (await response.json()) as VendorForm;
  }, []);

  useEffect(() => {
    if (!formId || !token) {
      setError('This form link isn\u2019t valid. Check the email from your wedding planner for the correct link.');
      setLoading(false);
      return;
    }

    let isActive = true;

    const loadForm = async () => {
      setLoading(true);
      try {
        const data = await fetchForm(formId, token);
        if (!isActive) return;

        setForm(data);
        setSubmitted(data.status === 'submitted');

        const initialData: {[key: string]: any} = {};
        data.fields.forEach((field: FormField) => {
          if (field.type === 'checkbox') {
            initialData[field.id] = [];
          } else {
            initialData[field.id] = '';
          }
        });
        setFormData(initialData);
        setError('');
      } catch (err) {
        if (!isActive) return;
        setForm(null);
        setError(err instanceof Error ? err.message : 'Failed to load form');
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    loadForm();

    return () => {
      isActive = false;
    };
  }, [formId, token, fetchForm]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');

    try {
      // Validate required fields
      for (const field of form!.fields) {
        if (field.required && (!formData[field.id] || formData[field.id] === '')) {
          throw new Error(`${field.label} is required`);
        }
      }

      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/vendor-form/${formId}/submit?token=${token}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to submit form');
      }

      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit form');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFieldChange = (fieldId: string, value: any, fieldType: string) => {
    if (fieldType === 'checkbox') {
      const currentValues = formData[fieldId] || [];
      const newValues = currentValues.includes(value)
        ? currentValues.filter((v: any) => v !== value)
        : [...currentValues, value];
      setFormData({ ...formData, [fieldId]: newValues });
    } else {
      setFormData({ ...formData, [fieldId]: value });
    }
  };

  const renderField = (field: FormField) => {
    const baseClasses = "w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent";

    switch (field.type) {
      case 'textarea':
        return (
          <textarea
            value={formData[field.id] || ''}
            onChange={(e) => handleFieldChange(field.id, e.target.value, field.type)}
            className={`${baseClasses} min-h-[100px]`}
            placeholder={field.placeholder}
            required={field.required}
            rows={4}
          />
        );

      case 'select':
        return (
          <select
            value={formData[field.id] || ''}
            onChange={(e) => handleFieldChange(field.id, e.target.value, field.type)}
            className={baseClasses}
            required={field.required}
          >
            <option value="">Select an option...</option>
            {field.options?.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        );

      case 'checkbox':
        return (
          <div className="space-y-2">
            {field.options?.map((option) => (
              <label key={option} className="flex items-center">
                <input
                  type="checkbox"
                  checked={(formData[field.id] || []).includes(option)}
                  onChange={(e) => handleFieldChange(field.id, option, field.type)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">{option}</span>
              </label>
            ))}
          </div>
        );

      case 'number':
        return (
          <input
            type="number"
            value={formData[field.id] || ''}
            onChange={(e) => handleFieldChange(field.id, e.target.value, field.type)}
            className={baseClasses}
            placeholder={field.placeholder}
            required={field.required}
          />
        );

      case 'date':
        return (
          <input
            type="date"
            value={formData[field.id] || ''}
            onChange={(e) => handleFieldChange(field.id, e.target.value, field.type)}
            className={baseClasses}
            required={field.required}
          />
        );

      case 'email':
        return (
          <input
            type="email"
            value={formData[field.id] || ''}
            onChange={(e) => handleFieldChange(field.id, e.target.value, field.type)}
            className={baseClasses}
            placeholder={field.placeholder}
            required={field.required}
          />
        );

      case 'phone':
        return (
          <input
            type="tel"
            value={formData[field.id] || ''}
            onChange={(e) => handleFieldChange(field.id, e.target.value, field.type)}
            className={baseClasses}
            placeholder={field.placeholder}
            required={field.required}
          />
        );

      default:
        return (
          <input
            type="text"
            value={formData[field.id] || ''}
            onChange={(e) => handleFieldChange(field.id, e.target.value, field.type)}
            className={baseClasses}
            placeholder={field.placeholder}
            required={field.required}
          />
        );
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading form...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md mx-auto text-center p-6">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <div className="text-red-600 mb-4">
              <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-red-900 mb-2">Unable to Load Form</h2>
            <p className="text-red-700">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md mx-auto text-center p-6">
          <div className="bg-green-50 border border-green-200 rounded-lg p-6">
            <div className="text-green-600 mb-4">
              <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-green-900 mb-2">Form Submitted Successfully!</h2>
            <p className="text-green-700 mb-4">
              Thank you for submitting your information. The wedding planner will review your submission and get back to you soon.
            </p>
            <p className="text-sm text-green-600">
              You can close this page now.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-lg overflow-hidden mb-8">
          <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-8 text-white text-center">
            <h1 className="text-2xl sm:text-3xl font-bold mb-2">Wedding Service Request</h1>
            <p className="text-blue-100">Please provide your service information</p>
          </div>
          <div className="px-6 py-4 bg-blue-50 border-b">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium text-gray-700">Wedding:</span>
                <span className="ml-2 text-gray-900">{form?.wedding.couple_names}</span>
              </div>
              <div>
                <span className="font-medium text-gray-700">Date:</span>
                <span className="ml-2 text-gray-900">{form?.wedding.date}</span>
              </div>
              <div>
                <span className="font-medium text-gray-700">Service:</span>
                <span className="ml-2 text-gray-900">{form?.vendor_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
              </div>
              <div>
                <span className="font-medium text-gray-700">Vendor:</span>
                <span className="ml-2 text-gray-900">{form?.vendor_name}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Form */}
        <div className="bg-white rounded-lg shadow-lg p-6 sm:p-8">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-gray-900 mb-2">{form?.form_name}</h2>
            <p className="text-gray-600">
              Please fill out all required fields marked with an asterisk (*). This information will help us understand your services and pricing.
            </p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-700">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {form?.fields.map((field) => (
              <div key={field.id}>
                <label htmlFor={field.id} className="block text-sm font-medium text-gray-700 mb-2">
                  {field.label}
                  {field.required && <span className="text-red-500 ml-1">*</span>}
                </label>
                {renderField(field)}
                {field.type === 'checkbox' && field.required && (
                  <p className="mt-1 text-xs text-gray-500">Please select at least one option.</p>
                )}
              </div>
            ))}

            <div className="pt-6 border-t border-gray-200">
              <button
                type="submit"
                disabled={submitting}
                className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 px-6 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
              >
                {submitting ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Submitting...
                  </span>
                ) : (
                  'Submit Information'
                )}
              </button>
            </div>
          </form>

          <div className="mt-6 pt-6 border-t border-gray-200 text-center text-sm text-gray-500">
            <p>This form is secure and your information will only be shared with the wedding planning team.</p>
          </div>
        </div>
      </div>
    </div>
  );
}