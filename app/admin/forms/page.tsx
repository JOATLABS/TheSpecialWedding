'use client';

import React, { useState, useEffect } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';

interface Form {
 id: string;
 name: string;
 settings: {
 title: string;
 description?: string;
 is_public: boolean;
 };
 template_type?: string;
 wedding_id?: string;
 submission_count: number;
 created_at: string;
 is_active: boolean;
}

interface FormTemplate {
 id: string;
 name: string;
 description: string;
 category: string;
}

export default function FormsManagementPage() {
 const { token, userProfile } = useAdmin();
 const router = useRouter();
 const [forms, setForms] = useState<Form[]>([]);
 const [templates, setTemplates] = useState<FormTemplate[]>([]);
 const [loading, setLoading] = useState(true);
 const [error, setError] = useState('');
 const [showCreateModal, setShowCreateModal] = useState(false);
 const [selectedTemplate, setSelectedTemplate] = useState('');
 const [formName, setFormName] = useState('');
 const [creating, setCreating] = useState(false);

 useEffect(() => {
 if (!token) {
 router.push('/admin/login');
 return;
 }

 if (!userProfile || (!userProfile.is_wedding_planner && !userProfile.is_root_admin)) {
 router.push('/admin');
 return;
 }

 fetchForms();
 fetchTemplates();
 }, [token, userProfile, router]);

 const fetchForms = async () => {
 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const response = await fetch(`${baseUrl}/admin/forms`, {
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 });

 if (response.ok) {
 const data = await response.json();
 setForms(data);
 } else {
 setError('Failed to fetch forms');
 }
 } catch (error) {
 setError('Failed to fetch forms');
 } finally {
 setLoading(false);
 }
 };

 const fetchTemplates = async () => {
 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const response = await fetch(`${baseUrl}/admin/form-templates`, {
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 });

 if (response.ok) {
 const data = await response.json();
 setTemplates(data.templates);
 }
 } catch (error) {
 // Template fetch failed - this is optional functionality
 }
 };

 const createFormFromTemplate = async () => {
 if (!selectedTemplate || !formName) return;

 setCreating(true);
 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const response = await fetch(
 `${baseUrl}/admin/forms/from-template/${selectedTemplate}?form_name=${encodeURIComponent(formName)}`,
 {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 }
 );

 if (response.ok) {
 const data = await response.json();
 setShowCreateModal(false);
 setFormName('');
 setSelectedTemplate('');
 await fetchForms();
 } else {
 setError('Failed to create form');
 }
 } catch (error) {
 setError('Failed to create form');
 } finally {
 setCreating(false);
 }
 };

 const deleteForm = async (formId: string) => {
 if (!confirm('Are you sure you want to delete this form?')) return;

 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const response = await fetch(`${baseUrl}/admin/forms/${formId}`, {
 method: 'DELETE',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 });

 if (response.ok) {
 await fetchForms();
 } else {
 setError('Failed to delete form');
 }
 } catch (error) {
 setError('Failed to delete form');
 }
 };

 const formatDate = (dateString: string) => {
 return new Date(dateString).toLocaleDateString('en-US', {
 year: 'numeric',
 month: 'short',
 day: 'numeric'
 });
 };

 if (loading) {
 return (
 <div className="min-h-screen flex items-center justify-center">
 <div className="text-center">
 <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
 <p className="text-gray-600">Loading forms...</p>
 </div>
 </div>
 );
 }

 return (
 <div className="space-y-6">
 {/* Header */}
 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
 <div className="flex items-center justify-between">
 <div>
 <h1 className="text-2xl font-bold text-gray-900 mb-2">Form Builder</h1>
 <p className="text-gray-600">Create and manage custom forms for feedback and data collection</p>
 </div>
 <button
 onClick={() => setShowCreateModal(true)}
 className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
 >
 Create New Form
 </button>
 </div>
 </div>

 {error && (
 <div className="bg-red-50 border border-red-200 rounded-lg p-4">
 <p className="text-red-600">{error}</p>
 </div>
 )}

 {/* Forms List */}
 <div className="bg-white rounded-lg shadow-sm border border-gray-200">
 <div className="px-6 py-4 border-b border-gray-200">
 <h2 className="text-lg font-semibold text-gray-900">Your Forms</h2>
 </div>

 <div className="divide-y divide-gray-200">
 {forms.length === 0 ? (
 <div className="p-6 text-center text-gray-500">
 <div className="w-12 h-12 mx-auto mb-4 text-gray-300">
 
 </div>
 <h3 className="text-lg font-medium text-gray-900 mb-2">No forms created yet</h3>
 <p className="text-gray-500">Get started by creating your first form from a template.</p>
 </div>
 ) : (
 forms.map((form) => (
 <div key={form.id} className="p-6 hover:bg-gray-50 transition-colors">
 <div className="flex items-center justify-between">
 <div className="flex-1">
 <h3 className="text-lg font-semibold text-gray-900 mb-1">
 {form.name}
 </h3>
 <p className="text-sm text-gray-600 mb-2">
 {form.settings.description || form.settings.title}
 </p>
 <div className="flex items-center space-x-4 text-sm text-gray-500">
 <span>Responses: {form.submission_count}</span>
 <span>Created: {formatDate(form.created_at)}</span>
 {form.template_type && (
 <span>Type: {form.template_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
 )}
 <span className={`px-2 py-1 rounded-full text-xs ${
 form.settings.is_public ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
 }`}>
 {form.settings.is_public ? 'Public' : 'Private'}
 </span>
 </div>
 </div>
 <div className="flex space-x-2">
 <button
 onClick={() => router.push(`/admin/forms/${form.id}/edit`)}
 className="bg-purple-100 text-purple-700 px-3 py-1 rounded-lg text-sm hover:bg-purple-200 transition-colors"
 >
 Edit
 </button>
 <button
 onClick={() => router.push(`/admin/forms/${form.id}/responses`)}
 className="bg-blue-100 text-blue-700 px-3 py-1 rounded-lg text-sm hover:bg-blue-200 transition-colors"
 >
 View Responses ({form.submission_count})
 </button>
 <button
 onClick={() => router.push(`/admin/forms/${form.id}/send`)}
 className="bg-green-100 text-green-700 px-3 py-1 rounded-lg text-sm hover:bg-green-200 transition-colors"
 >
 Send Form
 </button>
 <button
 onClick={() => router.push(`/admin/forms/${form.id}/analytics`)}
 className="bg-purple-100 text-purple-700 px-3 py-1 rounded-lg text-sm hover:bg-purple-200 transition-colors"
 >
 Analytics
 </button>
 <a
 href={`${window.location.protocol}//${window.location.host}/forms/${form.id}`}
 target="_blank"
 className="bg-gray-100 text-gray-700 px-3 py-1 rounded-lg text-sm hover:bg-gray-200 transition-colors inline-block"
 >
 Preview
 </a>
 <button
 onClick={() => deleteForm(form.id)}
 className="bg-red-100 text-red-700 px-3 py-1 rounded-lg text-sm hover:bg-red-200 transition-colors"
 >
 Delete
 </button>
 </div>
 </div>
 </div>
 ))
 )}
 </div>
 </div>

 {/* Create Form Modal */}
 {showCreateModal && (
 <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
 <div className="bg-white rounded-lg p-6 w-full max-w-md">
 <h3 className="text-lg font-semibold text-gray-900 mb-4">Create New Form</h3>
 
 <div className="space-y-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">Form Name</label>
 <input
 type="text"
 value={formName}
 onChange={(e) => setFormName(e.target.value)}
 placeholder="Enter form name..."
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">Template</label>
 <select
 value={selectedTemplate}
 onChange={(e) => setSelectedTemplate(e.target.value)}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
 >
 <option value="">Select a template...</option>
 {templates.map((template) => (
 <option key={template.id} value={template.id}>
 {template.name} - {template.description}
 </option>
 ))}
 </select>
 </div>
 </div>

 <div className="flex space-x-4 mt-6">
 <button
 onClick={() => setShowCreateModal(false)}
 className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
 >
 Cancel
 </button>
 <button
 onClick={createFormFromTemplate}
 disabled={!selectedTemplate || !formName || creating}
 className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-gray-300 transition-colors"
 >
 {creating ? 'Creating...' : 'Create Form'}
 </button>
 </div>
 </div>
 </div>
 )}
 </div>
 );
}