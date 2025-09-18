'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';

interface Form {
 id: string;
 name: string;
 settings: {
 title: string;
 description?: string;
 };
 fields: any[];
}

interface EmailSettings {
 subject: string;
 message: string;
 sender_name: string;
 include_form_link: boolean;
 send_reminder: boolean;
 reminder_days: number;
}

export default function SendFormPage() {
 const params = useParams();
 const router = useRouter();
 const { token } = useAdmin();
 const formId = params.id as string;

 const [form, setForm] = useState<Form | null>(null);
 const [loading, setLoading] = useState(true);
 const [sending, setSending] = useState(false);
 const [error, setError] = useState('');
 const [success, setSuccess] = useState('');

 // Email configuration
 const [recipients, setRecipients] = useState<string[]>(['']);
 const [emailSettings, setEmailSettings] = useState<EmailSettings>({
 subject: '',
 message: '',
 sender_name: '',
 include_form_link: true,
 send_reminder: false,
 reminder_days: 7
 });

 // Recipient categories
 const [recipientCategory, setRecipientCategory] = useState<'couples' | 'wedding_party' | 'vendors' | 'custom'>('custom');

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
 
 // Set default email settings
 setEmailSettings(prev => ({
 ...prev,
 subject: `Please complete: ${data.settings.title}`,
 sender_name: 'Your Wedding Planner',
 message: `Hi there!\n\nI hope this message finds you well. I've prepared a form for you to complete that will help us make your special day perfect.\n\nPlease take a few minutes to fill it out - your input is invaluable to creating the wedding of your dreams.`
 }));
 } else {
 setError('Failed to load form');
 }
 } catch (error) {
 setError('Failed to load form');
 } finally {
 setLoading(false);
 }
 };

 const addRecipient = () => {
 setRecipients([...recipients, '']);
 };

 const removeRecipient = (index: number) => {
 setRecipients(recipients.filter((_, i) => i !== index));
 };

 const updateRecipient = (index: number, email: string) => {
 const updated = [...recipients];
 updated[index] = email;
 setRecipients(updated);
 };

 const loadPredefinedRecipients = (category: 'couples' | 'wedding_party' | 'vendors') => {
 // This would typically fetch from your wedding data
 const predefined = {
 couples: ['bride@example.com', 'groom@example.com'],
 wedding_party: ['bridesmaid1@example.com', 'bridesmaid2@example.com', 'groomsman1@example.com'],
 vendors: ['photographer@example.com', 'caterer@example.com', 'florist@example.com']
 };
 
 setRecipients(predefined[category]);
 };

 const validateForm = () => {
 const validEmails = recipients.filter(email => 
 email.trim() && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
 );

 if (validEmails.length === 0) {
 setError('Please add at least one valid email address');
 return false;
 }

 if (!emailSettings.subject.trim()) {
 setError('Please enter an email subject');
 return false;
 }

 if (!emailSettings.sender_name.trim()) {
 setError('Please enter your name');
 return false;
 }

 if (!emailSettings.message.trim()) {
 setError('Please enter a message');
 return false;
 }

 return true;
 };

 const sendForm = async () => {
 if (!validateForm()) return;

 setSending(true);
 setError('');
 setSuccess('');

 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL!;
 
 const validEmails = recipients.filter(email => 
 email.trim() && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
 );

 const response = await fetch(`${baseUrl}/admin/forms/${formId}/send`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 body: JSON.stringify({
 recipient_emails: validEmails,
 email_settings: emailSettings
 }),
 });

 if (response.ok) {
 const data = await response.json();
 setSuccess(`Form sent successfully to ${data.sent} recipients! ${data.failed > 0 ? `(${data.failed} failed)` : ''}`);
 
 // Show form URL for manual sharing
 if (data.form_url) {
 setSuccess(prev => prev + `\n\nForm URL for manual sharing: ${data.form_url}`);
 }
 } else {
 const errorData = await response.json();
 setError(errorData.detail || 'Failed to send form');
 }
 } catch (error) {
 setError('Failed to send form. Please check your connection and try again.');
 } finally {
 setSending(false);
 }
 };

 if (loading) {
 return (
 <div className="min-h-screen flex items-center justify-center">
 <div className="text-center">
 <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
 <p className="text-gray-600 dark:text-gray-300">Loading form...</p>
 </div>
 </div>
 );
 }

 if (!form) {
 return (
 <div className="min-h-screen flex items-center justify-center">
 <div className="text-center">
 <p className="text-red-600 mb-4">Form not found</p>
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
 <div className="max-w-4xl mx-auto py-8 px-4">
 {/* Header */}
 <div className="mb-8">
 <div className="flex items-center justify-between mb-4">
 <button
 onClick={() => router.push('/admin/forms')}
 className="flex items-center text-gray-600 dark:text-gray-300 hover:text-gray-800"
 >
 <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
 </svg>
 Back to Forms
 </button>
 </div>
 
 <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 p-6">
 <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">Send Form</h1>
 <div className="flex items-center text-gray-600 dark:text-gray-300">
 <span className="text-lg font-medium">{form.name}</span>
 <span className="mx-2">•</span>
 <span>{form.settings.title}</span>
 </div>
 {form.settings.description && (
 <p className="text-gray-500 dark:text-gray-400 mt-2">{form.settings.description}</p>
 )}
 </div>
 </div>

 <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
 {/* Main Content */}
 <div className="lg:col-span-2 space-y-6">
 {/* Recipients */}
 <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 p-6">
 <h2 className="text-xl font-semibold mb-4">Recipients</h2>
 
 {/* Quick Categories */}
 <div className="mb-6">
 <p className="text-sm text-gray-600 dark:text-gray-300 mb-3">Quick add recipients:</p>
 <div className="flex flex-wrap gap-2">
 <button
 onClick={() => loadPredefinedRecipients('couples')}
 className="px-3 py-1 text-sm bg-pink-100 text-pink-800 rounded-full hover:bg-pink-200 transition-colors"
 >
 Couples
 </button>
 <button
 onClick={() => loadPredefinedRecipients('wedding_party')}
 className="px-3 py-1 text-sm bg-purple-100 text-purple-800 rounded-full hover:bg-purple-200 transition-colors"
 >
 Wedding Party
 </button>
 <button
 onClick={() => loadPredefinedRecipients('vendors')}
 className="px-3 py-1 text-sm bg-blue-100 text-blue-800 rounded-full hover:bg-blue-200 transition-colors"
 >
 Vendors
 </button>
 </div>
 </div>

 {/* Email List */}
 <div className="space-y-3">
 {recipients.map((email, index) => (
 <div key={index} className="flex gap-2">
 <input
 type="email"
 value={email}
 onChange={(e) => updateRecipient(index, e.target.value)}
 placeholder="recipient@example.com"
 className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 {recipients.length > 1 && (
 <button
 onClick={() => removeRecipient(index)}
 className="px-3 py-2 text-red-600 hover:text-red-800"
 >
 
 </button>
 )}
 </div>
 ))}
 </div>

 <button
 onClick={addRecipient}
 className="mt-4 text-blue-600 hover:text-blue-800 text-sm font-medium"
 >
 + Add another recipient
 </button>
 </div>

 {/* Email Settings */}
 <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 p-6">
 <h2 className="text-xl font-semibold mb-4">Email Settings</h2>
 
 <div className="space-y-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Your Name
 </label>
 <input
 type="text"
 value={emailSettings.sender_name}
 onChange={(e) => setEmailSettings(prev => ({ ...prev, sender_name: e.target.value }))}
 placeholder="Your Wedding Planner"
 className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Email Subject
 </label>
 <input
 type="text"
 value={emailSettings.subject}
 onChange={(e) => setEmailSettings(prev => ({ ...prev, subject: e.target.value }))}
 placeholder="Please complete: Your Wedding Form"
 className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Personal Message
 </label>
 <textarea
 value={emailSettings.message}
 onChange={(e) => setEmailSettings(prev => ({ ...prev, message: e.target.value }))}
 rows={6}
 placeholder="Add a personal message to your recipients..."
 className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
 This message will appear before the form link in the email.
 </p>
 </div>

 {/* Advanced Options */}
 <div className="border-t pt-4">
 <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Advanced Options</h3>
 
 <div className="space-y-3">
 <label className="flex items-center">
 <input
 type="checkbox"
 checked={emailSettings.include_form_link}
 onChange={(e) => setEmailSettings(prev => ({ ...prev, include_form_link: e.target.checked }))}
 className="rounded mr-2"
 />
 <span className="text-sm">Include direct form link in email</span>
 </label>

 <label className="flex items-center">
 <input
 type="checkbox"
 checked={emailSettings.send_reminder}
 onChange={(e) => setEmailSettings(prev => ({ ...prev, send_reminder: e.target.checked }))}
 className="rounded mr-2"
 />
 <span className="text-sm">Send reminder emails</span>
 </label>

 {emailSettings.send_reminder && (
 <div className="ml-6">
 <label className="block text-sm text-gray-600 dark:text-gray-300">
 Send reminder after:
 <select
 value={emailSettings.reminder_days}
 onChange={(e) => setEmailSettings(prev => ({ ...prev, reminder_days: parseInt(e.target.value) }))}
 className="ml-2 px-2 py-1 border border-gray-300 rounded"
 >
 <option value={3}>3 days</option>
 <option value={7}>7 days</option>
 <option value={14}>14 days</option>
 </select>
 </label>
 </div>
 )}
 </div>
 </div>
 </div>
 </div>
 </div>

 {/* Sidebar */}
 <div className="space-y-6">
 {/* Send Button */}
 <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 p-6">
 <button
 onClick={sendForm}
 disabled={sending}
 className={`w-full px-6 py-3 rounded-lg font-medium transition-colors ${
 sending
 ? 'bg-gray-300 text-gray-500 dark:text-gray-400 cursor-not-allowed'
 : 'bg-blue-600 text-white hover:bg-blue-700'
 }`}
 >
 {sending ? (
 <div className="flex items-center justify-center">
 <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
 Sending...
 </div>
 ) : (
 'Send Form'
 )}
 </button>

 <p className="text-sm text-gray-500 dark:text-gray-400 mt-2 text-center">
 Recipients will receive an email with a link to complete the form
 </p>
 </div>

 {/* Status Messages */}
 {error && (
 <div className="bg-red-50 border border-red-200 rounded-lg p-4">
 <div className="flex items-center">
 <svg className="w-5 h-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
 </svg>
 <p className="text-red-700 text-sm">{error}</p>
 </div>
 </div>
 )}

 {success && (
 <div className="bg-green-50 border border-green-200 rounded-lg p-4">
 <div className="flex items-start">
 <svg className="w-5 h-5 text-green-500 mr-2 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
 </svg>
 <div className="text-green-700 text-sm whitespace-pre-line">{success}</div>
 </div>
 </div>
 )}

 {/* Form Preview */}
 <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 p-6">
 <h3 className="text-lg font-semibold mb-4">Form Preview</h3>
 <div className="text-sm text-gray-600 dark:text-gray-300 space-y-2">
 <p><strong>Title:</strong> {form.settings.title}</p>
 {form.settings.description && (
 <p><strong>Description:</strong> {form.settings.description}</p>
 )}
 <p><strong>Fields:</strong> {form.fields.length} questions</p>
 
 <button
 onClick={() => window.open(`/forms/${form.id}`, '_blank')}
 className="mt-4 w-full px-4 py-2 bg-gray-100 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 transition-colors"
 >
 Preview Form →
 </button>
 </div>
 </div>
 </div>
 </div>
 </div>
 </div>
 );
}