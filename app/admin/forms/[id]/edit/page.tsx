'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { FormBuilder } from '@/components/forms/FormBuilder';
import { FormPreview } from '@/components/forms/FormPreview';

interface FormField {
  id: string;
  label: string;
  type: string;
  placeholder?: string;
  required: boolean;
  description?: string;
  options?: string[];
  order: number;
}

interface FormSettings {
  title: string;
  description?: string;
  submit_button_text: string;
  success_message: string;
  is_public: boolean;
}

interface Form {
  id: string;
  name: string;
  settings: FormSettings;
  fields: FormField[];
  is_active: boolean;
}

export default function FormEditPage() {
  const params = useParams();
  const router = useRouter();
  const { token } = useAdmin();
  const formId = params.id as string;

  const [form, setForm] = useState<Form | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'builder' | 'preview'>('builder');
  const [successMessage, setSuccessMessage] = useState('');
  const [lastSaved, setLastSaved] = useState<Date | null>(null);

  useEffect(() => {
    if (!token || !formId) return;
    fetchForm();
  }, [token, formId]);

  const fetchForm = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL!;
      const response = await fetch(`${baseUrl}/admin/forms/${formId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setForm(data);
      } else {
        setError('Failed to load form');
      }
    } catch (error) {
      setError('Failed to load form');
    } finally {
      setLoading(false);
    }
  };

  const saveForm = async () => {
    if (!form) return;

    setSaving(true);
    setError('');

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL!;
      const response = await fetch(`${baseUrl}/admin/forms/${formId}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: form.name,
          settings: form.settings,
          fields: form.fields,
          is_active: form.is_active
        }),
      });

      if (response.ok) {
        setSuccessMessage('Form saved successfully!');
        setLastSaved(new Date());
        setError('');
        
        // Clear success message after 3 seconds
        setTimeout(() => setSuccessMessage(''), 3000);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to save form');
        setSuccessMessage('');
      }
    } catch (error) {
      setError('Failed to save form');
    } finally {
      setSaving(false);
    }
  };

  const updateForm = (updates: Partial<Form>) => {
    if (form) {
      setForm({ ...form, ...updates });
    }
  };

  const updateFormSettings = (settings: FormSettings) => {
    updateForm({ settings });
  };

  const updateFormFields = (fields: FormField[]) => {
    updateForm({ fields });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-300">Loading form...</p>
        </div>
      </div>
    );
  }

  if (error && !form) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center bg-white dark:bg-gray-800 p-8 rounded-lg shadow-sm max-w-md">
          <div className="text-4xl mb-4 text-yellow-500 font-bold">!</div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Unable to Load Form</h2>
          <p className="text-gray-600 dark:text-gray-300 mb-4">{error}</p>
          <button
            onClick={() => router.push('/admin/forms')}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
          >
            Back to Forms
          </button>
        </div>
      </div>
    );
  }

  if (!form) return null;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => router.push('/admin/forms')}
              className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            >
              ← Back to Forms
            </button>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Edit Form</h1>
              <p className="text-gray-600 dark:text-gray-300">{form.name}</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="flex rounded-lg bg-gray-100 dark:bg-gray-700 p-1">
              <button
                onClick={() => setActiveTab('builder')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'builder'
                    ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm'
                    : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100'
                }`}
              >
                Builder
              </button>
              <button
                onClick={() => setActiveTab('preview')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'preview'
                    ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm'
                    : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100'
                }`}
              >
                Preview
              </button>
            </div>
            
            <div className="flex items-center space-x-3">
              {lastSaved && (
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  Last saved: {lastSaved.toLocaleTimeString()}
                </span>
              )}
              
              <button
                onClick={saveForm}
                disabled={saving}
                className="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center"
              >
                {saving ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Saving...
                  </>
                ) : (
                  'Save Form'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Status Messages */}
      {error && (
        <div className="mx-6 mt-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <div className="flex items-center">
            <svg className="w-5 h-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-red-600 dark:text-red-300">{error}</p>
          </div>
        </div>
      )}
      
      {successMessage && (
        <div className="mx-6 mt-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
          <div className="flex items-center">
            <svg className="w-5 h-5 text-green-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-green-600 dark:text-green-300">{successMessage}</p>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1">
        {activeTab === 'builder' ? (
          <FormBuilder
            form={form}
            onUpdateSettings={updateFormSettings}
            onUpdateFields={updateFormFields}
          />
        ) : (
          <FormPreview
            form={form}
          />
        )}
      </div>
    </div>
  );
}