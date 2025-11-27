'use client';

import React, { useState } from 'react';

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

interface FormPreviewProps {
 form: Form;
}

export const FormPreview: React.FC<FormPreviewProps> = ({ form }) => {
 const [responses, setResponses] = useState<{ [key: string]: any }>({});
 const [isSubmitting, setIsSubmitting] = useState(false);
 const [isSubmitted, setIsSubmitted] = useState(false);

 const handleInputChange = (fieldId: string, value: any) => {
 setResponses(prev => ({
 ...prev,
 [fieldId]: value
 }));
 };

 const handleSubmit = (e: React.FormEvent) => {
 e.preventDefault();
 setIsSubmitting(true);
 // Simulate form submission
 setTimeout(() => {
 setIsSubmitting(false);
 setIsSubmitted(true);
 }, 1000);
 };

 const renderField = (field: FormField) => {
 const commonProps = {
 id: field.id,
 required: field.required,
 };

 switch (field.type) {
 case 'text':
 case 'email':
 case 'phone':
 return (
 <input
 type={field.type}
 placeholder={field.placeholder}
 value={responses[field.id] || ''}
 onChange={(e) => handleInputChange(field.id, e.target.value)}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
 {...commonProps}
 />
 );

 case 'number':
 return (
 <input
 type="number"
 placeholder={field.placeholder}
 value={responses[field.id] || ''}
 onChange={(e) => handleInputChange(field.id, e.target.value)}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
 {...commonProps}
 />
 );

 case 'date':
 return (
 <input
 type="date"
 value={responses[field.id] || ''}
 onChange={(e) => handleInputChange(field.id, e.target.value)}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
 {...commonProps}
 />
 );

 case 'textarea':
 return (
 <textarea
 rows={4}
 placeholder={field.placeholder}
 value={responses[field.id] || ''}
 onChange={(e) => handleInputChange(field.id, e.target.value)}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-vertical"
 {...commonProps}
 />
 );

 case 'select':
 return (
 <select
 value={responses[field.id] || ''}
 onChange={(e) => handleInputChange(field.id, e.target.value)}
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
 type="radio"
 name={field.id}
 value={option}
 checked={responses[field.id] === option}
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
 type="checkbox"
 value={option}
 checked={(responses[field.id] || []).includes(option)}
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
 (responses[field.id] || 0) >= rating ? 'text-yellow-400' : 'text-gray-300'
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
 value={responses[field.id] || ''}
 onChange={(e) => handleInputChange(field.id, e.target.value)}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
 {...commonProps}
 />
 );
 }
 };

 if (isSubmitted) {
 return (
 <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 max-w-md w-full text-center">
 <div className="text-4xl mb-4"></div>
 <h2 className="text-xl font-semibold text-gray-900 mb-2">Thank You!</h2>
 <p className="text-gray-600 mb-6">{form.settings.success_message}</p>
 <button
 onClick={() => {
 setIsSubmitted(false);
 setResponses({});
 }}
 className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
 >
 Reset Form
 </button>
 </div>
 </div>
 );
 }

 // Sort fields by order
 const sortedFields = [...form.fields].sort((a, b) => a.order - b.order);

 return (
 <div className="min-h-screen bg-gray-50 p-6">
 <div className="max-w-2xl mx-auto">
 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
 {/* Preview Badge */}
 <div className="mb-6">
 <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
 Preview Mode
 </div>
 </div>

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

 {/* Form */}
 <form onSubmit={handleSubmit} className="space-y-6">
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

 {/* Submit Button */}
 <div className="pt-6 border-t border-gray-200">
 <button
 type="submit"
 disabled={isSubmitting}
 className="w-full bg-indigo-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
 >
 {isSubmitting ? 'Submitting...' : form.settings.submit_button_text}
 </button>
 </div>
 </form>

 {/* Footer */}
 <div className="mt-6 text-center text-sm text-gray-500">
 Powered by Special Wedding Platform
 </div>
 </div>
 </div>
 </div>
 );
};