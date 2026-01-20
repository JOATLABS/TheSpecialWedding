'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useParams, useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { formatDate, formatDateTime } from '@/utils/dateFormat';

interface VendorSubmission {
 _id: string;
 form_name: string;
 vendor_name: string;
 vendor_email: string;
 vendor_type: string;
 wedding: {
 couple_names: string;
 date: string;
 };
 submission_data: {[key: string]: any};
 submitted_at: string;
 status: string;
 fields: Array<{
 id: string;
 label: string;
 type: string;
 required: boolean;
 options?: string[];
 }>;
}

export default function VendorSubmissionPage() {
 const params = useParams();
 const router = useRouter();
 const { token } = useAdmin();
 const formId = params.form_id as string;

 const [submission, setSubmission] = useState<VendorSubmission | null>(null);
 const [loading, setLoading] = useState(true);
 const [error, setError] = useState('');

 const fetchSubmission = useCallback(async () => {
 try {
 const baseUrl = getApiBaseUrl();
 const response = await fetch(`${baseUrl}/admin/vendor-forms/${formId}`, {
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 });

 if (!response.ok) {
 throw new Error('Failed to fetch submission');
 }

 const data = await response.json();
 // Get wedding details - use planner endpoint for assigned weddings
 const weddingResponse = await fetch(`${baseUrl}/admin/planner/weddings`, {
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 });

 if (weddingResponse.ok) {
 const weddings = await weddingResponse.json();
 const wedding = weddings.find((w: any) => w._id === data.wedding_id);
 setSubmission({
 ...data,
 wedding: {
 couple_names: wedding?.couple_names || 'Unknown',
 date: wedding?.date || 'Unknown'
 }
 });
 } else {
 setSubmission({
 ...data,
 wedding: {
 couple_names: 'Unknown',
 date: 'Unknown'
 }
 });
 }

 } catch (err) {
 setError(err instanceof Error ? err.message : 'Failed to load submission');
 } finally {
 setLoading(false);
 }
 }, [formId, token]);

 useEffect(() => {
 if (formId && token) {
 fetchSubmission();
 }
 }, [fetchSubmission, formId, token]);

 const updateSubmissionStatus = async (newStatus: string) => {
 try {
 const baseUrl = getApiBaseUrl();
 const response = await fetch(`${baseUrl}/admin/vendor-forms/${formId}/status`, {
 method: 'PUT',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 body: JSON.stringify({ status: newStatus }),
 });

 if (response.ok) {
 setSubmission(prev => prev ? { ...prev, status: newStatus } : null);
 alert(`Submission ${newStatus} successfully`);
 } else {
 throw new Error('Failed to update status');
 }
 } catch (err) {
 alert('Failed to update status');
 }
 };

 const renderFieldValue = (field: any, value: any) => {
 if (!value && value !== 0) return <span className="text-gray-400 italic">Not provided</span>;

 switch (field.type) {
 case 'checkbox':
 if (Array.isArray(value) && value.length > 0) {
 return (
 <div className="flex flex-wrap gap-1">
 {value.map((item, index) => (
 <span key={index} className="inline-flex px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded">
 {item}
 </span>
 ))}
 </div>
 );
 }
 return <span className="text-gray-400 italic">None selected</span>;

 case 'textarea':
 return (
 <div className="bg-gray-50 p-3 rounded border">
 <pre className="whitespace-pre-wrap text-sm">{value}</pre>
 </div>
 );

    case 'date':
      return formatDate(value) || value;

 case 'email':
 return (
 <a href={`mailto:${value}`} className="text-blue-600 hover:text-blue-800">
 {value}
 </a>
 );

 case 'phone':
 return (
 <a href={`tel:${value}`} className="text-blue-600 hover:text-blue-800">
 {value}
 </a>
 );

 default:
 return <span>{value}</span>;
 }
 };

 const exportToPDF = () => {
 // Simple print functionality - browser will handle PDF generation
 window.print();
 };

 const contactVendor = () => {
 if (submission) {
 window.location.href = `mailto:${submission.vendor_email}?subject=Re: ${submission.form_name}&body=Hello ${submission.vendor_name},%0A%0AThank you for submitting your information for ${submission.wedding.couple_names}'s wedding.%0A%0A`;
 }
 };

 if (loading) {
 return (
 <div className="min-h-screen flex items-center justify-center">
 <div className="text-center">
 <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
 <p className="text-gray-600">Loading submission...</p>
 </div>
 </div>
 );
 }

 if (error) {
 return (
 <div className="min-h-screen flex items-center justify-center">
 <div className="text-center">
 <div className="text-red-600 mb-4">
 <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
 </svg>
 </div>
 <h2 className="text-lg font-semibold text-gray-900 mb-2">Error Loading Submission</h2>
 <p className="text-gray-600 mb-4">{error}</p>
 <button
 onClick={() => router.back()}
 className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
 >
 Go Back
 </button>
 </div>
 </div>
 );
 }

 if (!submission || submission.status !== 'submitted') {
 return (
 <div className="min-h-screen flex items-center justify-center">
 <div className="text-center">
 <h2 className="text-lg font-semibold text-gray-900 mb-2">No Submission Found</h2>
 <p className="text-gray-600 mb-4">This form has not been submitted yet.</p>
 <button
 onClick={() => router.back()}
 className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
 >
 Go Back
 </button>
 </div>
 </div>
 );
 }

 return (
 <div className="min-h-screen bg-gray-50 py-8 print:bg-white print:py-0">
 <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
 {/* Header */}
 <div className="bg-white rounded-lg shadow-lg overflow-hidden mb-8 print:shadow-none print:mb-4">
 <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-6 text-white print:bg-gray-800">
 <div className="flex items-center justify-between">
 <div>
 <h1 className="text-2xl font-bold mb-2">Vendor Submission</h1>
 <p className="text-blue-100">{submission.form_name}</p>
 </div>
 <div className="text-right print:hidden">
 <button
 onClick={() => router.back()}
 className="bg-white bg-opacity-20 text-white px-4 py-2 rounded-lg hover:bg-opacity-30 transition-colors mr-2"
 >
 ← Back
 </button>
 </div>
 </div>
 </div>

 {/* Wedding & Vendor Info */}
 <div className="px-6 py-4 bg-blue-50 border-b print:bg-white">
 <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
 <div>
 <span className="font-medium text-gray-700">Wedding:</span>
 <div className="text-gray-900">{submission.wedding.couple_names}</div>
 </div>
 <div>
 <span className="font-medium text-gray-700">Date:</span>
 <div className="text-gray-900">{submission.wedding.date}</div>
 </div>
 <div>
 <span className="font-medium text-gray-700">Vendor:</span>
 <div className="text-gray-900">{submission.vendor_name}</div>
 </div>
 <div>
 <span className="font-medium text-gray-700">Service:</span>
 <div className="text-gray-900">{submission.vendor_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</div>
 </div>
 </div>
 </div>

 {/* Submission Meta */}
 <div className="px-6 py-3 bg-gray-50 border-b text-sm print:bg-white">
 <div className="flex items-center justify-between">
 <div>
 <span className="font-medium text-gray-700">Submitted:</span>
        <span className="ml-2 text-gray-900">
          {formatDateTime(submission.submitted_at, {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
          })}
        </span>
 </div>
 <div className="flex items-center space-x-2">
 <span className="font-medium text-gray-700">Status:</span>
 <span className={`px-2 py-1 text-xs font-medium rounded-full ${{
 'submitted': 'bg-green-100 text-green-800',
 'approved': 'bg-emerald-100 text-emerald-800',
 'rejected': 'bg-red-100 text-red-800'
 }[submission.status] || 'bg-gray-100 text-gray-800'}`}>
 {submission.status.charAt(0).toUpperCase() + submission.status.slice(1)}
 </span>
 </div>
 </div>
 </div>
 </div>

 {/* Actions */}
 <div className="flex flex-wrap gap-3 mb-6 print:hidden">
 <button
 onClick={contactVendor}
 className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
 >
 Contact Vendor
 </button>
 <button
 onClick={exportToPDF}
 className="bg-gray-600 text-white px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors"
 >
 Print/PDF
 </button>
 {submission.status === 'submitted' && (
 <>
 <button
 onClick={() => updateSubmissionStatus('approved')}
 className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
 >
 Approve
 </button>
 <button
 onClick={() => updateSubmissionStatus('rejected')}
 className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors"
 >
 Reject
 </button>
 </>
 )}
 </div>

 {/* Submission Content */}
 <div className="bg-white rounded-lg shadow-lg p-6 sm:p-8 print:shadow-none">
 <h2 className="text-xl font-bold text-gray-900 mb-6">Vendor Information</h2>

 <div className="space-y-6">
 {submission.fields.map((field) => {
 const value = submission.submission_data[field.id];

 return (
 <div key={field.id} className="border-b border-gray-200 pb-4 last:border-b-0">
 <div className="flex flex-col sm:flex-row sm:items-start">
 <div className="sm:w-1/3 mb-2 sm:mb-0">
 <label className="font-medium text-gray-700">
 {field.label}
 {field.required && <span className="text-red-500 ml-1">*</span>}
 </label>
 <div className="text-xs text-gray-500 mt-1">
 {field.type.replace('_', ' ')}
 </div>
 </div>
 <div className="sm:w-2/3">
 {renderFieldValue(field, value)}
 </div>
 </div>
 </div>
 );
 })}
 </div>

 {/* Contact Information */}
 <div className="mt-8 pt-6 border-t border-gray-200">
 <h3 className="text-lg font-semibold text-gray-900 mb-4">Contact Information</h3>
 <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
 <div>
 <label className="font-medium text-gray-700">Vendor Name:</label>
 <div className="text-gray-900">{submission.vendor_name}</div>
 </div>
 <div>
 <label className="font-medium text-gray-700">Email:</label>
 <div>
 <a href={`mailto:${submission.vendor_email}`} className="text-blue-600 hover:text-blue-800">
 {submission.vendor_email}
 </a>
 </div>
 </div>
 </div>
 </div>
 </div>

 {/* Footer */}
 <div className="text-center text-sm text-gray-500 mt-8 print:mt-4">
  <p>Generated from Wedding Planning Platform • {formatDate(new Date())}</p>
 </div>
 </div>
 </div>
 );
}