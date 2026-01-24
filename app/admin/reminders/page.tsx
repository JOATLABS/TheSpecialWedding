'use client';

import { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { formatDateTime } from '@/utils/dateFormat';
import { MultiSelect } from '@/components/ui/MultiSelect';
import { MessageEnrichment } from '@/components/ui/MessageEnrichment';
import { Sparkles, X } from 'lucide-react';
import PageHeader from '../components/PageHeader';

interface Wedding {
 id?: string;
 _id?: string;
 couple_names: string;
 date: string;
 slug: string;
 events?: Array<{
 type: string;
 date: string;
 }>;
}

interface Guest {
 id?: string;
 _id?: string;
 wedding_id: string;
 name: string;
 token: string;
 phone?: string;
 email?: string;
 role: string;
 plus_one_allowed: boolean;
}

interface MessageLog {
 phone?: string;
 to?: string; // For email logs
 guest_id: string;
 message?: string;
 subject?: string; // For email logs
 target_type: 'guest' | 'plus-one';
 event_type?: string;
 email_type?: string; // For email logs
 status: string;
 sent_at: string;
 provider?: 'twilio' | 'telnyx' | 'resend'; // Track which service was used
}

export default function AdminRemindersPage() {
 const { token } = useAdmin();
 const [weddings, setWeddings] = useState<Wedding[]>([]);
 const [selectedWedding, setSelectedWedding] = useState<string>('');
 const [guests, setGuests] = useState<Guest[]>([]);
 const [messageHistory, setMessageHistory] = useState<MessageLog[]>([]);
 const [loading, setLoading] = useState(false);
 const [error, setError] = useState<string>('');
 const [success, setSuccess] = useState<string>('');
 const [activeTab, setActiveTab] = useState<'invites' | 'reminders' | 'individual' | 'history'>('invites');
 const [channel, setChannel] = useState<'sms' | 'email' | 'both'>('sms');
 const [emailSubject, setEmailSubject] = useState<string>('');
 const [emailHtml, setEmailHtml] = useState<string>('');
 const [emailAttachment, setEmailAttachment] = useState<File | null>(null);
 const [showEmailPreview, setShowEmailPreview] = useState(false);
 const [emailPreviewHtml, setEmailPreviewHtml] = useState<string>('');

 // Form states
 const [eventType, setEventType] = useState<string>('traditional');
 const [targetGroup, setTargetGroup] = useState<string>('guests');
 const [customMessage, setCustomMessage] = useState<string>('');
 const [inviteMessage, setInviteMessage] = useState<string>('');
 const [selectedGuests, setSelectedGuests] = useState<string[]>([]);

 // AI Drafting states
 const [showAiDraftModal, setShowAiDraftModal] = useState(false);
 const [aiDraftLoading, setAiDraftLoading] = useState(false);
 const [aiDraftTone, setAiDraftTone] = useState<'formal' | 'friendly' | 'casual'>('friendly');
 const [aiDraftType, setAiDraftType] = useState<string>('rsvp_reminder');
 const [aiDraftTarget, setAiDraftTarget] = useState<'customMessage' | 'inviteMessage'>('customMessage');
 const [aiDraftError, setAiDraftError] = useState<string | null>(null);

 const formatLogTimestamp = (timestamp: string) =>
   formatDateTime(timestamp, {
     month: 'short',
     day: 'numeric',
     year: 'numeric',
     hour: 'numeric',
     minute: '2-digit',
   });

 const fetchWeddings = useCallback(async () => {
 if (!token) return;

 try {
 const baseUrl = getApiBaseUrl();
 const response = await fetch(`${baseUrl}/admin/weddings`, {
   headers: {
     'Authorization': `Bearer ${token}`,
     'Content-Type': 'application/json',
   },
 });
 const data = await response.json();
 setWeddings(Array.isArray(data) ? data : []);
 } catch (err) {
 setError('Failed to load weddings');
 }
 }, [token]);

 const fetchGuests = useCallback(async () => {
 if (!selectedWedding || !token) return;

 try {
 const baseUrl = getApiBaseUrl();
 const response = await fetch(
 `${baseUrl}/admin/guests?wedding_id=${selectedWedding}`,
 {
 headers: { 'Authorization': `Bearer ${token}` },
 }
 );

 if (!response.ok) {
 console.error('Failed to fetch guests:', response.status);
 return;
 }

 const data = await response.json();
 console.log('Fetched guests:', Array.isArray(data) ? data.length : 0, 'guests');
 setGuests(Array.isArray(data) ? data : []);
 } catch (err) {
 console.error('Failed to load guests:', err);
 }
 }, [selectedWedding, token]);

 const fetchMessageHistory = useCallback(async () => {
 if (!token) return;

 try {
 const baseUrl = getApiBaseUrl();

 // Fetch both SMS and Email logs
 const [smsResponse, emailResponse] = await Promise.all([
 fetch(`${baseUrl}/admin/reminders/logs`, {
 headers: { 'Authorization': `Bearer ${token}` },
 }),
 fetch(`${baseUrl}/admin/email/logs?limit=100`, {
 headers: { 'Authorization': `Bearer ${token}` },
 })
 ]);

 const smsData = smsResponse.ok ? await smsResponse.json() : [];
 const emailData = emailResponse.ok ? await emailResponse.json() : { logs: [] };

 // Combine and sort by date
 const combined = [
 ...(Array.isArray(smsData) ? smsData : []),
 ...(Array.isArray(emailData.logs) ? emailData.logs : [])
 ].sort((a, b) => new Date(b.sent_at).getTime() - new Date(a.sent_at).getTime());

 setMessageHistory(combined);
 } catch (err) {
 console.error('Failed to load message history:', err);
 }
 }, [token]);

 useEffect(() => {
 fetchWeddings();
 if (token) {
 fetchMessageHistory();
 }
 }, [fetchMessageHistory, fetchWeddings, token]);

 useEffect(() => {
 if (selectedWedding && token) {
 fetchGuests();
 }
 }, [fetchGuests, selectedWedding, token]);

 const handleSendInviteLinks = async () => {
 if (!selectedWedding) {
 setError('Please select a wedding');
 return;
 }

 const selectedWeddingData = weddings.find(w => (w.id || w._id) === selectedWedding);
 if (!selectedWeddingData?.slug) {
 setError('Wedding slug not found');
 return;
 }

 setLoading(true);
 setError('');
 setSuccess('');

 try {
 const baseUrl = getApiBaseUrl();
 let totalSent = 0;
 let totalFailed = 0;

 // Send SMS invites
 if (channel === 'sms' || channel === 'both') {
 const response = await fetch(`${baseUrl}/admin/reminders/send-personalized-links`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 body: JSON.stringify({
 slug: selectedWeddingData.slug,
 custom_message: inviteMessage.trim() || null
 }),
 });

 if (response.ok) {
 const result = await response.json();
 totalSent += result.sent || 0;
 }
 }

 // Send Email invites
 if (channel === 'email' || channel === 'both') {
 let response;

 if (emailAttachment) {
 // Use multipart/form-data endpoint when attachment is present
 const formData = new FormData();
 formData.append('wedding_slug', selectedWeddingData.slug);
 if (emailSubject) formData.append('custom_subject', emailSubject);
 if (emailHtml) formData.append('custom_html', emailHtml);
 formData.append('attachment', emailAttachment);

 response = await fetch(`${baseUrl}/admin/email/send-invites-with-attachment`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 },
 body: formData,
 });
 } else {
 // Use JSON endpoint when no attachment
 response = await fetch(`${baseUrl}/admin/email/send-invites`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 body: JSON.stringify({
 wedding_slug: selectedWeddingData.slug,
 custom_subject: emailSubject || null,
 custom_html: emailHtml || null
 }),
 });
 }

 if (response.ok) {
 const result = await response.json();
 totalSent += result.sent || 0;
 totalFailed += result.failed || 0;
 }
 }

 const channelText = channel === 'both' ? 'SMS and email' : channel;
 setSuccess(`Successfully sent ${totalSent} invites via ${channelText}!${totalFailed > 0 ? ` (${totalFailed} failed)` : ''}`);
 fetchMessageHistory();
 } catch (err) {
 setError(err instanceof Error ? err.message : 'Failed to send invites');
 } finally {
 setLoading(false);
 }
 };

 const handleSendEventReminder = async () => {
 if (!selectedWedding) {
 setError('Please select a wedding');
 return;
 }

 const selectedWeddingData = weddings.find(w => (w.id || w._id) === selectedWedding);
 if (!selectedWeddingData?.slug) {
 setError('Wedding slug not found');
 return;
 }

 if (!customMessage.trim() && channel !== 'email') {
 setError('Please enter a message');
 return;
 }

 setLoading(true);
 setError('');
 setSuccess('');

 try {
 const baseUrl = getApiBaseUrl();
 let totalSent = 0;
 let totalFailed = 0;

 // Send SMS reminders
 if (channel === 'sms' || channel === 'both') {
 const params = new URLSearchParams({
 event_type: eventType,
 message: customMessage,
 target_group: targetGroup,
 });

 const response = await fetch(`${baseUrl}/admin/reminders/send?${params}`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 },
 });

 if (response.ok) {
 const result = await response.json();
 totalSent += result.sent || 0;
 }
 }

 // Send Email reminders
 if (channel === 'email' || channel === 'both') {
 const response = await fetch(`${baseUrl}/admin/email/send-reminders`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 body: JSON.stringify({
 wedding_slug: selectedWeddingData.slug,
 event_type: eventType,
 custom_subject: emailSubject || null,
 custom_html: emailHtml || customMessage || null,
 target_group: targetGroup
 }),
 });

 if (response.ok) {
 const result = await response.json();
 totalSent += result.sent || 0;
 totalFailed += result.failed || 0;
 }
 }

 if (totalSent === 0) {
 setError('No reminders sent. Make sure guests have RSVP\'d for the selected event type.');
 } else {
 const channelText = channel === 'both' ? 'SMS and email' : channel;
 setSuccess(`Successfully sent ${totalSent} reminders via ${channelText}!${totalFailed > 0 ? ` (${totalFailed} failed)` : ''}`);
 setCustomMessage('');
 setEmailSubject('');
 setEmailHtml('');
 fetchMessageHistory();
 }
 } catch (err) {
 setError(err instanceof Error ? err.message : 'Failed to send reminders');
 } finally {
 setLoading(false);
 }
 };

 const handleSendIndividualMessage = async () => {
 if (!customMessage.trim() || selectedGuests.length === 0) {
 setError('Please select guests and enter a message');
 return;
 }

 setLoading(true);
 setError('');
 setSuccess('');

 try {
 const baseUrl = getApiBaseUrl();
 const response = await fetch(`${baseUrl}/admin/reminders/send-to-guests`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 body: JSON.stringify({
 guest_tokens: selectedGuests,
 message: customMessage,
 }),
 });

 if (!response.ok) {
 const errorData = await response.json();
 throw new Error(errorData.detail || 'Failed to send messages');
 }

 const result = await response.json();
 if (result.sent > 0) {
 setSuccess(`Successfully sent messages to ${result.sent} guests!${result.failed > 0 ? ` (${result.failed} failed)` : ''}`);
 } else {
 setError('No messages sent. Guests may have opted out or have no phone numbers.');
 }
 setCustomMessage('');
 setSelectedGuests([]);
 fetchMessageHistory();
 } catch (err) {
 setError(err instanceof Error ? err.message : 'Failed to send messages');
 } finally {
 setLoading(false);
 }
 };

 // AI Draft handler
 const handleAiDraft = async () => {
   if (!selectedWedding) {
     setAiDraftError('Please select a wedding first');
     return;
   }

   setAiDraftLoading(true);
   setAiDraftError(null);

   try {
     const baseUrl = getApiBaseUrl();
     const response = await fetch(`${baseUrl}/admin/ai/generate-message`, {
       method: 'POST',
       headers: {
         'Authorization': `Bearer ${token}`,
         'Content-Type': 'application/json',
       },
       body: JSON.stringify({
         message_type: aiDraftType,
         wedding_id: selectedWedding,
         tone: aiDraftTone,
         recipient_context: targetGroup === 'guests' ? 'wedding guest' : 'plus one',
         couple_names: selectedWeddingData?.couple_names,
         wedding_date: selectedWeddingData?.date,
         event_name: eventType.replace('_', ' '),
       }),
     });

     if (!response.ok) {
       const error = await response.json();
       throw new Error(error.detail || 'Failed to generate message');
     }

     const data = await response.json();
     const messageContent = data.message;

     // Apply the generated message to the appropriate field
     if (aiDraftTarget === 'customMessage') {
       if (channel === 'sms' || channel === 'both') {
         setCustomMessage(messageContent.sms_version || messageContent.body || '');
       } else {
         setCustomMessage(messageContent.body || '');
       }
       if ((channel === 'email' || channel === 'both') && messageContent.subject) {
         setEmailSubject(messageContent.subject);
       }
     } else {
       setInviteMessage(messageContent.sms_version || messageContent.body || '');
     }

     setShowAiDraftModal(false);
     setSuccess('AI message generated! Review and edit as needed.');
   } catch (err) {
     setAiDraftError(err instanceof Error ? err.message : 'Failed to generate message');
   } finally {
     setAiDraftLoading(false);
   }
 };

 const openAiDraftModal = (target: 'customMessage' | 'inviteMessage') => {
   setAiDraftTarget(target);
   setAiDraftError(null);
   setShowAiDraftModal(true);
 };

 const selectedWeddingData = weddings.find(w => (w.id || w._id) === selectedWedding);
 const guestsWithPhone = guests.filter(g => g.phone && g.phone.trim() !== '');
 const guestsWithEmail = guests.filter(g => g.email && g.email.trim() !== '');
 const guestsWithPhoneOrEmail = guests.filter(g =>
 (g.phone && g.phone.trim() !== '') || (g.email && g.email.trim() !== '')
 );
 console.log('All guests:', guests);
 console.log('Guests with phone:', guestsWithPhone);
 console.log('Selected wedding:', selectedWedding);
 console.log('Token exists:', !!token);

 return (
 <div className="space-y-6">
 <div className="max-w-7xl mx-auto">
 <PageHeader
   title="Reminders & Invites"
   description="Send invitations and reminders via SMS or Email"
 />

 {/* Wedding Selection and Channel */}
 <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 mb-6">
 <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
 <div>
 <label htmlFor="wedding" className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 dark:text-gray-300 mb-2">
 Select Wedding
 </label>
 <select
 id="wedding"
 value={selectedWedding}
 onChange={(e) => setSelectedWedding(e.target.value)}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 >
 <option value="">Choose a wedding...</option>
 {weddings.map((wedding) => (
 <option key={wedding.id || wedding._id} value={wedding.id || wedding._id}>
 {wedding.couple_names} - {wedding.date}
 </option>
 ))}
 </select>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 dark:text-gray-300 mb-2">
 Communication Channel
 </label>
 <div className="flex gap-4">
 <label className="flex items-center">
 <input
 type="radio"
 value="sms"
 checked={channel === 'sms'}
 onChange={(e) => setChannel(e.target.value as 'sms' | 'email' | 'both')}
 className="mr-2"
 />
 <span>SMS</span>
 </label>
 <label className="flex items-center">
 <input
 type="radio"
 value="email"
 checked={channel === 'email'}
 onChange={(e) => setChannel(e.target.value as 'sms' | 'email' | 'both')}
 className="mr-2"
 />
 <span>Email</span>
 </label>
 <label className="flex items-center">
 <input
 type="radio"
 value="both"
 checked={channel === 'both'}
 onChange={(e) => setChannel(e.target.value as 'sms' | 'email' | 'both')}
 className="mr-2"
 />
 <span>Both</span>
 </label>
 </div>
 </div>
 </div>
 </div>

 {/* Status Messages */}
 {error && (
 <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
 <p className="text-red-700 dark:text-red-300 dark:text-red-300">{error}</p>
 </div>
 )}
 {success && (
 <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
 <p className="text-green-700 dark:text-green-300 dark:text-green-300">{success}</p>
 </div>
 )}

 {/* Tabs */}
 <div className="flex gap-4 mb-8">
 <button
 onClick={() => setActiveTab('invites')}
 className={`px-6 py-3 rounded-lg font-medium transition-colors ${
 activeTab === 'invites'
 ? 'bg-wedding-navy text-white'
 : 'bg-white text-wedding-navy dark:text-gray-100 hover:bg-gray-100 dark:bg-transparent'
 }`}
 >
 Send Invites
 </button>
 <button
 onClick={() => setActiveTab('reminders')}
 className={`px-6 py-3 rounded-lg font-medium transition-colors ${
 activeTab === 'reminders'
 ? 'bg-wedding-navy text-white'
 : 'bg-white text-wedding-navy dark:text-gray-100 hover:bg-gray-100 dark:bg-transparent'
 }`}
 >
 Event Reminders
 </button>
 <button
 onClick={() => setActiveTab('individual')}
 className={`px-6 py-3 rounded-lg font-medium transition-colors ${
 activeTab === 'individual'
 ? 'bg-wedding-navy text-white'
 : 'bg-white text-wedding-navy dark:text-gray-100 hover:bg-gray-100 dark:bg-transparent'
 }`}
 >
 Individual Messages
 </button>
 <button
 onClick={() => setActiveTab('history')}
 className={`px-6 py-3 rounded-lg font-medium transition-colors ${
 activeTab === 'history'
 ? 'bg-wedding-navy text-white'
 : 'bg-white text-wedding-navy dark:text-gray-100 hover:bg-gray-100 dark:bg-transparent'
 }`}
 >
 Message History ({messageHistory.length})
 </button>
 </div>

 {/* Send Invite Links Tab */}
 {activeTab === 'invites' && (
 <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
 <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100 mb-6">Send Wedding Invitations</h2>

 {selectedWedding ? (
 <div className="space-y-6">
 <div className="p-6 bg-gray-100 dark:bg-slate-700 dark:bg-transparent rounded-lg">
 <h3 className="font-semibold text-wedding-navy dark:text-gray-100 mb-2">Wedding Details:</h3>
 <p className="text-wedding-navy dark:text-gray-100">{selectedWeddingData?.couple_names}</p>
 <p className="text-sm text-gray-600 dark:text-gray-400 dark:text-gray-400 dark:text-gray-400">Date: {selectedWeddingData?.date}</p>
 <p className="text-sm text-gray-600 dark:text-gray-400 dark:text-gray-400 dark:text-gray-400">Slug: {selectedWeddingData?.slug}</p>
 <div className="mt-2 space-y-1">
 <p className="text-sm text-gray-600 dark:text-gray-400 dark:text-gray-400 dark:text-gray-400">
 Guests with phone numbers: {guestsWithPhone.length}
 </p>
 <p className="text-sm text-gray-600 dark:text-gray-400 dark:text-gray-400 dark:text-gray-400">
 Guests with email addresses: {guestsWithEmail.length}
 </p>
 <p className="text-sm text-gray-600 dark:text-gray-400 dark:text-gray-400 dark:text-gray-400">
 Total reachable guests: {guestsWithPhoneOrEmail.length}
 </p>
 </div>
 </div>

 {/* SMS Message Fields */}
 {(channel === 'sms' || channel === 'both') && (
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 dark:text-gray-300 mb-2">
 SMS Invitation Message (Optional)
 </label>
 <textarea
 value={inviteMessage}
 onChange={(e) => setInviteMessage(e.target.value)}
 placeholder="Enter custom SMS message..."
 rows={3}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 />
 <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Use {"{url}"} for the RSVP link and {"{name}"} for the guest’s name. Leave empty to use default message.
 </p>
 </div>
 )}

 {/* Email Fields */}
 {(channel === 'email' || channel === 'both') && (
 <>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 dark:text-gray-300 mb-2">
 Email Subject (Optional)
 </label>
 <input
 type="text"
 value={emailSubject}
 onChange={(e) => setEmailSubject(e.target.value)}
          placeholder={`You’re Invited - ${selectedWeddingData?.couple_names}`}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 dark:text-gray-300 mb-2">
 Custom Email HTML (Optional)
 </label>
 <textarea
 value={emailHtml}
 onChange={(e) => setEmailHtml(e.target.value)}
 placeholder="Enter custom HTML for email body. Leave empty to use beautiful default template..."
 rows={6}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent font-mono text-sm"
 />
 <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
 Available placeholders: {"{name}"}, {"{guest_name}"}, {"{url}"}, {"{rsvp_url}"}, {"{couple_names}"}, {"{wedding_date}"}
 </p>
 <div className="mt-2">
 <button
 type="button"
 onClick={async () => {
 const baseUrl = getApiBaseUrl();
 const response = await fetch(`${baseUrl}/admin/email/preview-invitation?guest_name=John Doe&couple_names=${selectedWeddingData?.couple_names}&wedding_date=${selectedWeddingData?.date}`, {
 headers: { 'Authorization': `Bearer ${token}` },
 });
 if (response.ok) {
 const data = await response.json();
 setEmailPreviewHtml(data.html);
 setShowEmailPreview(true);
 }
 }}
 className="text-sm text-wedding-rose hover:text-wedding-navy dark:text-gray-100"
 >
 Preview Default Email Template →
 </button>
 </div>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 dark:text-gray-300 mb-2">
 Email Attachment (Optional)
 </label>
 <div className="mt-1 flex items-center">
 <input
 type="file"
 onChange={(e) => {
 const file = e.target.files?.[0];
 if (file) {
 // Limit file size to 10MB
 if (file.size > 10 * 1024 * 1024) {
 setError('File size must be less than 10MB');
 return;
 }
 setEmailAttachment(file);
 }
 }}
 accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif"
 className="block w-full text-sm text-gray-500
 file:mr-4 file:py-2 file:px-4
 file:rounded-full file:border-0
 file:text-sm file:font-semibold
 file:bg-wedding-rose file:text-white
 hover:file:bg-wedding-rose-dark"
 />
 </div>
 {emailAttachment && (
 <div className="mt-2 flex items-center justify-between bg-gray-50 dark:bg-slate-700 p-2 rounded">
 <span className="text-sm text-gray-600 dark:text-gray-400 dark:text-gray-400 dark:text-gray-400">
 {emailAttachment.name} ({(emailAttachment.size / 1024 / 1024).toFixed(2)} MB)
 </span>
 <button
 type="button"
 onClick={() => setEmailAttachment(null)}
 className="text-red-500 hover:text-red-700 dark:text-red-300 text-sm"
 >
 Remove
 </button>
 </div>
 )}
 <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
 Accepted formats: PDF, Word documents, or images (max 10MB)
 </p>
 </div>
 </>
 )}

 {/* Message Preview */}
 {channel === 'sms' && inviteMessage.trim() && (
 <div className="p-6 bg-blue-50 rounded-lg">
 <h4 className="font-medium text-blue-900 mb-2">SMS Preview:</h4>
 <p className="text-blue-700 dark:text-blue-300 text-sm">
        “{inviteMessage.replace('{url}', `${process.env.NEXT_PUBLIC_FRONTEND_URL || ''}/${selectedWeddingData?.slug}/invite/[token]`).replace('{name}', '[Guest Name]')}”
 </p>
 </div>
 )}

 {/* Email Preview Modal */}
 {showEmailPreview && (
 <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
 <div className="bg-white dark:bg-slate-800 rounded-lg max-w-4xl max-h-[90vh] overflow-hidden">
 <div className="p-4 border-b flex justify-between items-center">
 <h3 className="text-lg font-semibold">Email Preview</h3>
 <button
 onClick={() => setShowEmailPreview(false)}
 className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:text-gray-300"
 >

 </button>
 </div>
 <div className="p-4 overflow-y-auto max-h-[70vh]">
 <iframe
 srcDoc={emailPreviewHtml}
 className="w-full h-[600px] border rounded"
 />
 </div>
 </div>
 </div>
 )}

 <button
 onClick={handleSendInviteLinks}
 disabled={loading || !selectedWedding}
 className="w-full bg-gradient-to-r from-wedding-sage to-wedding-gold text-white py-3 px-6 rounded-lg font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
 >
 {loading ? 'Sending...' : (
 channel === 'sms' ? `Send SMS Invites to ${guestsWithPhone.length} Guests` :
 channel === 'email' ? `Send Email Invites to ${guestsWithEmail.length} Guests` :
 `Send Invites to ${guestsWithPhoneOrEmail.length} Guests (SMS & Email)`
 )}
 </button>
 </div>
 ) : (
 <p className="text-gray-500 dark:text-gray-400 dark:text-gray-400">Please select a wedding to send invitations.</p>
 )}
 </div>
 )}

 {/* Event Reminders Tab */}
 {activeTab === 'reminders' && (
 <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
 <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100 mb-6">Send Event Reminders</h2>
 <div className="space-y-6">
 <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 dark:text-gray-300 mb-2">Event Type</label>
 <select
 value={eventType}
 onChange={(e) => setEventType(e.target.value)}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 >
 <option value="traditional">Traditional</option>
 <option value="white_wedding">White Wedding</option>
 <option value="reception">Reception</option>
 </select>
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 dark:text-gray-300 mb-2">Target Audience</label>
 <select
 value={targetGroup}
 onChange={(e) => setTargetGroup(e.target.value)}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 >
 <option value="guests">Guests Only</option>
 <option value="plus-ones">Plus-Ones Only</option>
 <option value="all">All (Guests + Plus-Ones)</option>
 </select>
 </div>
 </div>

 <div>
 <div className="flex items-center justify-between mb-2">
   <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Custom Message</label>
   <button
     type="button"
     onClick={() => openAiDraftModal('customMessage')}
     className="flex items-center gap-1 text-sm text-purple-600 hover:text-purple-700 dark:text-purple-400 dark:hover:text-purple-300"
   >
     <Sparkles className="w-4 h-4" />
     Draft with AI
   </button>
 </div>
 <textarea
 value={customMessage}
 onChange={(e) => setCustomMessage(e.target.value)}
 placeholder="Enter your reminder message..."
 rows={4}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 />
 <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
        This will be sent to guests who have RSVP’d for the {eventType.replace('_', ' ')} event.
 </p>
 <p className="text-sm text-yellow-600 mt-1">
        Note: If no messages are sent, guests may not have RSVP’d yet. Use “Send Invites” first to get responses.
 </p>
 </div>

 <button
 onClick={handleSendEventReminder}
 disabled={loading || !customMessage.trim()}
 className="w-full bg-gradient-to-r from-wedding-rose to-wedding-gold text-white py-3 px-6 rounded-lg font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
 >
 {loading ? 'Sending...' : 'Send Event Reminder'}
 </button>
 </div>
 </div>
 )}

 {/* Individual Messages Tab */}
 {activeTab === 'individual' && (
 <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
 <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100 mb-6">Send Individual Messages</h2>
 {selectedWedding ? (
 <div className="space-y-6">
 {/* Modern Multi-Select Dropdown */}
 <MultiSelect
 label={`Select Guests (${selectedGuests.length} selected)`}
 options={guestsWithPhone.map((guest) => ({
 value: guest.token,
 label: guest.name,
 sublabel: guest.phone || undefined,
 }))}
 selected={selectedGuests}
 onChange={setSelectedGuests}
 placeholder="Click to select guests..."
 searchPlaceholder="Search by name or phone..."
 emptyMessage="No guests with phone numbers found"
 />

 {/* Message Enrichment Options */}
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Add to Message
 </label>
 <MessageEnrichment
 onInsert={(text) => {
 setCustomMessage((prev) => prev ? `${prev}\n${text}` : text);
 }}
 />
 </div>

 {/* Message Textarea */}
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Message</label>
 <textarea
 value={customMessage}
 onChange={(e) => setCustomMessage(e.target.value)}
 placeholder="Enter your custom message..."
 rows={5}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent resize-none"
 />
 <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
 Tip: Use the buttons above to quickly add links, locations, or form references to your message.
 </p>
 </div>

 <button
 onClick={handleSendIndividualMessage}
 disabled={loading || !customMessage.trim() || selectedGuests.length === 0}
 className="w-full bg-gradient-to-r from-wedding-navy to-wedding-sage text-white py-3 px-6 rounded-lg font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
 >
 {loading ? 'Sending...' : `Send Message to ${selectedGuests.length} Guest(s)`}
 </button>
 </div>
 ) : (
 <p className="text-gray-500 dark:text-gray-400">Please select a wedding to send individual messages.</p>
 )}
 </div>
 )}

 {/* Message History Tab */}
 {activeTab === 'history' && (
 <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
 <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100 mb-6">Message History</h2>
 {messageHistory.length === 0 ? (
 <p className="text-gray-500 dark:text-gray-400 dark:text-gray-400">No messages sent yet.</p>
 ) : (
 <>
 {/* Mobile Card View */}
 <div className="md:hidden space-y-4">
 {messageHistory.map((log, index) => (
 <div key={index} className="bg-gray-50 dark:bg-slate-700/50 rounded-lg p-4 space-y-2">
 <div className="flex justify-between items-start">
 <div className="text-xs text-gray-500 dark:text-gray-400 dark:text-gray-400">
 {formatLogTimestamp(log.sent_at)}
 </div>
 <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
 log.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
 }`}>
 {log.status}
 </span>
 </div>
 <div className="font-semibold text-sm">{log.phone || log.to || 'N/A'}</div>
 <div className="flex gap-2">
 <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
 log.provider === 'resend' ? 'bg-indigo-100 text-indigo-800' : 'bg-green-100 text-green-800'
 }`}>
 {log.provider === 'resend' ? 'Email' : 'SMS'}
 </span>
 {log.target_type && (
 <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
 log.target_type === 'guest' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
 }`}>
 {log.target_type}
 </span>
 )}
 <span className="text-xs text-gray-600 dark:text-gray-400 dark:text-gray-400">{log.event_type || log.email_type || ''}</span>
 </div>
 <div className="text-sm text-gray-700 dark:text-gray-300 break-words">{log.message || log.subject || ''}</div>
 </div>
 ))}
 </div>

 {/* Desktop Table View */}
 <div className="hidden md:block overflow-x-auto">
 <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
 <thead className="bg-gray-50 dark:bg-slate-700">
 <tr>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Date/Time
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 To
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Channel
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Type
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Status
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Content
 </th>
 </tr>
 </thead>
 <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-gray-700">
 {messageHistory.map((log, index) => (
 <tr key={index}>
 <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100 dark:text-gray-100">
 {formatLogTimestamp(log.sent_at)}
 </td>
 <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100 dark:text-gray-100">
 {log.phone || log.to || 'N/A'}
 </td>
 <td className="px-6 py-4 whitespace-nowrap">
 <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
 log.provider === 'resend' ? 'bg-indigo-100 text-indigo-800' : 'bg-green-100 text-green-800'
 }`}>
 {log.provider === 'resend' ? 'Email' : 'SMS'}
 </span>
 </td>
 <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100 dark:text-gray-100">
 {log.target_type || log.email_type || log.event_type || '-'}
 </td>
 <td className="px-6 py-4 whitespace-nowrap">
 <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
 log.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
 }`}>
 {log.status}
 </span>
 </td>
 <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100 max-w-xs truncate">
 {log.message || log.subject || ''}
 </td>
 </tr>
 ))}
 </tbody>
 </table>
 </div>
 </>
 )}
 </div>
 )}
 </div>

 {/* AI Draft Modal */}
 {showAiDraftModal && (
   <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
     <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
       <div className="bg-gradient-to-r from-purple-600 to-indigo-600 px-6 py-4 flex items-center justify-between">
         <div className="flex items-center gap-2">
           <Sparkles className="w-5 h-5 text-white" />
           <h2 className="text-lg font-semibold text-white">AI Message Draft</h2>
         </div>
         <button onClick={() => setShowAiDraftModal(false)} className="text-white/80 hover:text-white">
           <X className="w-5 h-5" />
         </button>
       </div>

       <div className="p-6 space-y-4">
         {aiDraftError && (
           <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
             {aiDraftError}
           </div>
         )}

         <div>
           <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
             Message Type
           </label>
           <select
             value={aiDraftType}
             onChange={(e) => setAiDraftType(e.target.value)}
             className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
           >
             <option value="rsvp_reminder">RSVP Reminder</option>
             <option value="event_reminder">Event Reminder</option>
             <option value="save_the_date">Save the Date</option>
             <option value="thank_you">Thank You</option>
             <option value="vendor_reminder">Vendor Reminder</option>
             <option value="custom">Custom Message</option>
           </select>
         </div>

         <div>
           <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
             Tone
           </label>
           <div className="flex gap-2">
             {(['formal', 'friendly', 'casual'] as const).map((tone) => (
               <button
                 key={tone}
                 type="button"
                 onClick={() => setAiDraftTone(tone)}
                 className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium capitalize transition-colors ${
                   aiDraftTone === tone
                     ? 'bg-purple-600 text-white'
                     : 'bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-slate-600'
                 }`}
               >
                 {tone}
               </button>
             ))}
           </div>
         </div>

         <p className="text-sm text-gray-500 dark:text-gray-400">
           AI will generate a message based on your wedding details and selected options.
         </p>
       </div>

       <div className="border-t border-gray-200 dark:border-gray-700 px-6 py-4 flex justify-end gap-3">
         <button
           onClick={() => setShowAiDraftModal(false)}
           className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
         >
           Cancel
         </button>
         <button
           onClick={handleAiDraft}
           disabled={aiDraftLoading}
           className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
         >
           {aiDraftLoading ? (
             <>
               <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
               Generating...
             </>
           ) : (
             <>
               <Sparkles className="w-4 h-4" />
               Generate
             </>
           )}
         </button>
       </div>
     </div>
   </div>
 )}
 </div>
 );
}