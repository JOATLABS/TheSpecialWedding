'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAdmin } from '../../contexts/AdminContext';

interface Wedding {
 id: string;
 _id: string;
 couple_names: string;
 date: string;
 slug: string;
 assigned_planner_email?: string;
 assigned_planner_id?: string;
 status?: string;
 venue?: string;
 guest_count?: number;
 created_at?: string;
 events?: Array<{
 type: string;
 date: string;
 }>;
}

interface WeddingForm {
 couple_names: string;
 date: string;
 slug: string;
 assigned_planner_email?: string;
 venue?: string;
 status?: string;
 events: Array<{
 type: string;
 date: string;
 }>;
}

interface UserProfile {
 email: string;
 role: string;
 is_root_admin: boolean;
 is_wedding_planner: boolean;
 user_data?: any;
}

interface PlannerOption {
 email: string;
 name: string;
 id: string;
}

export default function AdminWeddingsPage() {
 const { token, userProfile, fetchUserProfile } = useAdmin();
 const [weddings, setWeddings] = useState<Wedding[]>([]);
 const [allWeddings, setAllWeddings] = useState<Wedding[]>([]);
 const [planners, setPlanners] = useState<PlannerOption[]>([]);
 const [loading, setLoading] = useState(false);
 const [error, setError] = useState<string>('');
 const [showForm, setShowForm] = useState(false);
 const [editingId, setEditingId] = useState<string | null>(null);
 const [filter, setFilter] = useState<'all' | 'assigned' | 'unassigned'>('all');
 const [searchTerm, setSearchTerm] = useState('');
 const [statusFilter, setStatusFilter] = useState<string>('all');
 const [dateFilter, setDateFilter] = useState<'all' | 'upcoming' | 'past' | 'this_month' | 'this_year'>('all');
 const [selectedWeddings, setSelectedWeddings] = useState<string[]>([]);
 const [showBulkActions, setShowBulkActions] = useState(false);
 const [showTemplates, setShowTemplates] = useState(false);

 // Wedding templates
 const weddingTemplates = [
 {
 id: 'traditional-nigerian',
 name: 'Traditional Nigerian Wedding',
 description: 'Complete traditional Nigerian wedding with engagement and white wedding',
 events: [
 { type: 'engagement', date: '' },
 { type: 'traditional', date: '' },
 { type: 'white_wedding', date: '' },
 { type: 'reception', date: '' }
 ],
 status: 'planning'
 },
 {
 id: 'simple-ceremony',
 name: 'Simple Wedding Ceremony',
 description: 'Intimate ceremony with reception',
 events: [
 { type: 'white_wedding', date: '' },
 { type: 'reception', date: '' }
 ],
 status: 'planning'
 },
 {
 id: 'destination-wedding',
 name: 'Destination Wedding',
 description: 'Wedding ceremony and reception at destination venue',
 events: [
 { type: 'rehearsal', date: '' },
 { type: 'white_wedding', date: '' },
 { type: 'reception', date: '' }
 ],
 status: 'planning'
 },
 {
 id: 'court-wedding',
 name: 'Court Wedding',
 description: 'Simple court ceremony with small reception',
 events: [
 { type: 'white_wedding', date: '' },
 { type: 'reception', date: '' }
 ],
 status: 'active'
 }
 ];
 
 const [formData, setFormData] = useState<WeddingForm>({
 couple_names: '',
 date: '',
 slug: '',
 assigned_planner_email: '',
 venue: '',
 status: 'active',
 events: []
 });

 useEffect(() => {
 if (!userProfile) {
 fetchUserProfile();
 } else {
 fetchWeddings();
 if (userProfile.is_root_admin) {
 fetchPlanners();
 }
 }
 }, [userProfile]);

 useEffect(() => {
 filterWeddings();
 }, [allWeddings, filter, userProfile, searchTerm, statusFilter, dateFilter]);

 const fetchWeddings = async () => {
 setLoading(true);
 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 
 // Choose API endpoint based on user role
 const endpoint = userProfile?.is_root_admin 
 ? `${baseUrl}/admin/weddings` // ROOT_ADMIN sees all weddings
 : `${baseUrl}/admin/planner/weddings`; // Planners see only assigned weddings
 
 const response = await fetch(endpoint, {
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 });
 
 if (!response.ok) {
 throw new Error('Failed to fetch weddings');
 }
 const data = await response.json();
 // Ensure data is an array
 const weddingList = Array.isArray(data) ? data : [];
 setAllWeddings(weddingList);
 } catch (err) {
 console.error('Error fetching weddings:', err);
 setError('Failed to load weddings');
 setAllWeddings([]);
 } finally {
 setLoading(false);
 }
 };

 const fetchPlanners = async () => {
 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const response = await fetch(`${baseUrl}/admin/users?role=wedding_planner`, {
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 });
 
 if (response.ok) {
 const data = await response.json();
 const plannerOptions = data.map((user: any) => ({
 email: user.email,
 name: user.user_data?.company_name || `${user.user_data?.first_name || ''} ${user.user_data?.last_name || ''}`.trim() || user.email,
 id: user._id
 }));
 setPlanners(plannerOptions);
 }
 } catch (err) {
 console.error('Error fetching planners:', err);
 }
 };

 const filterWeddings = () => {
 if (!userProfile) return;

 let filtered = [...allWeddings];

 // Apply role-based filtering
 if (!userProfile.is_root_admin) {
 // Wedding planners only see their assigned weddings
 filtered = filtered.filter(wedding => 
 wedding.assigned_planner_email === userProfile.email
 );
 } else {
 // ROOT_ADMIN can filter by assignment status
 if (filter === 'assigned') {
 filtered = filtered.filter(wedding => wedding.assigned_planner_email);
 } else if (filter === 'unassigned') {
 filtered = filtered.filter(wedding => !wedding.assigned_planner_email);
 }
 }

 // Apply search filter
 if (searchTerm.trim()) {
 const search = searchTerm.toLowerCase();
 filtered = filtered.filter(wedding => 
 wedding.couple_names?.toLowerCase().includes(search) ||
 wedding.venue?.toLowerCase().includes(search) ||
 wedding.assigned_planner_email?.toLowerCase().includes(search) ||
 wedding.slug?.toLowerCase().includes(search)
 );
 }

 // Apply status filter
 if (statusFilter !== 'all') {
 filtered = filtered.filter(wedding => wedding.status === statusFilter);
 }

 // Apply date filter
 if (dateFilter !== 'all') {
 const currentDate = new Date();
 filtered = filtered.filter(wedding => {
 try {
 const weddingDate = new Date(wedding.date);
 
 switch (dateFilter) {
 case 'upcoming':
 return weddingDate >= currentDate;
 case 'past':
 return weddingDate < currentDate;
 case 'this_month':
 return weddingDate.getMonth() === currentDate.getMonth() && 
 weddingDate.getFullYear() === currentDate.getFullYear();
 case 'this_year':
 return weddingDate.getFullYear() === currentDate.getFullYear();
 default:
 return true;
 }
 } catch {
 return true; // Include weddings with invalid dates
 }
 });
 }

 // Sort by date (upcoming first, then by date)
 filtered.sort((a, b) => {
 try {
 const dateA = new Date(a.date);
 const dateB = new Date(b.date);
 const currentDate = new Date();
 
 // Upcoming weddings first, sorted by date ascending
 const aUpcoming = dateA >= currentDate;
 const bUpcoming = dateB >= currentDate;
 
 if (aUpcoming && !bUpcoming) return -1;
 if (!aUpcoming && bUpcoming) return 1;
 
 return dateA.getTime() - dateB.getTime();
 } catch {
 return 0;
 }
 });

 setWeddings(filtered);
 };

 const generateSlug = (coupleNames: string) => {
 return coupleNames
 .toLowerCase()
 .replace(/[^a-z0-9\s-]/g, '')
 .replace(/\s+/g, '-')
 .replace(/-+/g, '-')
 .trim();
 };

 const handleSubmit = async (e: React.FormEvent) => {
 e.preventDefault();
 setError('');
 setLoading(true);

 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const url = editingId 
 ? `${baseUrl}/admin/weddings/${editingId}`
 : `${baseUrl}/admin/weddings`;
 
 const method = editingId ? 'PUT' : 'POST';
 
 // Prepare the wedding data
 const weddingData = editingId 
 ? formData 
 : {
 _id: `wedding_${Date.now()}`,
 ...formData,
 created_at: new Date().toISOString()
 };

 const response = await fetch(url, {
 method,
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 body: JSON.stringify(weddingData),
 });

 if (!response.ok) {
 const errorData = await response.json();
 throw new Error(errorData.detail || 'Failed to save wedding');
 }

 // Reset form and refresh list
 setFormData({
 couple_names: '',
 date: '',
 slug: '',
 assigned_planner_email: '',
 venue: '',
 status: 'active',
 events: []
 });
 setShowForm(false);
 setEditingId(null);
 fetchWeddings();
 } catch (err) {
 setError(err instanceof Error ? err.message : 'Failed to save wedding');
 } finally {
 setLoading(false);
 }
 };

 const handleDelete = async (weddingId: string) => {
 if (!confirm('Are you sure you want to delete this wedding? This will also delete all associated guests.')) {
 return;
 }

 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const response = await fetch(`${baseUrl}/admin/weddings/${weddingId}`, {
 method: 'DELETE',
 headers: {
 'Authorization': `Bearer ${token}`,
 },
 });

 if (response.ok) {
 fetchWeddings();
 } else {
 setError('Failed to delete wedding');
 }
 } catch (err) {
 setError('Failed to delete wedding');
 }
 };

 const handleEdit = (wedding: Wedding) => {
 setFormData({
 couple_names: wedding.couple_names,
 date: wedding.date,
 slug: wedding.slug,
 assigned_planner_email: wedding.assigned_planner_email || '',
 venue: wedding.venue || '',
 status: wedding.status || 'active',
 events: wedding.events || []
 });
 setEditingId(wedding._id);
 setShowForm(true);
 };

 const addEvent = () => {
 setFormData({
 ...formData,
 events: [...formData.events, { type: '', date: '' }]
 });
 };

 const removeEvent = (index: number) => {
 setFormData({
 ...formData,
 events: formData.events.filter((_, i) => i !== index)
 });
 };

 const updateEvent = (index: number, field: 'type' | 'date', value: string) => {
 const newEvents = [...formData.events];
 newEvents[index][field] = value;
 setFormData({ ...formData, events: newEvents });
 };

 const handleSelectWedding = (weddingId: string, checked: boolean) => {
 if (checked) {
 setSelectedWeddings([...selectedWeddings, weddingId]);
 } else {
 setSelectedWeddings(selectedWeddings.filter(id => id !== weddingId));
 }
 };

 const handleSelectAll = (checked: boolean) => {
 if (checked) {
 setSelectedWeddings(weddings.map(w => w._id));
 } else {
 setSelectedWeddings([]);
 }
 };

 const handleBulkStatusChange = async (newStatus: string) => {
 if (selectedWeddings.length === 0) return;
 
 try {
 setLoading(true);
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 
 // Update each selected wedding
 const updatePromises = selectedWeddings.map(weddingId =>
 fetch(`${baseUrl}/admin/weddings/${weddingId}`, {
 method: 'PUT',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 body: JSON.stringify({ status: newStatus }),
 })
 );

 await Promise.all(updatePromises);
 
 // Refresh wedding list
 await fetchWeddings();
 setSelectedWeddings([]);
 setShowBulkActions(false);
 
 } catch (err) {
 setError('Failed to update wedding statuses');
 } finally {
 setLoading(false);
 }
 };

 const handleBulkDelete = async () => {
 if (selectedWeddings.length === 0) return;
 
 if (!confirm(`Are you sure you want to delete ${selectedWeddings.length} wedding(s)? This action cannot be undone.`)) {
 return;
 }
 
 try {
 setLoading(true);
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 
 // Delete each selected wedding
 const deletePromises = selectedWeddings.map(weddingId =>
 fetch(`${baseUrl}/admin/weddings/${weddingId}`, {
 method: 'DELETE',
 headers: {
 'Authorization': `Bearer ${token}`,
 },
 })
 );

 await Promise.all(deletePromises);
 
 // Refresh wedding list
 await fetchWeddings();
 setSelectedWeddings([]);
 setShowBulkActions(false);
 
 } catch (err) {
 setError('Failed to delete weddings');
 } finally {
 setLoading(false);
 }
 };

 const applyTemplate = (template: any) => {
 setFormData({
 ...formData,
 events: template.events,
 status: template.status
 });
 setShowTemplates(false);
 };

 return (
 <div className="min-h-screen bg-gradient-to-br from-wedding-ivory to-rose-50 p-4 sm:p-6">
 <div className="max-w-6xl mx-auto">
 {/* Header */}
 <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-8">
 <div className="bg-gradient-to-r from-wedding-navy to-wedding-gold px-4 sm:px-8 py-4 sm:py-6">
 <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
 <div>
 <h1 className="text-2xl sm:text-3xl font-bold text-white">
 {userProfile?.is_root_admin ? 'Wedding Management' : 'My Weddings'}
 </h1>
 <p className="text-blue-100 mt-1 sm:mt-2 text-sm sm:text-base">
 {userProfile?.is_root_admin 
 ? 'Create and manage wedding events for all planners' 
 : 'Manage your assigned wedding events'
 }
 </p>
 </div>
 <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
 {userProfile?.is_root_admin && (
 <select
 value={filter}
 onChange={(e) => setFilter(e.target.value as 'all' | 'assigned' | 'unassigned')}
 className="bg-white text-wedding-navy px-4 py-2 rounded-lg border-0 text-sm focus:ring-2 focus:ring-blue-300"
 >
 <option value="all">All Weddings ({allWeddings.length})</option>
 <option value="assigned">Assigned ({allWeddings.filter(w => w.assigned_planner_email).length})</option>
 <option value="unassigned">Unassigned ({allWeddings.filter(w => !w.assigned_planner_email).length})</option>
 </select>
 )}
 {userProfile?.is_root_admin && (
 <button
 onClick={() => {
 setShowForm(!showForm);
 setEditingId(null);
 setFormData({
 couple_names: '',
 date: '',
 slug: '',
 assigned_planner_email: '',
 venue: '',
 status: 'active',
 events: []
 });
 }}
 className="bg-white text-wedding-navy px-4 sm:px-6 py-2 sm:py-3 rounded-lg font-semibold hover:bg-wedding-ivory transition-colors text-sm sm:text-base w-full sm:w-auto"
 >
 {showForm ? 'Cancel' : 'Create Wedding'}
 </button>
 )}
 </div>
 </div>
 </div>
 </div>

 {/* Search and Filter Section */}
 <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-8">
 <div className="p-4 sm:p-6">
 <h2 className="text-lg font-semibold text-gray-900 mb-4">Search & Filter</h2>
 
 <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
 {/* Search Input */}
 <div>
 <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-2">
 Search Weddings
 </label>
 <input
 type="text"
 id="search"
 placeholder="Couple names, venue, planner..."
 value={searchTerm}
 onChange={(e) => setSearchTerm(e.target.value)}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent text-sm"
 />
 </div>

 {/* Status Filter */}
 <div>
 <label htmlFor="statusFilter" className="block text-sm font-medium text-gray-700 mb-2">
 Status
 </label>
 <select
 id="statusFilter"
 value={statusFilter}
 onChange={(e) => setStatusFilter(e.target.value)}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent text-sm"
 >
 <option value="all">All Statuses</option>
 <option value="draft">Draft</option>
 <option value="planning">Planning</option>
 <option value="active">Active</option>
 <option value="confirmed">Confirmed</option>
 <option value="completed">Completed</option>
 <option value="archived">Archived</option>
 <option value="cancelled">Cancelled</option>
 <option value="postponed">Postponed</option>
 </select>
 </div>

 {/* Date Filter */}
 <div>
 <label htmlFor="dateFilter" className="block text-sm font-medium text-gray-700 mb-2">
 Date Range
 </label>
 <select
 id="dateFilter"
 value={dateFilter}
 onChange={(e) => setDateFilter(e.target.value as any)}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent text-sm"
 >
 <option value="all">All Dates</option>
 <option value="upcoming">Upcoming</option>
 <option value="past">Past</option>
 <option value="this_month">This Month</option>
 <option value="this_year">This Year</option>
 </select>
 </div>

 {/* Clear Filters */}
 <div className="flex items-end">
 <button
 onClick={() => {
 setSearchTerm('');
 setStatusFilter('all');
 setDateFilter('all');
 setFilter('all');
 }}
 className="w-full px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
 >
 Clear Filters
 </button>
 </div>
 </div>

 {/* Results Summary */}
 <div className="mt-4 flex items-center justify-between text-sm text-gray-600">
 <span>
 Showing {weddings.length} of {allWeddings.length} wedding{allWeddings.length !== 1 ? 's' : ''}
 </span>
 {(searchTerm || statusFilter !== 'all' || dateFilter !== 'all') && (
 <span className="text-wedding-rose">
 Filters active
 </span>
 )}
 </div>
 </div>
 </div>

 {/* Bulk Actions */}
 {selectedWeddings.length > 0 && (
 <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
 <div className="flex items-center justify-between">
 <span className="text-blue-800 font-medium">
 {selectedWeddings.length} wedding{selectedWeddings.length !== 1 ? 's' : ''} selected
 </span>
 <div className="flex space-x-2">
 <select
 onChange={(e) => e.target.value && handleBulkStatusChange(e.target.value)}
 className="px-3 py-1 text-sm border border-blue-300 rounded focus:ring-2 focus:ring-blue-500"
 defaultValue=""
 >
 <option value="">Change Status</option>
 <option value="draft">Draft</option>
 <option value="planning">Planning</option>
 <option value="active">Active</option>
 <option value="confirmed">Confirmed</option>
 <option value="completed">Completed</option>
 <option value="archived">Archived</option>
 <option value="cancelled">Cancelled</option>
 <option value="postponed">Postponed</option>
 </select>
 {userProfile?.is_root_admin && (
 <button
 onClick={handleBulkDelete}
 className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
 >
 Delete Selected
 </button>
 )}
 <button
 onClick={() => setSelectedWeddings([])}
 className="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors"
 >
 Clear Selection
 </button>
 </div>
 </div>
 </div>
 )}

 {/* Error Display */}
 {error && (
 <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
 <p className="text-red-700">{error}</p>
 </div>
 )}

 {/* Wedding Form */}
 {showForm && (
 <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-8">
 <div className="p-4 sm:p-8">
 <div className="flex items-center justify-between mb-4 sm:mb-6">
 <h2 className="text-xl sm:text-2xl font-bold text-wedding-navy">
 {editingId ? 'Edit Wedding' : 'Create New Wedding'}
 </h2>
 {!editingId && (
 <button
 type="button"
 onClick={() => setShowTemplates(!showTemplates)}
 className="px-4 py-2 text-sm bg-wedding-sage text-white rounded-lg hover:bg-opacity-90 transition-colors"
 >
 {showTemplates ? 'Hide Templates' : 'Use Template'}
 </button>
 )}
 </div>

 {/* Wedding Templates */}
 {showTemplates && !editingId && (
 <div className="mb-6 p-4 bg-gray-50 rounded-lg">
 <h3 className="text-lg font-semibold text-gray-900 mb-3">Choose a Template</h3>
 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
 {weddingTemplates.map((template) => (
 <div
 key={template.id}
 className="p-4 bg-white border border-gray-200 rounded-lg hover:border-wedding-rose cursor-pointer transition-colors"
 onClick={() => applyTemplate(template)}
 >
 <h4 className="font-semibold text-wedding-navy">{template.name}</h4>
 <p className="text-sm text-gray-600 mt-1">{template.description}</p>
 <div className="mt-2 flex flex-wrap gap-1">
 {template.events.map((event, index) => (
 <span 
 key={index}
 className="inline-flex px-2 py-1 text-xs bg-wedding-sage bg-opacity-20 text-wedding-navy rounded"
 >
 {event.type.replace('_', ' ')}
 </span>
 ))}
 </div>
 </div>
 ))}
 </div>
 </div>
 )}
 
 <form onSubmit={handleSubmit} className="space-y-6">
 {/* Couple Names */}
 <div>
 <label htmlFor="couple_names" className="block text-sm font-medium text-gray-700 mb-2">
 Couple Names
 </label>
 <input
 type="text"
 id="couple_names"
 value={formData.couple_names}
 onChange={(e) => {
 setFormData({
 ...formData,
 couple_names: e.target.value,
 slug: generateSlug(e.target.value)
 });
 }}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 placeholder="John & Jane"
 required
 />
 </div>

 {/* Wedding Date */}
 <div>
 <label htmlFor="date" className="block text-sm font-medium text-gray-700 mb-2">
 Main Wedding Date
 </label>
 <input
 type="date"
 id="date"
 value={formData.date}
 onChange={(e) => setFormData({ ...formData, date: e.target.value })}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 required
 />
 </div>

 {/* URL Slug */}
 <div>
 <label htmlFor="slug" className="block text-sm font-medium text-gray-700 mb-2">
 URL Slug
 </label>
 <input
 type="text"
 id="slug"
 value={formData.slug}
 onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 placeholder="john-jane-wedding"
 required
 />
 <p className="mt-1 text-sm text-gray-500">
 This will be used in the URL: thespecialwedding.com/{formData.slug || 'your-wedding'}
 </p>
 </div>

 {/* Venue */}
 <div>
 <label htmlFor="venue" className="block text-sm font-medium text-gray-700 mb-2">
 Venue (Optional)
 </label>
 <input
 type="text"
 id="venue"
 value={formData.venue}
 onChange={(e) => setFormData({ ...formData, venue: e.target.value })}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 placeholder="Wedding Venue Name"
 />
 </div>

 {/* Assigned Planner (ROOT_ADMIN only) */}
 {userProfile?.is_root_admin && (
 <div>
 <label htmlFor="assigned_planner" className="block text-sm font-medium text-gray-700 mb-2">
 Assign Wedding Planner
 </label>
 <select
 id="assigned_planner"
 value={formData.assigned_planner_email}
 onChange={(e) => setFormData({ ...formData, assigned_planner_email: e.target.value })}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 >
 <option value="">Select a wedding planner...</option>
 {planners.map((planner) => (
 <option key={planner.id} value={planner.email}>
 {planner.name} ({planner.email})
 </option>
 ))}
 </select>
 <p className="mt-1 text-sm text-gray-500">
 Choose which wedding planner will manage this wedding
 </p>
 </div>
 )}

 {/* Status */}
 <div>
 <label htmlFor="status" className="block text-sm font-medium text-gray-700 mb-2">
 Wedding Status
 </label>
 <select
 id="status"
 value={formData.status}
 onChange={(e) => setFormData({ ...formData, status: e.target.value })}
 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 >
 <option value="draft">Draft</option>
 <option value="planning">Planning</option>
 <option value="active">Active</option>
 <option value="confirmed">Confirmed</option>
 <option value="completed">Completed</option>
 <option value="archived">Archived</option>
 <option value="cancelled">Cancelled</option>
 <option value="postponed">Postponed</option>
 </select>
 </div>

 {/* Events Section */}
 <div>
 <div className="flex justify-between items-center mb-4">
 <label className="block text-sm font-medium text-gray-700">
 Wedding Events
 </label>
 <button
 type="button"
 onClick={addEvent}
 className="text-sm bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90 transition-colors"
 >
 Add Event
 </button>
 </div>

 {formData.events.map((event, index) => (
 <div key={index} className="flex flex-col sm:flex-row gap-2 sm:gap-4 mb-3">
 <select
 value={event.type}
 onChange={(e) => updateEvent(index, 'type', e.target.value)}
 className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 required
 >
 <option value="">Select event type</option>
 <option value="traditional">Traditional</option>
 <option value="white_wedding">White Wedding</option>
 <option value="reception">Reception</option>
 <option value="engagement">Engagement</option>
 <option value="rehearsal">Rehearsal Dinner</option>
 </select>
 <input
 type="date"
 value={event.date}
 onChange={(e) => updateEvent(index, 'date', e.target.value)}
 className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
 required
 />
 <button
 type="button"
 onClick={() => removeEvent(index)}
 className="px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors self-start sm:self-auto"
 >
 Remove
 </button>
 </div>
 ))}
 </div>

 {/* Submit Button */}
 <button
 type="submit"
 disabled={loading}
 className="w-full bg-gradient-to-r from-wedding-rose to-wedding-gold text-white py-3 px-6 rounded-lg font-semibold hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-wedding-rose focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
 >
 {loading ? 'Saving...' : editingId ? 'Update Wedding' : 'Create Wedding'}
 </button>
 </form>
 </div>
 </div>
 )}

 {/* Weddings List */}
 <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
 <div className="p-4 sm:p-8">
 {/* Select All Header */}
 {weddings.length > 0 && !loading && (
 <div className="flex items-center mb-6 pb-4 border-b border-gray-200">
 <label className="flex items-center">
 <input
 type="checkbox"
 checked={selectedWeddings.length === weddings.length && weddings.length > 0}
 onChange={(e) => handleSelectAll(e.target.checked)}
 className="h-4 w-4 text-wedding-rose focus:ring-wedding-rose border-gray-300 rounded"
 />
 <span className="ml-2 text-sm text-gray-700">
 Select all ({weddings.length})
 </span>
 </label>
 <div className="ml-auto text-sm text-gray-500">
 {selectedWeddings.length} of {weddings.length} selected
 </div>
 </div>
 )}

 {loading && !showForm ? (
 <div className="flex items-center justify-center py-8">
 <div className="animate-spin h-8 w-8 border-4 border-wedding-rose border-t-transparent rounded-full"></div>
 <span className="ml-3 text-gray-600">Loading weddings...</span>
 </div>
 ) : weddings.length === 0 ? (
 <div className="text-center py-8 text-gray-500">
 <p className="text-lg">No weddings found.</p>
 <p className="text-sm mt-2">
 {userProfile?.is_root_admin ? 'Click "Create Wedding" to get started.' : 'No weddings assigned to you yet.'}
 </p>
 </div>
 ) : (
 <div className="grid gap-6">
 {weddings.map((wedding) => (
 <div key={wedding._id} className="border border-gray-200 rounded-xl p-4 sm:p-6 hover:shadow-lg transition-shadow">
 <div className="flex space-x-4">
 {/* Selection Checkbox */}
 <div className="flex-shrink-0 pt-1">
 <input
 type="checkbox"
 checked={selectedWeddings.includes(wedding._id)}
 onChange={(e) => handleSelectWedding(wedding._id, e.target.checked)}
 className="h-4 w-4 text-wedding-rose focus:ring-wedding-rose border-gray-300 rounded"
 />
 </div>
 
 <div className="flex-1 space-y-4">
 <div className="flex items-start justify-between">
 <h3 className="text-lg sm:text-xl font-bold text-wedding-navy">{wedding.couple_names}</h3>
 <span className={`px-2 py-1 text-xs font-medium rounded-full ${
 wedding.status === 'active' ? 'bg-green-100 text-green-800' :
 wedding.status === 'confirmed' ? 'bg-emerald-100 text-emerald-800' :
 wedding.status === 'planning' ? 'bg-blue-100 text-blue-800' :
 wedding.status === 'draft' ? 'bg-slate-100 text-slate-800' :
 wedding.status === 'completed' ? 'bg-purple-100 text-purple-800' :
 wedding.status === 'archived' ? 'bg-gray-100 text-gray-800' :
 wedding.status === 'postponed' ? 'bg-yellow-100 text-yellow-800' :
 wedding.status === 'cancelled' ? 'bg-red-100 text-red-800' :
 'bg-gray-100 text-gray-800'
 }`}>
 {wedding.status || 'active'}
 </span>
 </div>
 <p className="text-gray-600 mt-1 text-sm sm:text-base"> {wedding.date}</p>
 {wedding.venue && (
 <p className="text-gray-600 text-sm"> {wedding.venue}</p>
 )}
 <p className="text-xs sm:text-sm text-gray-500 mt-1 break-all">
 thespecialwedding.com/{wedding.slug}
 </p>
 
 {/* Planner Assignment */}
 {userProfile?.is_root_admin && (
 <div className="mt-2">
 {wedding.assigned_planner_email ? (
 <p className="text-sm text-green-600">
 Assigned to: {wedding.assigned_planner_email}
 </p>
 ) : (
 <p className="text-sm text-orange-600">
 No planner assigned
 </p>
 )}
 </div>
 )}

 {wedding.events && wedding.events.length > 0 && (
 <div className="mt-3">
 <p className="text-sm font-medium text-gray-700">Events:</p>
 <div className="flex flex-wrap gap-2 mt-1">
 {wedding.events.map((event, index) => (
 <span 
 key={index}
 className="inline-flex px-2 sm:px-3 py-1 text-xs font-semibold rounded-full bg-wedding-sage bg-opacity-20 text-wedding-navy"
 >
 {event.type.replace('_', ' ')} - {event.date}
 </span>
 ))}
 </div>
 </div>
 )}
 </div>
 <div className="flex flex-col sm:flex-row gap-2 w-full">
 <Link
 href={`/admin/weddings/${wedding._id}`}
 className="w-full sm:w-auto px-4 py-2 text-sm bg-wedding-rose text-white rounded-lg hover:bg-opacity-90 transition-colors text-center"
 >
 Configure
 </Link>
 <button
 onClick={() => handleEdit(wedding)}
 className="w-full sm:w-auto px-4 py-2 text-sm bg-wedding-sage text-white rounded-lg hover:bg-opacity-90 transition-colors"
 >
 Edit
 </button>
 <button
 onClick={() => handleDelete(wedding._id)}
 className="w-full sm:w-auto px-4 py-2 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
 >
 Delete
 </button>
 </div>
 </div>
 </div>
 </div>
 ))}
 </div>
 )}
 </div>
 </div>
 </div>
 </div>
 );
}