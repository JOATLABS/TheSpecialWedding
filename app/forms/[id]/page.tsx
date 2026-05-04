'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter, useParams, useSearchParams } from 'next/navigation';

interface FormField {
 id: string;
 label: string;
 type: string;
 placeholder?: string;
 required: boolean;
 description?: string;
 options: string[];
 order: number;
}

interface FormSettings {
 title: string;
 description?: string;
 submit_button_text: string;
 success_message: string;
 collect_email: boolean;
}

interface Form {
 id: string;
 settings: FormSettings;
 fields: FormField[];
 is_active: boolean;
}

export default function PublicFormPage() {
 const params = useParams();
 const router = useRouter();
 const searchParams = useSearchParams();
 const formId = params.id as string;
 // Per-recipient link params from the email send: ?dist=<distribution_id>&t=<access_token>.
 // The pair is verified against the backend before rendering the form so we can
 // show "already responded" / "link expired" instead of a stale form.
 const distributionId = searchParams?.get('dist') || undefined;
 const accessToken = searchParams?.get('t') || undefined;
 const [form, setForm] = useState<Form | null>(null);
 const [responses, setResponses] = useState<{ [key: string]: any }>({});
 const [loading, setLoading] = useState(true);
 const [submitting, setSubmitting] = useState(false);
 const [submitted, setSubmitted] = useState(false);
 const [error, setError] = useState('');
 const [successMessage, setSuccessMessage] = useState('');
 const [linkState, setLinkState] = useState<
   'unknown' | 'valid' | 'already_submitted' | 'expired' | 'invalid'
 >('unknown');

 const fetchForm = useCallback(async () => {
 try {
 const baseUrl = getApiBaseUrl();
 const response = await fetch(`${baseUrl}/public/forms/${formId}`);

 if (response.ok) {
 const data = await response.json();
 setForm(data);
 if (!data.is_active) {
 setError('This form is no longer accepting responses.');
 }
 } else {
 setError('Form not found or no longer available.');
 }

 // Tokenized link: validate it server-side so we can short-circuit
 // the render with an honest message instead of letting the user
 // fill out a doomed form.
 if (distributionId && accessToken) {
   try {
     const checkRes = await fetch(
       `${baseUrl}/public/forms/${formId}/distributions/${encodeURIComponent(distributionId)}/check?t=${encodeURIComponent(accessToken)}`,
     );
     if (checkRes.ok) {
       const checkData = await checkRes.json();
       if (checkData.already_submitted) setLinkState('already_submitted');
       else if (checkData.expired) setLinkState('expired');
       else setLinkState('valid');
     } else {
       setLinkState('invalid');
     }
   } catch {
     setLinkState('invalid');
   }
 } else {
   setLinkState('valid'); // No-token flow stays open
 }
 } catch (error) {
 setError('Failed to load form. Please try again later.');
 } finally {
 setLoading(false);
 }
 }, [formId, distributionId, accessToken]);

 useEffect(() => {
 if (formId) {
 fetchForm();
 }
 }, [fetchForm, formId]);

 const handleInputChange = (fieldId: string, value: any) => {
 setResponses(prev => ({
 ...prev,
 [fieldId]: value
 }));
 };

 const validateForm = () => {
 if (!form) return false;

 for (const field of form.fields) {
 if (field.required && !responses[field.id]) {
 setError(`Please fill in the required field: ${field.label}`);
 return false;
 }
 }

 return true;
 };

 const submitForm = async () => {
 if (!validateForm()) return;

 setSubmitting(true);
 setError('');

 try {
 const baseUrl = getApiBaseUrl();
 // Prepare submission data
 const submissionData = {
 responses,
 submitted_by_email: responses.email || responses.guest_email || responses.contact_email,
 submitted_by_name: responses.name || responses.guest_name || responses.contact_name,
 distribution_id: distributionId,
 access_token: accessToken,
 };

 const response = await fetch(`${baseUrl}/public/forms/${formId}/submit`, {
 method: 'POST',
 headers: {
 'Content-Type': 'application/json',
 },
 body: JSON.stringify(submissionData),
 });

 if (response.ok) {
 const data = await response.json();
 setSuccessMessage(data.message || form?.settings.success_message || 'Thank you for your submission!');
 setSubmitted(true);
 // Redirect if URL is provided
 if (data.redirect_url) {
 setTimeout(() => {
 window.location.href = data.redirect_url;
 }, 3000);
 }
 } else {
 const errorData = await response.json();
 setError(errorData.detail || 'Failed to submit form. Please try again.');
 }
 } catch (error) {
 setError('Failed to submit form. Please check your connection and try again.');
 } finally {
 setSubmitting(false);
 }
 };

 const renderField = (field: FormField) => {
 const commonProps = {
 id: field.id,
 required: field.required,
 onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
 handleInputChange(field.id, e.target.value)
 };

 switch (field.type) {
 case 'text':
 case 'email':
 case 'phone':
 return (
 <input
 type={field.type}
 placeholder={field.placeholder}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
 {...commonProps}
 />
 );

 case 'number':
 return (
 <input
 type="number"
 placeholder={field.placeholder}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
 {...commonProps}
 />
 );

 case 'date':
 return (
 <input
 type="date"
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
 {...commonProps}
 />
 );

 case 'textarea':
 return (
 <textarea
 rows={4}
 placeholder={field.placeholder}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-vertical"
 {...commonProps}
 />
 );

 case 'select':
 return (
 <select
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
 {...commonProps}
 >
 <option value="">Select an option...</option>
 {field.options.map((option, index) => (
 <option key={index} value={option}>{option}</option>
 ))}
 </select>
 );

 case 'radio':
 return (
 <div className="space-y-3">
 {field.options.map((option, index) => (
 <label key={index} className="flex items-center">
 <input
 type="radio"
 name={field.id}
 value={option}
 onChange={() => handleInputChange(field.id, option)}
 className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300"
 />
 <span className="ml-3 text-gray-700">{option}</span>
 </label>
 ))}
 </div>
 );

 case 'checkbox':
 return (
 <div className="space-y-3">
 {field.options.map((option, index) => (
 <label key={index} className="flex items-center">
 <input
 type="checkbox"
 value={option}
 onChange={(e) => {
 const currentValues = responses[field.id] || [];
 if (e.target.checked) {
 handleInputChange(field.id, [...currentValues, option]);
 } else {
 handleInputChange(field.id, currentValues.filter((v: string) => v !== option));
 }
 }}
 className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
 />
 <span className="ml-3 text-gray-700">{option}</span>
 </label>
 ))}
 </div>
 );

 case 'rating':
 return (
 <div className="flex space-x-2">
 {[1, 2, 3, 4, 5].map((rating) => (
 <button
 key={rating}
 type="button"
 onClick={() => handleInputChange(field.id, rating)}
 className={`text-2xl ${
 responses[field.id] >= rating ? 'text-yellow-400' : 'text-gray-300'
 } hover:text-yellow-400 transition-colors`}
 >
 </button>
 ))}
 <span className="ml-2 text-sm text-gray-600">
 {responses[field.id] ? `${responses[field.id]} star${responses[field.id] !== 1 ? 's' : ''}` : 'Click to rate'}
 </span>
 </div>
 );

 case 'scale':
 return (
 <div className="space-y-3">
 <div className="flex justify-between text-sm text-gray-600">
 <span>1 (Poor)</span>
 <span>10 (Excellent)</span>
 </div>
 <div className="grid grid-cols-10 gap-2">
 {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((rating) => (
 <button
 key={rating}
 type="button"
 onClick={() => handleInputChange(field.id, rating)}
 className={`h-10 w-10 rounded-lg border ${
 responses[field.id] === rating
 ? 'bg-indigo-600 text-white border-indigo-600'
 : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
 } transition-colors`}
 >
 {rating}
 </button>
 ))}
 </div>
 {responses[field.id] && (
 <p className="text-sm text-gray-600 text-center">
 Selected: {responses[field.id]}/10
 </p>
 )}
 </div>
 );

 default:
 return (
 <input
 type="text"
 placeholder={field.placeholder}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
 {...commonProps}
 />
 );
 }
 };

 if (loading) {
 return (
 <div className="min-h-screen flex items-center justify-center bg-gray-50">
 <div className="text-center">
 <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
 <p className="text-gray-600">Loading form...</p>
 </div>
 </div>
 );
 }

 if (error) {
 return (
 <div className="min-h-screen flex items-center justify-center bg-gray-50">
 <div className="text-center bg-white p-8 rounded-lg shadow-sm max-w-md">
 <div className="text-4xl mb-4"></div>
 <h2 className="text-xl font-semibold text-gray-900 mb-2">Unable to Load Form</h2>
 <p className="text-gray-600 mb-4">{error}</p>
 <button
 onClick={() => window.location.reload()}
 className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
 >
 Try Again
 </button>
 </div>
 </div>
 );
 }

 if (submitted) {
 return (
 <div className="min-h-screen flex items-center justify-center bg-gray-50">
 <div className="text-center bg-white p-8 rounded-lg shadow-sm max-w-md">
 <div className="text-4xl mb-4"></div>
 <h2 className="text-xl font-semibold text-gray-900 mb-2">Thank You!</h2>
 <p className="text-gray-600">{successMessage}</p>
 </div>
 </div>
 );
 }

 if (linkState === 'already_submitted') {
 return (
 <div className="min-h-screen flex items-center justify-center bg-gray-50">
 <div className="text-center bg-white p-8 rounded-lg shadow-sm max-w-md">
 <h2 className="text-xl font-semibold text-gray-900 mb-2">Response Already Submitted</h2>
 <p className="text-gray-600">
 We&rsquo;ve already received a response for this link. If you need to update your answer, please contact the planner.
 </p>
 </div>
 </div>
 );
 }

 if (linkState === 'expired') {
 return (
 <div className="min-h-screen flex items-center justify-center bg-gray-50">
 <div className="text-center bg-white p-8 rounded-lg shadow-sm max-w-md">
 <h2 className="text-xl font-semibold text-gray-900 mb-2">Link Expired</h2>
 <p className="text-gray-600">
 This form link has expired. Please reach out to the planner for a fresh link.
 </p>
 </div>
 </div>
 );
 }

 if (linkState === 'invalid') {
 return (
 <div className="min-h-screen flex items-center justify-center bg-gray-50">
 <div className="text-center bg-white p-8 rounded-lg shadow-sm max-w-md">
 <h2 className="text-xl font-semibold text-gray-900 mb-2">Invalid Form Link</h2>
 <p className="text-gray-600">
 This form link could not be verified. It may have been mistyped or already been used.
 </p>
 </div>
 </div>
 );
 }

 if (!form) return null;

 // Sort fields by order
 const sortedFields = [...form.fields].sort((a, b) => a.order - b.order);

 return (
 <div className="min-h-screen bg-gray-50 py-8">
 <div className="max-w-2xl mx-auto px-4">
 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
 {/* Form Header */}
 <div className="text-center mb-8">
 <h1 className="text-3xl font-bold text-gray-900 mb-4">
 {form.settings.title}
 </h1>
 {form.settings.description && (
 <p className="text-gray-600 text-lg leading-relaxed">
 {form.settings.description}
 </p>
 )}
 </div>

 {/* Error Message */}
 {error && (
 <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
 <p className="text-red-600">{error}</p>
 </div>
 )}

 {/* Form Fields */}
 <div className="space-y-6">
 {sortedFields.map((field) => (
 <div key={field.id} className="space-y-2">
 <label className="block text-sm font-medium text-gray-700">
 {field.label}
 {field.required && <span className="text-red-500 ml-1">*</span>}
 </label>
 {field.description && (
 <p className="text-sm text-gray-500">{field.description}</p>
 )}
 {renderField(field)}
 </div>
 ))}
 </div>

 {/* Submit Button */}
 <div className="mt-8 pt-6 border-t border-gray-200">
 <button
 onClick={submitForm}
 disabled={submitting}
 className="w-full bg-indigo-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
 >
 {submitting ? 'Submitting...' : form.settings.submit_button_text}
 </button>
 </div>

 {/* Footer */}
 <div className="mt-6 text-center text-sm text-gray-500">
 Powered by Special Wedding Platform
 </div>
 </div>
 </div>
 </div>
 );
}
