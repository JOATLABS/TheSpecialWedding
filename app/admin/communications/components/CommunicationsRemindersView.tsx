'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { buildGuestOtpVerifyUrl } from '@/utils/rsvpLinks';
import { useAdmin } from '@/contexts/AdminContext';
import {
 canSendReminders,
 canSendRsvp,
} from '@/admin/utils/teamAccess';
import { formatDateTime } from '@/utils/dateFormat';
import { MultiSelect } from '@/components/ui/MultiSelect';
import { MessageEnrichment } from '@/components/ui/MessageEnrichment';
import { extractGuestList } from '@/admin/utils/guestListResponse';
import WeddingPicker from '@/admin/components/WeddingPicker';
import { Sparkles, X } from 'lucide-react';
import {
 ALL_WEDDING_EVENTS,
 getWeddingEventLabel,
 getWeddingReminderEventOptions,
} from '@/utils/weddingEvents';
import PageHeader from '../../components/PageHeader';
import { buildEventReminderEmailPayload } from './reminderPayloads';

export type CommunicationsTab = 'invites' | 'reminders' | 'individual' | 'history';

interface CommunicationsRemindersViewProps {
 forcedTab: CommunicationsTab;
}

interface Wedding {
 id?: string;
 _id?: string;
 couple_names: string;
 date: string;
 slug: string;
 events?: Array<{
 type: string;
 custom_type_label?: string;
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
 group_id?: string;
 plus_one_allowed: boolean;
 phone_status?: 'unknown' | 'valid' | 'invalid' | 'landline' | 'unreachable' | 'unsubscribed';
 sms_opt_in?: boolean;
 phone_error?: string;
 sms_opt_out_reason?: string;
}

interface PlusOne {
 id: string;
 _id?: string;
 guest_id: string;
 name: string;
 phone?: string;
 email?: string;
 sms_opt_in?: boolean;
 email_opt_in?: boolean;
 attending?: string[];
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
 // Delivery tracking fields (Twilio)
 message_sid?: string;
 delivery_status?: 'accepted' | 'queued' | 'sending' | 'sent' | 'delivered' | 'failed' | 'undelivered';
 delivery_status_updated_at?: string;
 error_code?: number;
 error_message?: string;
 // Fallback tracking
 fallback_channel?: 'email';
 fallback_status?: 'sent' | 'failed';
 fallback_email?: string;
}

export default function CommunicationsRemindersView({
 forcedTab,
}: CommunicationsRemindersViewProps) {
 const { token, userProfile } = useAdmin();
 const router = useRouter();
 const pathname = usePathname();
 const searchParams = useSearchParams();
 const lastAppliedTemplateRef = useRef<string | null>(null);
 const [weddings, setWeddings] = useState<Wedding[]>([]);
 const [selectedWedding, setSelectedWedding] = useState<string>('');
 const [guests, setGuests] = useState<Guest[]>([]);
 const [plusOnes, setPlusOnes] = useState<PlusOne[]>([]);
 const [messageHistory, setMessageHistory] = useState<MessageLog[]>([]);
 const [loading, setLoading] = useState(false);
 const [error, setError] = useState<string>('');
 const [success, setSuccess] = useState<string>('');
 const [channel, setChannel] = useState<'sms' | 'email' | 'both'>('sms');
 const [emailSubject, setEmailSubject] = useState<string>('');
 const [emailHtml, setEmailHtml] = useState<string>('');
 const [emailAttachment, setEmailAttachment] = useState<File | null>(null);
 const [showEmailPreview, setShowEmailPreview] = useState(false);
 const [emailPreviewHtml, setEmailPreviewHtml] = useState<string>('');

 // Form states
 const [eventType, setEventType] = useState<string>(ALL_WEDDING_EVENTS);
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

 const selectedWeddingData = useMemo(
 () => weddings.find((w) => (w.id || w._id) === selectedWedding),
 [selectedWedding, weddings]
 );
 const activeTab = forcedTab;
 const canAccessInvites = canSendRsvp(userProfile);
 const canAccessReminderTabs = canSendReminders(userProfile);
 const canAccessHistory = canAccessInvites || canAccessReminderTabs;
 const requestedWeddingId = searchParams.get('wedding_id') || '';
 const requestedRecipients = searchParams.get('recipients') || '';
 const requestedTemplate = searchParams.get('template') || '';
 const requestedChannel = searchParams.get('channel');

 const reminderEventOptions = useMemo(
 () => getWeddingReminderEventOptions(selectedWeddingData?.events),
 [selectedWeddingData]
 );
 const selectedReminderEventLabel = useMemo(
 () => getWeddingEventLabel(
 eventType,
 selectedWeddingData?.events?.find((event) => event.type === eventType)?.custom_type_label
 ),
 [eventType, selectedWeddingData]
 );
 const reminderRecipientDescription = eventType === ALL_WEDDING_EVENTS
 ? 'This will be sent once to each selected recipient who has RSVP’d for at least one event.'
 : `This will be sent to guests who have RSVP’d for the ${selectedReminderEventLabel} event.`;

 const hasTabAccess = useMemo(() => {
 if (activeTab === 'invites') return canAccessInvites;
 if (activeTab === 'history') return canAccessHistory;
 return canAccessReminderTabs;
 }, [activeTab, canAccessHistory, canAccessInvites, canAccessReminderTabs]);

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
 const weddingList = Array.isArray(data)
   ? data
   : Array.isArray(data?.weddings)
     ? data.weddings
     : [];
 setWeddings(weddingList);
 } catch (err) {
 setError('Failed to load weddings');
 }
 }, [token]);

 const fetchGuests = useCallback(async () => {
 if (!selectedWedding || !token) return;

 try {
 const baseUrl = getApiBaseUrl();
 const response = await fetch(
 `${baseUrl}/admin/guests?wedding_id=${selectedWedding}&fetch_all=true`,
 {
 headers: { 'Authorization': `Bearer ${token}` },
 }
 );

 if (!response.ok) {
 console.error('Failed to fetch guests:', response.status);
 return;
 }

 const data = await response.json();
 const guestList = extractGuestList<Guest>(data);
 console.log('Fetched guests:', guestList.length, 'guests');
 setGuests(guestList);
 } catch (err) {
 console.error('Failed to load guests:', err);
 }
 }, [selectedWedding, token]);

 const fetchPlusOnes = useCallback(async () => {
 if (!selectedWedding || !token) return;

 try {
 const baseUrl = getApiBaseUrl();
 const response = await fetch(
 `${baseUrl}/admin/plus-one/wedding/${selectedWedding}`,
 {
 headers: { 'Authorization': `Bearer ${token}` },
 }
 );

 if (!response.ok) {
 console.error('Failed to fetch plus-ones:', response.status);
 return;
 }

 const data = await response.json();
 setPlusOnes(Array.isArray(data) ? data : []);
 } catch (err) {
 console.error('Failed to load plus-ones:', err);
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
 if (!requestedWeddingId) return;
 if (requestedWeddingId !== selectedWedding) {
 setSelectedWedding(requestedWeddingId);
 }
 }, [requestedWeddingId, selectedWedding]);

 useEffect(() => {
 if (!selectedWedding || !pathname) return;
 if (requestedWeddingId === selectedWedding) return;

 const params = new URLSearchParams(searchParams.toString());
 params.set('wedding_id', selectedWedding);
 const nextUrl = `${pathname}?${params.toString()}`;
 router.replace(nextUrl, { scroll: false });
 }, [pathname, requestedWeddingId, router, searchParams, selectedWedding]);

 useEffect(() => {
 if (selectedWedding && token) {
 fetchGuests();
 fetchPlusOnes();
 }
 }, [fetchGuests, fetchPlusOnes, selectedWedding, token]);

 useEffect(() => {
 if (!weddings.length) return;
 const hasSelectedWedding = weddings.some((wedding) => (wedding.id || wedding._id) === selectedWedding);
 if (hasSelectedWedding) return;
 const requestedWedding = requestedWeddingId
 ? weddings.find((wedding) => (wedding.id || wedding._id) === requestedWeddingId)
 : null;
 const defaultWeddingId =
 requestedWedding?.id ||
 requestedWedding?._id ||
 weddings[0].id ||
 weddings[0]._id ||
 '';
 if (defaultWeddingId) {
 setSelectedWedding(defaultWeddingId);
 }
 }, [requestedWeddingId, selectedWedding, weddings]);

 useEffect(() => {
 if (activeTab !== 'individual') return;
 if (!requestedRecipients) {
 setSelectedGuests([]);
 return;
 }

 const nextRecipients = requestedRecipients
 .split(',')
 .map((recipient) => recipient.trim())
 .filter(Boolean);

 setSelectedGuests((currentRecipients) => {
 const currentKey = currentRecipients.join(',');
 const nextKey = nextRecipients.join(',');
 return currentKey === nextKey ? currentRecipients : nextRecipients;
 });
 }, [activeTab, requestedRecipients]);

 useEffect(() => {
 if (reminderEventOptions.length === 0) return;
 if (!reminderEventOptions.some((option) => option.value === eventType)) {
 setEventType(ALL_WEDDING_EVENTS);
 }
 }, [eventType, reminderEventOptions]);

 useEffect(() => {
 if (!requestedChannel) return;
 if (!['sms', 'email', 'both'].includes(requestedChannel)) return;

 setChannel((currentChannel) =>
 currentChannel === requestedChannel ? currentChannel : (requestedChannel as 'sms' | 'email' | 'both')
 );
 }, [requestedChannel]);

 const handleSendInviteLinks = async () => {
 if (!selectedWedding) {
 setError('Please select a wedding');
 return;
 }

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
 const skipDetails: string[] = [];

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
 totalFailed += result.failed || 0;
 // Collect skip details from SMS response
 if (result.skipped_no_phone > 0) skipDetails.push(`${result.skipped_no_phone} no phone`);
 if (result.skipped_no_token > 0) skipDetails.push(`${result.skipped_no_token} no token`);
 if (result.skipped_opted_out > 0) skipDetails.push(`${result.skipped_opted_out} opted out`);
 if (result.unreachable_guests?.length > 0) skipDetails.push(`${result.unreachable_guests.length} completely unreachable`);
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
 // Collect skip details from email response
 if (result.skipped_no_email > 0) skipDetails.push(`${result.skipped_no_email} no email`);
 if (result.skipped_no_token > 0) skipDetails.push(`${result.skipped_no_token} no token`);
 if (result.skipped_opted_out > 0) skipDetails.push(`${result.skipped_opted_out} email opted out`);
 } else {
 const errorData = await response.json().catch(() => ({}));
 const detail = errorData.detail || 'Email invite send failed';
 console.error('Email invite error:', detail);
 skipDetails.push(`Email error: ${detail}`);
 }
 }

 const channelText = channel === 'both' ? 'SMS and email' : channel;
 let successMsg = `Sent ${totalSent} invites via ${channelText}.`;
 if (totalFailed > 0) successMsg += ` ${totalFailed} failed.`;
 if (skipDetails.length > 0) successMsg += ` Skipped: ${skipDetails.join(', ')}.`;
 setSuccess(successMsg);
 fetchMessageHistory();
 fetchGuests(); // Refresh to pick up any phone_status changes
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
 const sendErrors: string[] = [];

 // Send SMS reminders
 if (channel === 'sms' || channel === 'both') {
 const params = new URLSearchParams({
 wedding_slug: selectedWeddingData.slug,
 event_type: eventType,
 message: customMessage,
 target_group: targetGroup,
 });

 const response = await fetch(`${baseUrl}/admin/reminders/twilio/send?${params}`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 },
 });

 if (response.ok) {
 const result = await response.json();
 totalSent += result.sent || 0;
 totalFailed += result.skipped_no_phone || 0;
 totalFailed += result.skipped_opted_out || 0;
 } else {
 const errorData = await response.json().catch(() => ({}));
 const detail = errorData.detail || 'SMS reminder send failed';
 console.error('SMS reminder error:', detail);
 sendErrors.push(`SMS error: ${detail}`);
 totalFailed += 1;
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
 body: JSON.stringify(buildEventReminderEmailPayload({
 weddingSlug: selectedWeddingData.slug,
 eventType,
 customMessage,
 emailSubject,
 targetGroup,
 })),
 });

 if (response.ok) {
 const result = await response.json();
 totalSent += result.sent || 0;
 totalFailed += result.failed || 0;
 } else {
 const errorData = await response.json().catch(() => ({}));
 const detail = errorData.detail || 'Email reminder send failed';
 console.error('Email reminder error:', detail);
 sendErrors.push(`Email error: ${detail}`);
 totalFailed += 1;
 }
 }

 if (totalSent === 0) {
 setError(sendErrors[0] || (
 eventType === ALL_WEDDING_EVENTS
 ? 'No reminders sent. Make sure guests have RSVP’d for at least one event.'
 : 'No reminders sent. Make sure guests have RSVP’d for the selected event type.'
 ));
 } else {
 const channelText = channel === 'both' ? 'SMS and email' : channel;
 setSuccess(`Successfully sent ${totalSent} reminders via ${channelText}!${totalFailed > 0 ? ` (${totalFailed} failed)` : ''}`);
 setCustomMessage('');
 setEmailSubject('');
 setEmailHtml('');
 fetchMessageHistory();
 fetchGuests(); // Refresh to pick up any phone_status changes
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

 if ((channel === 'email' || channel === 'both') && !selectedWeddingData?.slug) {
 setError('Wedding slug not found');
 return;
 }

 setLoading(true);
 setError('');
 setSuccess('');

 try {
 const baseUrl = getApiBaseUrl();

 const selectedGuestTokens = selectedGuests
 .filter((selection) => selection.startsWith('guest:'))
 .map((selection) => selection.replace('guest:', ''));
 const selectedPlusOneIds = selectedGuests
 .filter((selection) => selection.startsWith('plusone:'))
 .map((selection) => selection.replace('plusone:', ''));

 const selectedGuestRecords = selectedGuestTokens
 .map((guestToken) => guestByToken.get(guestToken))
 .filter((guest): guest is Guest => Boolean(guest));
 const selectedPlusOneRecords = selectedPlusOneIds
 .map((plusOneId) => plusOneById.get(plusOneId))
 .filter((plusOne): plusOne is PlusOne => Boolean(plusOne));

 let totalSent = 0;
 let totalFailed = 0;
 const totalCount = selectedGuests.length;
 const allFailureReasons: string[] = [];

 const smsEligibleGuestTokens =
 channel === 'email'
 ? []
 : selectedGuestRecords
 .filter((guest) => guest.phone && guest.phone.trim() !== '')
 .map((guest) => guest.token);
 const smsIneligibleGuests =
 channel === 'sms'
 ? selectedGuestRecords.filter((guest) => !guest.phone || guest.phone.trim() === '')
 : [];

 const emailEligibleGuests =
 channel === 'sms'
 ? []
 : selectedGuestRecords.filter((guest) => guest.email && guest.email.trim() !== '');
 const emailIneligibleGuests =
 channel === 'sms'
 ? []
 : selectedGuestRecords.filter((guest) => !guest.email || guest.email.trim() === '');

 const smsEligiblePlusOneIds =
 channel === 'email'
 ? []
 : selectedPlusOneRecords
 .filter((plusOne) => plusOne.phone && plusOne.phone.trim() !== '')
 .map((plusOne) => plusOne.id || plusOne._id || '');

 if (channel === 'email' && selectedPlusOneRecords.length > 0) {
 totalFailed += selectedPlusOneRecords.length;
 allFailureReasons.push('Plus-ones can only receive individual SMS messages right now.');
 }

 if (smsIneligibleGuests.length > 0) {
 totalFailed += smsIneligibleGuests.length;
 allFailureReasons.push(
 ...smsIneligibleGuests.map((guest) => `${guest.name} has no phone number for SMS delivery`)
 );
 }

 if (channel === 'email' || channel === 'both') {
 const emailOnlyFailures = channel === 'email' ? emailIneligibleGuests : emailIneligibleGuests.filter((guest) => !guest.phone || guest.phone.trim() === '');
 if (emailOnlyFailures.length > 0) {
 totalFailed += emailOnlyFailures.length;
 allFailureReasons.push(
 ...emailOnlyFailures.map((guest) => `${guest.name} has no email address for email delivery`)
 );
 }
 }

 if (smsEligibleGuestTokens.length > 0) {
 try {
 const response = await fetch(`${baseUrl}/admin/reminders/send-to-guests`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 body: JSON.stringify({
 guest_tokens: smsEligibleGuestTokens,
 message: customMessage,
 }),
 });

 if (!response.ok) {
 const errorData = await response.json().catch(() => ({}));
 allFailureReasons.push(errorData.detail || 'Failed to send SMS messages to guests');
 totalFailed += smsEligibleGuestTokens.length;
 } else {
 const result = await response.json();
 totalSent += result.sent || 0;
 totalFailed += result.failed || 0;
 if (result.failure_reasons) allFailureReasons.push(...result.failure_reasons);
 }
 } catch {
 allFailureReasons.push('Failed to send SMS messages to guests (network error)');
 totalFailed += smsEligibleGuestTokens.length;
 }
 }

 if (smsEligiblePlusOneIds.length > 0) {
 try {
 const response = await fetch(`${baseUrl}/admin/reminders/send-to-plus-ones`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 body: JSON.stringify({
 plus_one_ids: smsEligiblePlusOneIds,
 message: customMessage,
 wedding_id: selectedWedding,
 }),
 });

 if (!response.ok) {
 const errorData = await response.json().catch(() => ({}));
 allFailureReasons.push(errorData.detail || 'Failed to send SMS messages to plus-ones');
 totalFailed += smsEligiblePlusOneIds.length;
 } else {
 const result = await response.json();
 totalSent += result.sent || 0;
 totalFailed += result.failed || 0;
 if (result.failure_reasons) allFailureReasons.push(...result.failure_reasons);
 }
 } catch {
 allFailureReasons.push('Failed to send SMS messages to plus-ones (network error)');
 totalFailed += smsEligiblePlusOneIds.length;
 }
 }

 if (emailEligibleGuests.length > 0) {
 const emailResults = await Promise.allSettled(
 emailEligibleGuests.map((guest) =>
 fetch(`${baseUrl}/admin/email/send-reminder-individual`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 body: JSON.stringify({
 wedding_slug: selectedWeddingData?.slug,
 guest_email: guest.email,
 guest_name: guest.name,
 guest_token: guest.token,
 custom_message: customMessage,
 }),
 })
 )
 );

 for (let index = 0; index < emailResults.length; index += 1) {
 const guest = emailEligibleGuests[index];
 const result = emailResults[index];

 if (result.status === 'rejected') {
 totalFailed += 1;
 allFailureReasons.push(`Failed to send email to ${guest.name}`);
 continue;
 }

 if (!result.value.ok) {
 totalFailed += 1;
 const errorData = await result.value.json().catch(() => ({}));
 allFailureReasons.push(errorData.detail || `Failed to send email to ${guest.name}`);
 continue;
 }

 const body = await result.value.json().catch(() => ({}));
 if (body.sent || body.success) {
 totalSent += 1;
 } else {
 totalFailed += 1;
 allFailureReasons.push(body.error || `Failed to send email to ${guest.name}`);
 }
 }
 }

 if (totalSent > 0) {
 let msg = `Sent messages to ${totalSent} of ${totalCount} recipients.`;
 if (totalFailed > 0) msg += ` ${totalFailed} failed.`;
 if (allFailureReasons.length > 0) {
 msg += ` Details: ${allFailureReasons.slice(0, 5).join('; ')}`;
 if (allFailureReasons.length > 5) msg += `... and ${allFailureReasons.length - 5} more`;
 }
 setSuccess(msg);
 } else {
 const reasons = allFailureReasons.length > 0
 ? allFailureReasons.slice(0, 5).join('; ')
 : 'Recipients may have opted out or have no phone numbers.';
 setError(`No messages sent. ${reasons}`);
 }
 setCustomMessage('');
 setSelectedGuests([]);
 fetchMessageHistory();
 fetchGuests();
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
         event_name: eventType === ALL_WEDDING_EVENTS ? 'all wedding events' : selectedReminderEventLabel,
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

 const guestByToken = useMemo(
 () => new Map(guests.map((guest) => [guest.token, guest])),
 [guests]
 );
 const plusOneById = useMemo(
 () =>
 new Map(
 plusOnes
 .map((plusOne) => {
 const plusOneId = plusOne.id || plusOne._id || '';
 return plusOneId ? [plusOneId, plusOne] : null;
 })
 .filter((entry): entry is [string, PlusOne] => Boolean(entry))
 ),
 [plusOnes]
 );
 const guestsWithPhone = guests.filter(g => g.phone && g.phone.trim() !== '');
 const guestsWithEmail = guests.filter(g => g.email && g.email.trim() !== '');
 const guestsWithDirectMessaging = guests.filter(g =>
 (g.phone && g.phone.trim() !== '') || (g.email && g.email.trim() !== '')
 );

 // Plus-ones with phone numbers for individual messaging
 const plusOnesWithPhone = plusOnes.filter(po => po.phone && po.phone.trim() !== '');

 // Build a guest name lookup for showing "Host's +1: Name" in the dropdown
 const guestNameMap = new Map(guests.map(g => [g.id || g._id, g.name]));
 const getHostName = (guestId: string) => guestNameMap.get(guestId) || 'Unknown';
 const guestsWithPhoneOrEmail = guests.filter(g =>
 (g.phone && g.phone.trim() !== '') || (g.email && g.email.trim() !== '')
 );
 const unreachableGuests = guests.filter(g =>
 (!g.phone || g.phone.trim() === '') && (!g.email || g.email.trim() === '')
 );
 const guestsWithInvalidPhone = guests.filter(g =>
 g.phone_status === 'invalid' || g.phone_status === 'landline' || g.phone_status === 'unreachable'
 );
 const guestsOptedOut = guests.filter(g => g.sms_opt_in === false);
 const buildGuestManagementHref = (params: Record<string, string>) => {
 const searchParams = new URLSearchParams({
 wedding_id: selectedWedding,
 ...params,
 });
 return `/admin/guests?${searchParams.toString()}`;
 };
 const renderIssueGuestList = (
 issueGuests: Guest[],
 issueType: 'invalid_phone' | 'no_contact' | 'opted_out',
 description: string
 ) => (
 <details className="mt-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white/70 dark:bg-slate-900/40">
 <summary className="cursor-pointer list-none px-3 py-2 text-sm font-medium text-wedding-navy dark:text-gray-100">
 View affected guests
 </summary>
 <div className="border-t border-gray-200 dark:border-gray-700 px-3 py-3">
 <div className="mb-3 flex items-center justify-between gap-3">
 <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
 <Link
 href={buildGuestManagementHref(
 issueType === 'invalid_phone'
 ? { phone_issue: 'invalid_or_unreachable' }
 : issueType === 'no_contact'
 ? { phone_issue: 'no_contact' }
 : { sms_status: 'opted_out' }
 )}
 className="text-xs font-medium text-wedding-rose hover:text-wedding-navy"
 >
 Open filtered guest list
 </Link>
 </div>
 <ul className="space-y-2">
 {issueGuests.map((guest) => {
 const guestKey = guest.id || guest._id || `${guest.name}-${guest.phone || guest.email || guest.token}`;
 const guestParams: Record<string, string> = { name: guest.name };
 if (guest.phone) {
 guestParams.phone = guest.phone;
 }
 return (
 <li
 key={guestKey}
 className="flex flex-col gap-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-slate-800/80 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
 >
 <div>
 <p className="font-medium text-gray-900 dark:text-gray-100">{guest.name}</p>
 <p className="text-xs text-gray-500 dark:text-gray-400">
 {guest.phone || 'No phone'}{guest.email ? ` · ${guest.email}` : ' · No email'}
 </p>
 <p className="text-xs text-gray-500 dark:text-gray-400">
 {issueType === 'invalid_phone'
 ? `Phone status: ${guest.phone_status || 'unknown'}${guest.phone_error ? ` · ${guest.phone_error}` : ''}`
 : issueType === 'opted_out'
 ? `SMS opted out${guest.sms_opt_out_reason ? ` · ${guest.sms_opt_out_reason}` : ''}`
 : 'Missing both phone number and email address'}
 </p>
 </div>
 <Link
 href={buildGuestManagementHref(guestParams)}
 className="text-sm font-medium text-wedding-rose hover:text-wedding-navy"
 >
 Review guest
 </Link>
 </li>
 );
 })}
 </ul>
 </div>
 </details>
 );

 useEffect(() => {
 if (activeTab !== 'individual') return;
 if (!requestedTemplate || requestedTemplate !== 'rsvp_link') return;
 if (!selectedWeddingData?.slug || selectedGuests.length !== 1) return;

 const selectedRecipient = selectedGuests[0];
 if (!selectedRecipient.startsWith('guest:')) return;

 const guestToken = selectedRecipient.replace('guest:', '');
 const guest = guestByToken.get(guestToken);
 if (!guest) return;

 const templateKey = `${requestedTemplate}:${selectedWeddingData.slug}:${selectedRecipient}`;
 if (lastAppliedTemplateRef.current === templateKey) return;

 setCustomMessage(
 `Hi ${guest.name}, you're invited to our wedding! Please RSVP at: ${buildGuestOtpVerifyUrl({ slug: selectedWeddingData.slug, token: guest.token })} Need help? Reply HELP to wedding texts or use Get Help on the wedding website.`
 );
 lastAppliedTemplateRef.current = templateKey;
 }, [activeTab, guestByToken, requestedTemplate, selectedGuests, selectedWeddingData]);

 if (!hasTabAccess) {
 return (
   <div className="space-y-6">
     <PageHeader
       title="Communications"
       description="Send invitations, reminders, and one-off messages while monitoring delivery history"
     />
     <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-950">
       <h2 className="text-lg font-semibold">Access restricted</h2>
       <p className="mt-2 text-sm text-amber-900">
         {activeTab === 'invites'
           ? 'This area requires invite-sending access.'
           : activeTab === 'history'
             ? 'This area requires invite or reminder history access.'
             : 'This area requires reminder-sending access.'}
       </p>
     </div>
   </div>
 );
 }

 return (
 <div className="space-y-6">
 <PageHeader
   title="Communications"
   description="Send invitations, reminders, and one-off messages while monitoring delivery history"
 />

 {/* Wedding picker + channel — shared inline pill (see WeddingPicker.tsx) */}
 <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
 <div className="flex items-center gap-3">
 <span className="text-sm text-slate-500 dark:text-gray-400">Wedding:</span>
 <WeddingPicker
 options={weddings.map((w) => ({
 id: (w.id || w._id) as string,
 label: `${w.couple_names} — ${w.date}`,
 }))}
 value={selectedWedding}
 onChange={setSelectedWedding}
 placeholder="Choose a wedding…"
 />
 </div>

 <div className="flex items-center gap-1 whitespace-nowrap">
 <span className="text-sm font-medium text-slate-700 dark:text-gray-200 mr-2">Channel:</span>
 <label className="flex items-center">
 <input
 type="radio"
 value="sms"
 checked={channel === 'sms'}
 onChange={(e) => setChannel(e.target.value as 'sms' | 'email' | 'both')}
 className="mr-1"
 />
 <span className="text-sm">SMS</span>
 </label>
 <label className="flex items-center ml-3">
 <input
 type="radio"
 value="email"
 checked={channel === 'email'}
 onChange={(e) => setChannel(e.target.value as 'sms' | 'email' | 'both')}
 className="mr-1"
 />
 <span className="text-sm">Email</span>
 </label>
 <label className="flex items-center ml-3">
 <input
 type="radio"
 value="both"
 checked={channel === 'both'}
 onChange={(e) => setChannel(e.target.value as 'sms' | 'email' | 'both')}
 className="mr-1"
 />
 <span className="text-sm">Both</span>
 </label>
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
 {unreachableGuests.length > 0 && (
 <div>
 <p className="text-sm font-medium text-amber-600 dark:text-amber-400">
 {unreachableGuests.length} guest{unreachableGuests.length !== 1 ? 's have' : ' has'} no phone or email — unreachable
 </p>
 {renderIssueGuestList(
 unreachableGuests,
 'no_contact',
 'These guests cannot receive invitations or reminders until at least one contact method is added.'
 )}
 </div>
 )}
 {guestsWithInvalidPhone.length > 0 && (
 <div>
 <p className="text-sm font-medium text-red-600 dark:text-red-400">
 {guestsWithInvalidPhone.length} guest{guestsWithInvalidPhone.length !== 1 ? 's have' : ' has'} invalid/unreachable phone numbers
 </p>
 {renderIssueGuestList(
 guestsWithInvalidPhone,
 'invalid_phone',
 'These guests have a phone number on file, but SMS delivery cannot reach it in its current state.'
 )}
 </div>
 )}
 {guestsOptedOut.length > 0 && (
 <div>
 <p className="text-sm text-gray-500 dark:text-gray-400">
 {guestsOptedOut.length} guest{guestsOptedOut.length !== 1 ? 's have' : ' has'} opted out of SMS
 </p>
 {renderIssueGuestList(
 guestsOptedOut,
 'opted_out',
 'These guests have explicitly opted out of SMS and should only be contacted by email unless they opt back in.'
 )}
 </div>
 )}
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
        "{inviteMessage.replace('{url}', selectedWeddingData?.slug ? buildGuestOtpVerifyUrl({ slug: selectedWeddingData.slug, token: '[token]' }) : '').replace('{name}', '[Guest Name]')}"
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
 {reminderEventOptions.map((option) => (
 <option key={option.value} value={option.value}>{option.label}</option>
 ))}
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
 <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{reminderRecipientDescription}</p>
 <p className="text-sm text-yellow-600 mt-1">
        Note: If no messages are sent, guests may not have RSVP’d yet. Use “Send Invites” first to get responses.
 </p>
 </div>

 <button
 onClick={handleSendEventReminder}
 disabled={loading || (!customMessage.trim() && channel !== 'email')}
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
 {/* Modern Multi-Select Dropdown — Guests + Plus-Ones */}
 <MultiSelect
 label={`Select Recipients (${selectedGuests.length} selected)`}
 options={[
 ...guestsWithDirectMessaging.map((guest) => ({
 value: `guest:${guest.token}`,
 label: guest.name,
 sublabel: guest.phone || guest.email || undefined,
 })),
 ...plusOnesWithPhone.map((po) => ({
 value: `plusone:${po.id || po._id}`,
 label: `${po.name} (${getHostName(po.guest_id)}'s +1)`,
 sublabel: po.phone || undefined,
 })),
]}
selected={selectedGuests}
 onChange={setSelectedGuests}
 placeholder="Click to select guests or plus-ones..."
 searchPlaceholder="Search by name or phone..."
 emptyMessage="No guests or plus-ones with phone numbers found"
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
 {loading ? 'Sending...' : `Send Message to ${selectedGuests.length} Recipient(s)`}
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

 {/* SMS Delivery Health Summary Banner */}
 {messageHistory.length > 0 && (() => {
  // Filter to SMS records only — email delivery metrics are separate
  const smsLogs = messageHistory.filter(log => log.provider === 'twilio' || log.provider === 'telnyx');
  const last24h = smsLogs.filter(log => {
   const sentAt = new Date(log.sent_at);
   const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
   return sentAt >= oneDayAgo;
  });
  const totalSent = last24h.length;
  const delivered = last24h.filter(l => l.delivery_status === 'delivered' || (l.status === 'success' && !l.delivery_status)).length;
  const failed = last24h.filter(l => l.delivery_status === 'failed' || l.delivery_status === 'undelivered' || (l.status && l.status.startsWith('failed'))).length;
  const pending = last24h.filter(l => l.delivery_status === 'queued' || l.delivery_status === 'accepted' || l.delivery_status === 'sending' || l.delivery_status === 'sent').length;
  const withFallback = last24h.filter(l => l.fallback_channel === 'email' && l.fallback_status === 'sent').length;
  const completed = delivered + failed;
  const rate = completed > 0 ? Math.round((delivered / completed) * 100) : 100;
  const isHealthy = rate >= 95;
  const isDegraded = rate >= 80 && rate < 95;

  if (totalSent === 0) return null;
  return (
   <div className={`rounded-lg p-4 mb-6 border ${
    isHealthy ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800' :
    isDegraded ? 'bg-yellow-50 border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800' :
    'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
   }`}>
    <div className="flex flex-wrap items-center gap-4">
     <div className="flex items-center gap-2">
      <div className={`w-3 h-3 rounded-full ${isHealthy ? 'bg-green-500' : isDegraded ? 'bg-yellow-500' : 'bg-red-500'}`} />
      <span className="font-semibold text-sm text-gray-800 dark:text-gray-200">Last 24h SMS Delivery</span>
     </div>
     <div className="flex flex-wrap gap-3 text-sm">
      <span className="text-gray-600 dark:text-gray-300">Rate: <strong className={isHealthy ? 'text-green-700 dark:text-green-400' : isDegraded ? 'text-yellow-700 dark:text-yellow-400' : 'text-red-700 dark:text-red-400'}>{rate}%</strong></span>
      <span className="text-gray-600 dark:text-gray-300">Sent: <strong>{totalSent}</strong></span>
      <span className="text-green-700 dark:text-green-400">Delivered: <strong>{delivered}</strong></span>
      {failed > 0 && <span className="text-red-700 dark:text-red-400">Failed: <strong>{failed}</strong></span>}
      {pending > 0 && <span className="text-yellow-700 dark:text-yellow-400">Pending: <strong>{pending}</strong></span>}
      {withFallback > 0 && <span className="text-blue-700 dark:text-blue-400">Email fallbacks: <strong>{withFallback}</strong></span>}
     </div>
    </div>
    {failed > 0 && (
     <button
      onClick={() => {
       const failedLogs = last24h.filter(l => l.delivery_status === 'failed' || l.delivery_status === 'undelivered' || (l.status && l.status.startsWith('failed')));
       const subject = `Bulk SMS Delivery Failures (${failed} messages)`;
       const description = failedLogs.slice(0, 10).map(l =>
        `- ${l.phone || l.to || 'N/A'}: ${l.error_message || l.status || 'Unknown'}`
       ).join('\n');
       window.open(`/admin/support?action=create&subject=${encodeURIComponent(subject)}&description=${encodeURIComponent(description)}&category=technical&priority=high`, '_blank');
      }}
      className="mt-2 inline-flex items-center px-3 py-1.5 text-xs font-medium text-red-700 bg-red-100 border border-red-300 rounded-md hover:bg-red-200 dark:text-red-300 dark:bg-red-900/40 dark:border-red-700"
     >
      Report {failed} Failed Deliveries
     </button>
    )}
   </div>
  );
 })()}

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
 <div className="flex gap-2">
 <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
 log.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
 }`}>
 {log.status}
 </span>
 {log.provider === 'twilio' && log.delivery_status && (
 <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
 log.delivery_status === 'delivered'
 ? 'bg-green-100 text-green-800'
 : log.delivery_status === 'sent'
 ? 'bg-blue-100 text-blue-800'
 : log.delivery_status === 'queued' || log.delivery_status === 'accepted'
 ? 'bg-yellow-100 text-yellow-800'
 : log.delivery_status === 'failed' || log.delivery_status === 'undelivered'
 ? 'bg-red-100 text-red-800'
 : 'bg-gray-100 text-gray-800'
 }`}>
 {log.delivery_status}
 </span>
 )}
 </div>
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
 {log.fallback_channel === 'email' && (
 <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded mt-1 ${
  log.fallback_status === 'sent' ? 'bg-blue-100 text-blue-700' : 'bg-red-100 text-red-700'
 }`}>
  Email fallback {log.fallback_status}
 </span>
 )}
 {(log.delivery_status === 'failed' || log.delivery_status === 'undelivered' || (log.status && log.status.startsWith('failed'))) && (
 <button
  onClick={() => {
   const subject = `SMS Delivery Failure: ${log.error_message || 'Unknown error'}`;
   const description = [
    `Phone: ${log.phone || 'N/A'}`,
    `Error Code: ${log.error_code || 'N/A'}`,
    `Error: ${log.error_message || 'N/A'}`,
    `Message SID: ${log.message_sid || 'N/A'}`,
    `Sent At: ${log.sent_at}`,
   ].join('\n');
   window.open(`/admin/support?action=create&subject=${encodeURIComponent(subject)}&description=${encodeURIComponent(description)}&category=technical&priority=high`, '_blank');
  }}
  className="inline-flex items-center px-2 py-1 mt-1 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded hover:bg-red-100"
 >
  Report Issue
 </button>
 )}
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
 Delivery
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Content
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Actions
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
 <td className="px-6 py-4 whitespace-nowrap">
 {log.provider === 'twilio' && log.delivery_status ? (
 <div className="flex flex-col">
 <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
 log.delivery_status === 'delivered'
 ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
 : log.delivery_status === 'sent'
 ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
 : log.delivery_status === 'queued' || log.delivery_status === 'accepted'
 ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
 : log.delivery_status === 'failed' || log.delivery_status === 'undelivered'
 ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
 : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
 }`}>
 {log.delivery_status}
 </span>
 {log.error_message && (
 <span className="text-xs text-red-600 dark:text-red-400 mt-1 max-w-[150px] truncate" title={log.error_message}>
 {log.error_message}
 </span>
 )}
 </div>
 ) : (
 <span className="text-gray-400 dark:text-gray-500 text-xs">-</span>
 )}
 </td>
 <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100 max-w-xs truncate">
 {log.message || log.subject || ''}
 </td>
 <td className="px-6 py-4 whitespace-nowrap text-sm">
 <div className="flex flex-col gap-1">
 {log.fallback_channel !== 'email' &&
  log.delivery_status !== 'failed' &&
  log.delivery_status !== 'undelivered' &&
  !(log.status && log.status.startsWith('failed')) && (
   <span className="text-xs text-gray-400 dark:text-gray-500">No action</span>
  )}
 {log.fallback_channel === 'email' && (
 <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded ${
  log.fallback_status === 'sent' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200' : 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200'
 }`}>
  Email fallback {log.fallback_status}
 </span>
 )}
 {(log.delivery_status === 'failed' || log.delivery_status === 'undelivered' || (log.status && log.status.startsWith('failed'))) && (
 <button
  onClick={() => {
   const subject = `SMS Delivery Failure: ${log.error_message || 'Unknown error'}`;
   const description = [
    `Phone: ${log.phone || 'N/A'}`,
    `Error Code: ${log.error_code || 'N/A'}`,
    `Error: ${log.error_message || 'N/A'}`,
    `Message SID: ${log.message_sid || 'N/A'}`,
    `Sent At: ${log.sent_at}`,
    `Delivery Status: ${log.delivery_status || log.status}`,
   ].join('\n');
   window.open(`/admin/support?action=create&subject=${encodeURIComponent(subject)}&description=${encodeURIComponent(description)}&category=technical&priority=high`, '_blank');
  }}
  className="inline-flex items-center px-2 py-1 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded hover:bg-red-100 dark:text-red-300 dark:bg-red-900/30 dark:border-red-800 dark:hover:bg-red-900/50"
 >
  Report Issue
 </button>
 )}
 </div>
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
