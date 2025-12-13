'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '@/components/ui/Card';

interface Wedding {
 id?: string;
 _id?: string;
 couple_names: string;
 date: string;
 slug: string;
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
 number_of_plus_ones_allowed?: number;
 plus_one_submitted: boolean;
 created_at?: string;
 updated_at?: string;
}

export default function AdminImportPage() {
 const { token } = useAdmin();
 const [file, setFile] = useState<File | null>(null);
 const [weddings, setWeddings] = useState<Wedding[]>([]);
 const [selectedWedding, setSelectedWedding] = useState<string>('');
 const [loading, setLoading] = useState(false);
 const [result, setResult] = useState<{ imported: number; tokens: string[] } | null>(null);
 const [error, setError] = useState<string>('');
 const [guests, setGuests] = useState<Guest[]>([]);
 const [loadingGuests, setLoadingGuests] = useState(false);

 const fetchWeddings = useCallback(async () => {
 if (!token) return;
 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 // Use authenticated planner endpoint to get assigned weddings
 const response = await fetch(`${baseUrl}/admin/planner/weddings`, {
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
 if (!selectedWedding) return;

 setLoadingGuests(true);
 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const response = await fetch(
 `${baseUrl}/admin/guests?wedding_id=${selectedWedding}`,
 {
 headers: {
 'Authorization': `Bearer ${token}`,
 },
 }
 );

 if (!response.ok) {
 throw new Error('Failed to fetch guests');
 }

 const data = await response.json();
 setGuests(Array.isArray(data) ? data : []);
 } catch (err) {
 console.error('Error fetching guests:', err);
 setError('Failed to load guests');
 setGuests([]);
 } finally {
 setLoadingGuests(false);
 }
 }, [selectedWedding, token]);

 useEffect(() => {
 fetchWeddings();
 }, [fetchWeddings]);

 useEffect(() => {
 if (selectedWedding) {
 fetchGuests();
 }
 }, [fetchGuests, selectedWedding]);

 const handleDeleteGuest = async (guestId: string) => {
 if (!confirm('Are you sure you want to delete this guest?')) return;

 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const response = await fetch(`${baseUrl}/admin/guests/${guestId}`, {
 method: 'DELETE',
 headers: {
 'Authorization': `Bearer ${token}`,
 },
 });

 if (response.ok) {
 fetchGuests(); // Refresh the list
 } else {
 setError('Failed to delete guest');
 }
 } catch (err) {
 setError('Failed to delete guest');
 }
 };

 const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
 const selectedFile = e.target.files?.[0];
 if (selectedFile && selectedFile.type === 'text/csv') {
 setFile(selectedFile);
 setError('');
 } else {
 setError('Please select a valid CSV file');
 setFile(null);
 }
 };

 const handleImport = async (e: React.FormEvent) => {
 e.preventDefault();

 if (!file || !selectedWedding) {
 setError('Please select both a CSV file and a wedding');
 return;
 }

 setLoading(true);
 setError('');
 setResult(null);

 try {
 const formData = new FormData();
 formData.append('file', file);

 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const response = await fetch(
 `${baseUrl}/admin/guests/import?wedding_id=${selectedWedding}`,
 {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 },
 body: formData,
 }
 );

 if (!response.ok) {
 const errorData = await response.json();
 throw new Error(errorData.detail || 'Import failed');
 }

 const data = await response.json();
 setResult(data);
 setFile(null);
 setSelectedWedding('');

 // Reset file input
 const fileInput = document.getElementById('csvFile') as HTMLInputElement;
 if (fileInput) fileInput.value = '';

 } catch (err) {
 setError(err instanceof Error ? err.message : 'Import failed');
 } finally {
 setLoading(false);
 }
 };

 return (
 <div className="min-h-screen dark:bg-transparent p-4 sm:p-6">
 <div className="max-w-4xl mx-auto space-y-8">
 {/* === IMPORT FORM CARD === */}
 <Card className="overflow-hidden">
 {/* Card header with sage→gold gradient */}
 <div className="bg-gradient-to-r from-wedding-sage to-wedding-gold px-8 py-6">
 <h1 className="text-3xl font-elegant text-white">Import Guests</h1>
 <p className="text-wedding-ivory mt-2">
 Upload a CSV file to import guest information
 </p>
 </div>

 <div className="p-4 sm:p-6 md:p-8 space-y-6 sm:space-y-8">
 {/* CSV Format Documentation */}
 <div className="p-4 sm:p-6 bg-gray-50 dark:bg-transparent rounded-xl border border-wedding-sage">
 <h2 className="text-lg font-semibold text-wedding-navy mb-3">
 CSV Format Requirements
 </h2>
 <p className="text-wedding-navy mb-3">
 Your CSV file should include the following columns:
 </p>
 <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-wedding-navy">
 <div>
 <strong>Required:</strong>
 <ul className="ml-4 mt-1 list-disc">
 <li>name (min. 2 chars)</li>
 <li>phone OR email (at least one)</li>
 </ul>
 </div>
 <div>
 <strong>Optional:</strong>
 <ul className="ml-4 mt-1 list-disc">
 <li>role (default: “guest”)</li>
 <li>plus_one_allowed (true/false)</li>
 <li>number_of_plus_ones_allowed (number)</li>
 <li>group_id (for grouping)</li>
 </ul>
 </div>
 </div>
 </div>

 {/* Import Form */}
 <form onSubmit={handleImport} className="space-y-6">
 {/* Select Wedding */}
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">
 Select Wedding
 </label>
 <select
 value={selectedWedding}
 onChange={(e) => setSelectedWedding(e.target.value)}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-sage focus:border-transparent"
 required
 >
 <option value="">Choose a wedding…</option>
 {weddings.map((w) => (
 <option key={w.id || w._id} value={w.id || w._id}>
 {w.couple_names} – {w.date}
 </option>
 ))}
 </select>
 </div>

 {/* CSV File Input */}
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">
 CSV File
 </label>
 <input
 type="file"
 accept=".csv"
 onChange={handleFileChange}
 className="
 w-full
 px-4 py-3
 border border-gray-300
 rounded-lg
 focus:ring-2 focus:ring-wedding-sage focus:border-transparent
 file:mr-4 file:py-2 file:px-4 file:rounded-full
 file:border-0 file:text-sm file:font-semibold
 file:bg-wedding-sage file:text-wedding-ivory
 hover:file:bg-wedding-gold hover:file:text-white
 "
 required
 />
 {file && (
 <p className="mt-2 text-sm text-green-600 dark:text-green-300">Selected: {file.name}</p>
 )}
 </div>

 {/* Error & Success Messages */}
 {error && (
 <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
 <p className="text-red-700 dark:text-red-300">{error}</p>
 </div>
 )}
 {result && (
 <div className="p-4 sm:p-6 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
 {/* … */}
 </div>
 )}

 {/* Submit Button */}
 <button
 type="submit"
 disabled={loading || !file || !selectedWedding}
 className="
 w-full
 py-3
 rounded-lg
 bg-gradient-to-r from-wedding-sage to-wedding-gold
 text-white font-semibold
 hover:from-wedding-rose hover:to-wedding-gold
 focus:outline-none focus:ring-2 focus:ring-wedding-sage
 disabled:opacity-50 disabled:cursor-not-allowed
 transition-all duration-200
 "
 >
 {loading ? 'Importing…' : 'Import Guests'}
 </button>
 </form>
 </div>
 </Card>
 {/* Guest Management Table */}
 {selectedWedding && (
 <div className="mt-8 bg-white dark:bg-slate-800 rounded-2xl shadow-xl overflow-hidden">
 <div className="bg-gradient-to-r from-wedding-navy to-wedding-sage px-8 py-6">
 <h2 className="text-2xl font-bold text-white">Guest Management</h2>
 <p className="text-blue-100 mt-2">
 {weddings.find(w => (w.id || w._id) === selectedWedding)?.couple_names} - Current Guests
 </p>
 </div>

 <div className="p-4 sm:p-6">
 {loadingGuests ? (
 <div className="flex items-center justify-center py-8">
 <div className="animate-spin h-8 w-8 border-4 border-wedding-rose border-t-transparent rounded-full"></div>
 <span className="ml-3 text-gray-600 dark:text-gray-400">Loading guests...</span>
 </div>
 ) : guests.length === 0 ? (
 <div className="text-center py-8 text-gray-500 dark:text-gray-400">
 <p>No guests found for this wedding.</p>
 <p className="text-sm mt-2">Import a CSV file to get started.</p>
 </div>
 ) : (
 <>
 {/* Mobile Card View */}
 <div className="md:hidden space-y-4">
 {guests.map((guest) => (
 <div key={guest.id || guest._id} className="bg-gray-50 dark:bg-slate-700/50 rounded-lg p-4 space-y-3">
 <div className="flex justify-between items-start">
 <div>
 <h3 className="font-semibold text-gray-900 dark:text-gray-100">{guest.name}</h3>
 {guest.group_id && (
 <p className="text-xs text-gray-500 dark:text-gray-400">Group: {guest.group_id}</p>
 )}
 </div>
 <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">
 {guest.role}
 </span>
 </div>
 <div className="space-y-1 text-sm">
 {guest.email && <div className="text-gray-600 dark:text-gray-400"> {guest.email}</div>}
 {guest.phone && <div className="text-gray-600 dark:text-gray-400"> {guest.phone}</div>}
 </div>
 <div className="flex justify-between items-center">
 <div className="text-sm">
 {guest.plus_one_allowed ? (
 <div>
 <span className="text-green-600 dark:text-green-300"> Plus one allowed</span>
 <span className="text-xs text-gray-500 dark:text-gray-400 ml-1">(Max: {guest.number_of_plus_ones_allowed || 0})</span>
 {guest.plus_one_submitted && (
 <span className="text-xs text-blue-600 ml-1">• Submitted</span>
 )}
 </div>
 ) : (
 <span className="text-gray-400">No plus one</span>
 )}
 </div>
 <button
 onClick={() => handleDeleteGuest(guest.id || guest._id || '')}
 className="text-red-600 dark:text-red-300 hover:text-red-900 transition-colors text-sm font-medium"
 >
 Delete
 </button>
 </div>
 <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
 <code className="text-xs bg-gray-200 px-2 py-1 rounded">
 {guest.token}
 </code>
 </div>
 </div>
 ))}
 </div>

 {/* Desktop Table View */}
 <div className="hidden md:block overflow-x-auto">
 <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
 <thead className="bg-gray-50 dark:bg-slate-700">
 <tr>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Name
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Contact
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Role
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Plus Ones
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Token
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
 Actions
 </th>
 </tr>
 </thead>
 <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-gray-700">
 {guests.map((guest) => (
 <tr key={guest.id || guest._id} className="hover:bg-gray-50 dark:bg-slate-700">
 <td className="px-6 py-4 whitespace-nowrap">
 <div className="text-sm font-medium text-gray-900 dark:text-gray-100">{guest.name}</div>
 {guest.group_id && (
 <div className="text-xs text-gray-500 dark:text-gray-400">Group: {guest.group_id}</div>
 )}
 </td>
 <td className="px-6 py-4 whitespace-nowrap">
 <div className="text-sm text-gray-900 dark:text-gray-100">
 {guest.email && <div>{guest.email}</div>}
 {guest.phone && <div>{guest.phone}</div>}
 </div>
 </td>
 <td className="px-6 py-4 whitespace-nowrap">
 <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">
 {guest.role}
 </span>
 </td>
 <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
 {guest.plus_one_allowed ? (
 <div>
 <span className="text-green-600 dark:text-green-300"> Allowed</span>
 <div className="text-xs text-gray-500 dark:text-gray-400">
 Max: {guest.number_of_plus_ones_allowed || 0}
 </div>
 {guest.plus_one_submitted && (
 <div className="text-xs text-blue-600">Submitted</div>
 )}
 </div>
 ) : (
 <span className="text-gray-400">Not allowed</span>
 )}
 </td>
 <td className="px-6 py-4 whitespace-nowrap">
 <code className="text-xs bg-gray-100 dark:bg-slate-700 px-2 py-1 rounded">
 {guest.token}
 </code>
 </td>
 <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
 <button
 onClick={() => handleDeleteGuest(guest.id || guest._id || '')}
 className="text-red-600 dark:text-red-300 hover:text-red-900 transition-colors"
 >
 Delete
 </button>
 </td>
 </tr>
 ))}
 </tbody>
 </table>
 </div>

 <div className="mt-4 flex flex-col sm:flex-row sm:justify-between items-center text-sm text-gray-600 dark:text-gray-400 gap-2">
 <span>Total guests: {guests.length}</span>
 <span>
 Plus one eligible: {guests.filter(g => g.plus_one_allowed).length}
 </span>
 </div>
 </>
 )}
 </div>
 </div>
 )}
 </div>
 </div>
 );
}