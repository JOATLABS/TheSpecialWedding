'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { ArrowLeft, Loader2, Send, CheckCircle, Eye } from 'lucide-react';
import {
  buildCoupleLoginRedirect,
  coupleFetch,
  extractApiErrorMessage,
  logoutCoupleSession,
} from '@/couple/lib/auth';

interface FormField {
  id: string;
  label: string;
  type: string;
  required?: boolean;
  placeholder?: string;
  description?: string;
  options?: string[];
  validation?: any;
}

interface FormData {
  form: {
    id: string;
    title: string;
    description?: string;
    fields: FormField[];
    created_at?: string;
  };
  existing_responses?: Record<string, any>;
  submitted_at?: string;
  read_only?: boolean;
  archived?: boolean;
  read_only_reason?: string | null;
}

export default function CoupleFormPage() {
  const params = useParams();
  const router = useRouter();
  const formId = params.formId as string;

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState<FormData | null>(null);
  const [responses, setResponses] = useState<Record<string, any>>({});
  const isReadOnly = Boolean(formData?.read_only);

  useEffect(() => {
    const fetchForm = async () => {
      try {
        const res = await coupleFetch(`/couple/portal/forms/${formId}`);

        if (res.status === 401) {
          await logoutCoupleSession();
          router.replace(buildCoupleLoginRedirect('Session expired. Please sign in again.'));
          return;
        }

        if (res.status === 403) {
          const detail = await extractApiErrorMessage(
            res,
            'This wedding portal is currently unavailable. Please contact your planner.',
          );
          await logoutCoupleSession();
          router.replace(buildCoupleLoginRedirect(detail));
          return;
        }

        if (!res.ok) {
          const detail = await extractApiErrorMessage(res, 'Failed to load form');
          toast.error(detail);
          return;
        }

        const data = await res.json();
        setFormData(data);
        if (data.existing_responses) {
          setResponses(data.existing_responses);
        }
      } catch {
        toast.error('Failed to connect to server');
      } finally {
        setLoading(false);
      }
    };

    fetchForm();
  }, [formId, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isReadOnly) return;

    setSubmitting(true);
    try {
      const res = await coupleFetch('/couple/portal/forms/submit', {
        method: 'POST',
        body: JSON.stringify({ form_id: formId, responses }),
      });

      if (res.status === 401) {
        await logoutCoupleSession();
        router.replace(buildCoupleLoginRedirect('Session expired. Please sign in again.'));
        return;
      }

      if (res.status === 403) {
        const detail = await extractApiErrorMessage(
          res,
          'This wedding portal is currently unavailable. Please contact your planner.',
        );
        if (detail.toLowerCase().includes('archived')) {
          setFormData((current) =>
            current
              ? {
                  ...current,
                  read_only: true,
                  archived: true,
                  read_only_reason: detail,
                }
              : current,
          );
          toast.error(detail);
        } else {
          await logoutCoupleSession();
          router.replace(buildCoupleLoginRedirect(detail));
        }
        return;
      }

      if (!res.ok) {
        const detail = await extractApiErrorMessage(res, 'Failed to submit form');
        toast.error(detail);
        return;
      }

      toast.success('Form submitted successfully!');
      router.push('/couple/dashboard');
    } catch {
      toast.error('Failed to submit form');
    } finally {
      setSubmitting(false);
    }
  };

  const updateResponse = (fieldId: string, value: any) => {
    setResponses(prev => ({ ...prev, [fieldId]: value }));
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-[#1e3a5f]" />
      </div>
    );
  }

  if (!formData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Form not found</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Back Button */}
        <button
          onClick={() => router.push('/couple/dashboard')}
          className="flex items-center gap-2 text-gray-500 hover:text-gray-700 mb-6 text-sm"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </button>

        {/* Form Header */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-6">
          <h1 className="text-2xl font-serif text-[#1e3a5f] mb-2">{formData.form.title}</h1>
          {formData.form.description && (
            <p className="text-gray-500">{formData.form.description}</p>
          )}
          {formData.read_only && (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
              <Eye className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <span>{formData.read_only_reason || 'This form is view-only because the wedding has been archived.'}</span>
            </div>
          )}
          {!formData.read_only && formData.submitted_at && (
            <div className="flex items-center gap-2 mt-3 text-sm text-green-600">
              <CheckCircle className="w-4 h-4" />
              Previously submitted — you can update your responses
            </div>
          )}
          {formData.read_only && formData.submitted_at && (
            <div className="flex items-center gap-2 mt-3 text-sm text-slate-500">
              <CheckCircle className="w-4 h-4" />
              Previously submitted — responses are shown below in read-only mode
            </div>
          )}
        </div>

        {/* Form Fields */}
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            {formData.form.fields.map((field) => (
              <div key={field.id} className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  {field.label}
                  {field.required && <span className="text-red-400 ml-1">*</span>}
                </label>
                {field.description && (
                  <p className="text-xs text-gray-400 mb-2">{field.description}</p>
                )}

                {/* Text/Email/Phone/Number */}
                {['text', 'email', 'phone', 'number'].includes(field.type) && (
                  <input
                    type={field.type === 'phone' ? 'tel' : field.type}
                    value={responses[field.id] || ''}
                    onChange={(e) => updateResponse(field.id, e.target.value)}
                    placeholder={field.placeholder}
                    required={field.required}
                    disabled={isReadOnly}
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] text-gray-800"
                  />
                )}

                {/* Date */}
                {field.type === 'date' && (
                  <input
                    type="date"
                    value={responses[field.id] || ''}
                    onChange={(e) => updateResponse(field.id, e.target.value)}
                    required={field.required}
                    disabled={isReadOnly}
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] text-gray-800"
                  />
                )}

                {/* Textarea */}
                {field.type === 'textarea' && (
                  <textarea
                    value={responses[field.id] || ''}
                    onChange={(e) => updateResponse(field.id, e.target.value)}
                    placeholder={field.placeholder}
                    required={field.required}
                    rows={4}
                    disabled={isReadOnly}
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] text-gray-800 resize-none"
                  />
                )}

                {/* Select */}
                {field.type === 'select' && (
                  <select
                    value={responses[field.id] || ''}
                    onChange={(e) => updateResponse(field.id, e.target.value)}
                    required={field.required}
                    disabled={isReadOnly}
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] text-gray-800"
                  >
                    <option value="">Select an option</option>
                    {field.options?.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                )}

                {/* Checkbox */}
                {field.type === 'checkbox' && (
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={responses[field.id] || false}
                      onChange={(e) => updateResponse(field.id, e.target.checked)}
                      disabled={isReadOnly}
                      className="w-5 h-5 rounded border-gray-300 text-[#1e3a5f] focus:ring-[#1e3a5f]"
                    />
                    <span className="text-sm text-gray-600">{field.placeholder || 'Yes'}</span>
                  </label>
                )}
              </div>
            ))}
          </div>

          {/* Submit */}
          {formData.read_only ? (
            <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              This form is view-only. New submissions and edits are disabled for archived weddings.
            </div>
          ) : (
            <div className="mt-6">
              <button
                type="submit"
                disabled={submitting}
                className="w-full bg-[#1e3a5f] text-white py-3 rounded-xl font-medium hover:bg-[#2a4a6f] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {submitting ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    {formData.submitted_at ? 'Update Responses' : 'Submit Form'}
                  </>
                )}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
