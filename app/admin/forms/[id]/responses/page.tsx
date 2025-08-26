'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';

interface FormResponse {
 id: string;
 responses: { [key: string]: any };
 submitted_by_email?: string;
 submitted_by_name?: string;
 submitted_at: string;
 ip_address?: string;
}

interface FormField {
 id: string;
 label: string;
 type: string;
 options?: string[];
}

interface Form {
 id: string;
 name: string;
 settings: {
 title: string;
 description?: string;
 };
 fields: FormField[];
}

export default function FormResponsesPage() {
 const params = useParams();
 const router = useRouter();
 const { token } = useAdmin();
 const formId = params.id as string;

 const [form, setForm] = useState<Form | null>(null);
 const [responses, setResponses] = useState<FormResponse[]>([]);
 const [loading, setLoading] = useState(true);
 const [error, setError] = useState('');
 const [selectedResponse, setSelectedResponse] = useState<FormResponse | null>(null);
 const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'name'>('newest');
 const [filterEmail, setFilterEmail] = useState('');

 useEffect(() => {
 if (!token || !formId) return;
 fetchFormAndResponses();
 }, [token, formId]);

 const fetchFormAndResponses = async () => {
 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 
 // Fetch form details and responses in parallel
 const [formResponse, responsesResponse] = await Promise.all([
 fetch(`${baseUrl}/admin/forms/${formId}`, {
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 }),
 fetch(`${baseUrl}/admin/forms/${formId}/responses`, {
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 })
 ]);

 if (formResponse.ok && responsesResponse.ok) {
 const formData = await formResponse.json();
 const responsesData = await responsesResponse.json();
 
 setForm(formData);
 setResponses(responsesData);
 } else {
 setError('Failed to load form or responses');
 }
 } catch (error) {
 setError('Failed to load data');
 } finally {
 setLoading(false);
 }
 };

 const downloadCSV = () => {
 if (!form || responses.length === 0) return;

 // Prepare CSV headers
 const headers = [
 'Submission Date',
 'Name',
 'Email',
 'IP Address',
 ...form.fields.map(field => field.label)
 ];

 // Prepare CSV data
 const csvData = responses.map(response => [
 new Date(response.submitted_at).toLocaleString(),
 response.submitted_by_name || '',
 response.submitted_by_email || '',
 response.ip_address || '',
 ...form.fields.map(field => {
 const value = response.responses[field.id];
 if (Array.isArray(value)) {
 return value.join(', ');
 }
 return value || '';
 })
 ]);

 // Create CSV content
 const csvContent = [
 headers.join(','),
 ...csvData.map(row => row.map(cell => `"${cell}"`).join(','))
 ].join('\n');

 // Download file
 const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
 const link = document.createElement('a');
 const url = URL.createObjectURL(blob);
 link.setAttribute('href', url);
 link.setAttribute('download', `${form.name}_responses_${new Date().toISOString().split('T')[0]}.csv`);
 link.style.visibility = 'hidden';
 document.body.appendChild(link);
 link.click();
 document.body.removeChild(link);
 };

 const formatFieldValue = (field: FormField, value: any) => {
 if (value === null || value === undefined || value === '') {
 return <span className="text-gray-400 italic">No response</span>;
 }

 switch (field.type) {
 case 'rating':
 return (
 <div className="flex">
 {[...Array(5)].map((_, i) => (
 <span key={i} className={i < value ? 'text-yellow-400' : 'text-gray-300'}>
 
 </span>
 ))}
 <span className="ml-2 text-sm text-gray-600">({value}/5)</span>
 </div>
 );
 
 case 'scale':
 return (
 <div className="flex items-center">
 <div className="w-20 bg-gray-200 rounded-full h-2 mr-2">
 <div 
 className="bg-blue-600 h-2 rounded-full" 
 style={{ width: `${(value / 10) * 100}%` }}
 ></div>
 </div>
 <span className="text-sm">{value}/10</span>
 </div>
 );
 
 case 'checkbox':
 if (Array.isArray(value)) {
 return value.join(', ');
 }
 return value;
 
 case 'email':
 return <a href={`mailto:${value}`} className="text-blue-600 hover:underline">{value}</a>;
 
 case 'phone':
 return <a href={`tel:${value}`} className="text-blue-600 hover:underline">{value}</a>;
 
 case 'textarea':
 return (
 <div className="max-w-xs">
 <p className="truncate">{value}</p>
 {value.length > 50 && (
 <button 
 onClick={() => setSelectedResponse(responses.find(r => r.responses[field.id] === value) || null)}
 className="text-blue-600 text-sm hover:underline"
 >
 View full
 </button>
 )}
 </div>
 );
 
 default:
 return value;
 }
 };

 const filteredAndSortedResponses = responses
 .filter(response => 
 !filterEmail || 
 (response.submitted_by_email && response.submitted_by_email.toLowerCase().includes(filterEmail.toLowerCase())) ||
 (response.submitted_by_name && response.submitted_by_name.toLowerCase().includes(filterEmail.toLowerCase()))
 )
 .sort((a, b) => {
 switch (sortBy) {
 case 'newest':
 return new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime();
 case 'oldest':
 return new Date(a.submitted_at).getTime() - new Date(b.submitted_at).getTime();
 case 'name':
 return (a.submitted_by_name || '').localeCompare(b.submitted_by_name || '');
 default:
 return 0;
 }
 });

 if (loading) {
 return (
 <div className="min-h-screen flex items-center justify-center">
 <div className="text-center">
 <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
 <p className="text-gray-600">Loading responses...</p>
 </div>
 </div>
 );
 }

 if (error || !form) {
 return (
 <div className="min-h-screen flex items-center justify-center">
 <div className="text-center">
 <p className="text-red-600 mb-4">{error || 'Form not found'}</p>
 <button
 onClick={() => router.push('/admin/forms')}
 className="text-blue-600 hover:text-blue-800"
 >
 ← Back to Forms
 </button>
 </div>
 </div>
 );
 }

 return (
 <div className="min-h-screen bg-gray-50">
 <div className="max-w-7xl mx-auto py-8 px-4">
 {/* Header */}
 <div className="mb-8">
 <div className="flex items-center justify-between mb-4">
 <button
 onClick={() => router.push('/admin/forms')}
 className="flex items-center text-gray-600 hover:text-gray-800"
 >
 <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
 </svg>
 Back to Forms
 </button>
 
 {responses.length > 0 && (
 <button
 onClick={downloadCSV}
 className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
 >
 <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
 </svg>
 Export CSV
 </button>
 )}
 </div>
 
 <div className="bg-white rounded-lg shadow-sm border p-6">
 <h1 className="text-3xl font-bold text-gray-900 mb-2">Form Responses</h1>
 <div className="flex items-center text-gray-600">
 <span className="text-lg font-medium">{form.name}</span>
 <span className="mx-2">•</span>
 <span>{form.settings.title}</span>
 <span className="mx-2">•</span>
 <span className="font-medium">{responses.length} responses</span>
 </div>
 </div>
 </div>

 {responses.length === 0 ? (
 <div className="bg-white rounded-lg shadow-sm border p-12 text-center">
 <div className="text-4xl mb-4"></div>
 <h3 className="text-lg font-medium text-gray-900 mb-2">No responses yet</h3>
 <p className="text-gray-500 mb-6">Once people start submitting your form, their responses will appear here.</p>
 <button
 onClick={() => router.push(`/admin/forms/${formId}/send`)}
 className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
 >
 Send Form to Recipients
 </button>
 </div>
 ) : (
 <>
 {/* Filters and Controls */}
 <div className="bg-white rounded-lg shadow-sm border p-4 mb-6">
 <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
 <div className="flex gap-4 items-center">
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">Search</label>
 <input
 type="text"
 value={filterEmail}
 onChange={(e) => setFilterEmail(e.target.value)}
 placeholder="Search by name or email..."
 className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">Sort by</label>
 <select
 value={sortBy}
 onChange={(e) => setSortBy(e.target.value as any)}
 className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
 >
 <option value="newest">Newest first</option>
 <option value="oldest">Oldest first</option>
 <option value="name">Name A-Z</option>
 </select>
 </div>
 </div>
 
 <div className="text-sm text-gray-500">
 Showing {filteredAndSortedResponses.length} of {responses.length} responses
 </div>
 </div>
 </div>

 {/* Responses Table */}
 <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
 <div className="overflow-x-auto">
 <table className="min-w-full divide-y divide-gray-200">
 <thead className="bg-gray-50">
 <tr>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
 Submitted
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
 Name
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
 Email
 </th>
 {form.fields.slice(0, 3).map(field => (
 <th key={field.id} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
 {field.label}
 </th>
 ))}
 {form.fields.length > 3 && (
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
 +{form.fields.length - 3} more
 </th>
 )}
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
 Actions
 </th>
 </tr>
 </thead>
 <tbody className="bg-white divide-y divide-gray-200">
 {filteredAndSortedResponses.map((response) => (
 <tr key={response.id} className="hover:bg-gray-50">
 <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
 <div>
 {new Date(response.submitted_at).toLocaleDateString()}
 </div>
 <div className="text-xs text-gray-500">
 {new Date(response.submitted_at).toLocaleTimeString()}
 </div>
 </td>
 <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
 {response.submitted_by_name || <span className="text-gray-400 italic">Anonymous</span>}
 </td>
 <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
 {response.submitted_by_email ? (
 <a href={`mailto:${response.submitted_by_email}`} className="text-blue-600 hover:underline">
 {response.submitted_by_email}
 </a>
 ) : (
 <span className="text-gray-400 italic">No email</span>
 )}
 </td>
 {form.fields.slice(0, 3).map(field => (
 <td key={field.id} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
 {formatFieldValue(field, response.responses[field.id])}
 </td>
 ))}
 {form.fields.length > 3 && (
 <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
 <button
 onClick={() => setSelectedResponse(response)}
 className="text-blue-600 hover:underline"
 >
 View all
 </button>
 </td>
 )}
 <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
 <button
 onClick={() => setSelectedResponse(response)}
 className="text-blue-600 hover:text-blue-800 font-medium"
 >
 View Details
 </button>
 </td>
 </tr>
 ))}
 </tbody>
 </table>
 </div>
 </div>
 </>
 )}
 </div>

 {/* Response Detail Modal */}
 {selectedResponse && (
 <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
 <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
 <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
 <h3 className="text-lg font-semibold">Response Details</h3>
 <button
 onClick={() => setSelectedResponse(null)}
 className="text-gray-400 hover:text-gray-600"
 >
 <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
 </svg>
 </button>
 </div>
 
 <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
 {/* Response Meta */}
 <div className="bg-gray-50 rounded-lg p-4 mb-6">
 <div className="grid grid-cols-2 gap-4 text-sm">
 <div>
 <span className="font-medium text-gray-700">Submitted:</span>
 <div>{new Date(selectedResponse.submitted_at).toLocaleString()}</div>
 </div>
 <div>
 <span className="font-medium text-gray-700">Name:</span>
 <div>{selectedResponse.submitted_by_name || 'Anonymous'}</div>
 </div>
 <div>
 <span className="font-medium text-gray-700">Email:</span>
 <div>
 {selectedResponse.submitted_by_email ? (
 <a href={`mailto:${selectedResponse.submitted_by_email}`} className="text-blue-600 hover:underline">
 {selectedResponse.submitted_by_email}
 </a>
 ) : (
 'Not provided'
 )}
 </div>
 </div>
 <div>
 <span className="font-medium text-gray-700">IP Address:</span>
 <div>{selectedResponse.ip_address || 'Not recorded'}</div>
 </div>
 </div>
 </div>

 {/* Response Data */}
 <div className="space-y-6">
 {form.fields.map(field => (
 <div key={field.id} className="border-b border-gray-200 pb-4">
 <h4 className="font-medium text-gray-900 mb-2">{field.label}</h4>
 <div className="text-gray-700">
 {formatFieldValue(field, selectedResponse.responses[field.id])}
 </div>
 </div>
 ))}
 </div>
 </div>
 </div>
 </div>
 )}
 </div>
 );
}