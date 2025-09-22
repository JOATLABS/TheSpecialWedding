'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { PublicForm as Form, FormField, FormResponseValue } from '@/types/forms';
import { buildApiUrl } from '@/utils/api-base';

export default function PublicFormPage() {
 const params = useParams();
 // Removed unused router (public form page does not navigate programmatically here)
 const formId = params.id as string;
 
 const [form, setForm] = useState<Form | null>(null);
 const [responses, setResponses] = useState<Record<string, FormResponseValue>>({});
 const [loading, setLoading] = useState(true);
 const [submitting, setSubmitting] = useState(false);
 const [submitted, setSubmitted] = useState(false);
 const [error, setError] = useState('');
 const [successMessage, setSuccessMessage] = useState('');

 useEffect(() => {
 if (formId) {
 fetchForm();
 }
 }, [formId]);

 const fetchForm = async () => {
 try {
 const response = await fetch(buildApiUrl(`/public/forms/${formId}`));

 if (response.ok) {
 const data = await response.json();
 setForm(data);
 
 if (!data.is_active) {
 setError('This form is no longer accepting responses.');
 }
 } else {
 setError('Form not found or no longer available.');
 }
 } catch (error) {
 setError('Failed to load form. Please try again later.');
 } finally {
 setLoading(false);
 }
 };

 const handleInputChange = (fieldId: string, value: FormResponseValue) => {
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
 // Prepare submission data
 const submissionData = {
 responses,
 submitted_by_email: responses.email || responses.guest_email || responses.contact_email,
 submitted_by_name: responses.name || responses.guest_name || responses.contact_name
 };

 const response = await fetch(buildApiUrl(`/public/forms/${formId}/submit`), {
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
 {(field.options || []).map((option, index) => (
 <option key={index} value={option}>{option}</option>
 ))}
 </select>
 );

 case 'radio':
 return (
 <div className="space-y-3">
 {(field.options || []).map((option, index) => (
 <label key={index} className="flex items-center">
 <input
 id={`${field.id}-radio-${index}`}
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
 {(field.options || []).map((option, index) => (
 <label key={index} className="flex items-center">
 <input
 id={`${field.id}-checkbox-${index}`}
 type="checkbox"
 value={option}
 onChange={(e) => {
 const currentValues = Array.isArray(responses[field.id]) ? (responses[field.id] as string[]) : [];
 if (e.target.checked) {
	 handleInputChange(field.id, [...currentValues, option]);
 } else {
	 handleInputChange(
		 field.id,
		 currentValues.filter((v: string) => v !== option)
	 );
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
 id={`${field.id}-rating-${rating}`}
 key={rating}
 type="button"
 onClick={() => handleInputChange(field.id, rating)}
 className={`text-2xl ${
 (typeof responses[field.id] === 'number' ? (responses[field.id] as number) : 0) >= rating
	 ? 'text-yellow-400'
	 : 'text-gray-300'
 } hover:text-yellow-400 transition-colors`}
 >
 
 </button>
 ))}
 <span className="ml-2 text-sm text-gray-600">
 {typeof responses[field.id] === 'number'
	 ? `${responses[field.id]} star${responses[field.id] !== 1 ? 's' : ''}`
	 : 'Click to rate'}
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
 id={`${field.id}-scale-${rating}`}
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
 {typeof responses[field.id] === 'number' && (
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
 id="form-error-retry-button"
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
 id="form-submit-button"
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