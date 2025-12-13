'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

const vendorTypes = [
  'photographer', 'videographer', 'florist', 'caterer',
  'musician', 'decorator', 'makeup_artist', 'venue',
  'transport', 'baker', 'jewelry', 'other'
] as const;

type VendorType = typeof vendorTypes[number];

const isVendorType = (value: string): value is VendorType =>
  (vendorTypes as readonly string[]).includes(value);

interface VendorForm {
  _id?: string;
  wedding_id: string;
  form_name: string;
  vendor_email: string;
  vendor_name: string;
  vendor_type: VendorType;
  fields: FormField[];
  status: 'draft' | 'sent' | 'submitted' | 'approved' | 'rejected';
  created_at?: string;
  sent_at?: string;
  submitted_at?: string;
  submission_data?: any;
}

interface FormField {
  id: string;
  label: string;
  type: 'text' | 'email' | 'phone' | 'textarea' | 'number' | 'date' | 'select' | 'checkbox' | 'file';
  required: boolean;
  options?: string[];
  placeholder?: string;
}

interface Wedding {
  _id: string;
  couple_names: string;
  date: string;
  slug: string;
}

export default function VendorManagementPage() {
  const { token, userProfile, fetchUserProfile } = useAdmin();
  const router = useRouter();
  const [vendors, setVendors] = useState<VendorForm[]>([]);
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const [formData, setFormData] = useState<VendorForm>({
    wedding_id: '',
    form_name: '',
    vendor_email: '',
    vendor_name: '',
    vendor_type: 'photographer',
    fields: [],
    status: 'draft'
  });

  const defaultFields: Partial<Record<VendorType, FormField[]>> = {
    photographer: [
      { id: 'portfolio', label: 'Portfolio Link', type: 'text', required: true, placeholder: 'https://...' },
      { id: 'packages', label: 'Available Packages', type: 'textarea', required: true },
      { id: 'price_range', label: 'Price Range', type: 'text', required: true },
      { id: 'availability', label: 'Availability', type: 'date', required: true },
      { id: 'equipment', label: 'Equipment List', type: 'textarea', required: false },
      { id: 'experience', label: 'Years of Experience', type: 'number', required: true }
    ],
    caterer: [
      { id: 'menu_options', label: 'Menu Options', type: 'textarea', required: true },
      { id: 'guest_capacity', label: 'Maximum Guest Capacity', type: 'number', required: true },
      { id: 'price_per_person', label: 'Price Per Person', type: 'text', required: true },
      { id: 'dietary_options', label: 'Dietary Restrictions Catered', type: 'checkbox', required: false, options: ['Vegetarian', 'Vegan', 'Gluten-Free', 'Halal', 'Kosher'] },
      { id: 'service_style', label: 'Service Style', type: 'select', required: true, options: ['Buffet', 'Plated', 'Family Style', 'Cocktail'] }
    ],
    florist: [
      { id: 'specialties', label: 'Floral Specialties', type: 'textarea', required: true },
      { id: 'seasonal_flowers', label: 'Seasonal Flower Availability', type: 'textarea', required: true },
      { id: 'arrangement_types', label: 'Arrangement Types', type: 'checkbox', required: true, options: ['Bridal Bouquet', 'Centerpieces', 'Ceremony Arch', 'Boutonnieres', 'Corsages'] },
      { id: 'delivery_setup', label: 'Delivery and Setup Included', type: 'select', required: true, options: ['Yes', 'No', 'Additional Cost'] }
    ]
  };

  const fetchVendors = useCallback(async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/vendor-forms`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setVendors(data);
      }
    } catch (err) {
      console.error('Error fetching vendors:', err);
    }
  }, [token]);

  const fetchWeddings = useCallback(async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const endpoint = userProfile?.is_root_admin
        ? `${baseUrl}/admin/weddings`
        : `${baseUrl}/admin/planner/weddings`;
      const response = await fetch(endpoint, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setWeddings(data);
      }
    } catch (err) {
      console.error('Error fetching weddings:', err);
    }
  }, [token, userProfile?.is_root_admin]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([fetchVendors(), fetchWeddings()]);
    } catch (err) {
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [fetchVendors, fetchWeddings]);

  useEffect(() => {
    if (!userProfile) {
      fetchUserProfile();
    } else if (!userProfile.is_wedding_planner && !userProfile.is_root_admin) {
      router.push('/admin');
    } else {
      fetchData();
    }
  }, [fetchData, fetchUserProfile, router, userProfile]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const url = editingId
        ? `${baseUrl}/admin/vendor-forms/${editingId}`
        : `${baseUrl}/admin/vendor-forms`;

      const method = editingId ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save vendor form');
      }

      resetForm();
      fetchVendors();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save vendor form');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      wedding_id: '',
      form_name: '',
      vendor_email: '',
      vendor_name: '',
      vendor_type: 'photographer',
      fields: [],
      status: 'draft'
    });
    setShowForm(false);
    setEditingId(null);
  };

  const handleVendorTypeChange = (type: string) => {
    const nextType: VendorType = isVendorType(type) ? type : 'other';
    const defaultFieldsForType = defaultFields[nextType] ?? [];
    setFormData(previous => ({
      ...previous,
      vendor_type: nextType,
      fields: defaultFieldsForType.map(field => ({ ...field }))
    }));
  };

  const sendVendorForm = async (vendorId: string) => {
    try {
      setLoading(true);
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/vendor-forms/${vendorId}/send`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        fetchVendors();
        alert('Vendor form sent successfully!');
      } else {
        throw new Error('Failed to send vendor form');
      }
    } catch (err) {
      setError('Failed to send vendor form');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const statusStyles = {
      draft: 'bg-gray-100 text-gray-800',
      sent: 'bg-blue-100 text-blue-800',
      submitted: 'bg-green-100 text-green-800',
      approved: 'bg-emerald-100 text-emerald-800',
      rejected: 'bg-red-100 text-red-800'
    };

    return (
      <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusStyles[status as keyof typeof statusStyles] || statusStyles.draft}`}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  if (loading && vendors.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading vendor management...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-wedding-ivory to-rose-50 p-4 sm:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl overflow-hidden mb-8">
          <div className="bg-gradient-to-r from-wedding-navy to-wedding-gold px-4 sm:px-8 py-4 sm:py-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
              <div>
                <h1 className="text-2xl sm:text-3xl font-bold text-white">Vendor Management</h1>
                <p className="text-blue-100 mt-1 sm:mt-2 text-sm sm:text-base">
                  Send forms to vendors and manage their submissions
                </p>
              </div>
              <button
                onClick={() => {
                  setShowForm(!showForm);
                  if (!showForm) resetForm();
                }}
                className="bg-white text-wedding-navy px-4 sm:px-6 py-2 sm:py-3 rounded-lg font-semibold hover:bg-gray-50 dark:bg-transparent transition-colors text-sm sm:text-base w-full sm:w-auto"
              >
                {showForm ? 'Cancel' : 'Create Vendor Form'}
              </button>
            </div>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-red-700 dark:text-red-300">{error}</p>
          </div>
        )}

        {/* Vendor Form Creation */}
        {showForm && (
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl overflow-hidden mb-8">
            <div className="p-4 sm:p-8">
              <h2 className="text-xl sm:text-2xl font-bold text-wedding-navy mb-4 sm:mb-6">
                {editingId ? 'Edit Vendor Form' : 'Create New Vendor Form'}
              </h2>
              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Wedding Selection */}
                <div>
                  <label htmlFor="wedding_id" className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">
                    Select Wedding
                  </label>
                  <select
                    id="wedding_id"
                    value={formData.wedding_id}
                    onChange={(e) => setFormData({ ...formData, wedding_id: e.target.value })}
                    className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    required
                  >
                    <option value="">Select a wedding...</option>
                    {weddings.map((wedding) => (
                      <option key={wedding._id} value={wedding._id}>
                        {wedding.couple_names} - {wedding.date}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Form Name */}
                <div>
                  <label htmlFor="form_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">
                    Form Name
                  </label>
                  <input
                    type="text"
                    id="form_name"
                    value={formData.form_name}
                    onChange={(e) => setFormData({ ...formData, form_name: e.target.value })}
                    className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    placeholder="e.g., Photography Services Quote"
                    required
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Vendor Name */}
                  <div>
                    <label htmlFor="vendor_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">
                      Vendor Name
                    </label>
                    <input
                      type="text"
                      id="vendor_name"
                      value={formData.vendor_name}
                      onChange={(e) => setFormData({ ...formData, vendor_name: e.target.value })}
                      className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      placeholder="Vendor or Company Name"
                      required
                    />
                  </div>

                  {/* Vendor Email */}
                  <div>
                    <label htmlFor="vendor_email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">
                      Vendor Email
                    </label>
                    <input
                      type="email"
                      id="vendor_email"
                      value={formData.vendor_email}
                      onChange={(e) => setFormData({ ...formData, vendor_email: e.target.value })}
                      className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      placeholder="vendor@example.com"
                      required
                    />
                  </div>
                </div>

                {/* Vendor Type */}
                <div>
                  <label htmlFor="vendor_type" className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">
                    Vendor Type
                  </label>
                  <select
                    id="vendor_type"
                    value={formData.vendor_type}
                    onChange={(e) => handleVendorTypeChange(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    required
                  >
                    {vendorTypes.map((type) => (
                      <option key={type} value={type}>
                        {type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Form Fields Preview */}
                {formData.fields.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Form Fields Preview</h3>
                    <div className="bg-gray-50 dark:bg-slate-700 p-4 rounded-lg space-y-4">
                      {formData.fields.map((field, index) => (
                        <div key={field.id} className="flex items-center justify-between p-3 bg-white border border-gray-200 dark:border-gray-700 rounded">
                          <div>
                            <span className="font-medium">{field.label}</span>
                            <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">({field.type})</span>
                            {field.required && <span className="ml-1 text-red-500">*</span>}
                          </div>
                          <div className="text-sm text-gray-400">
                            {field.options && `Options: ${field.options.join(', ')}`}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-wedding-rose to-wedding-gold text-white py-3 px-6 rounded-lg font-semibold hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-wedding-rose focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  {loading ? 'Creating...' : editingId ? 'Update Form' : 'Create Form'}
                </button>
              </form>
            </div>
          </div>
        )}

        {/* Vendor Forms List */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl overflow-hidden">
          <div className="p-4 sm:p-8">
            <h2 className="text-xl font-bold text-wedding-navy mb-6">Vendor Forms</h2>
            {vendors.length === 0 ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                <p className="text-lg">No vendor forms created yet.</p>
                <p className="text-sm mt-2">Create your first vendor form to get started.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-slate-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Form Details
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Vendor
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Wedding
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-gray-700">
                    {vendors.map((vendor) => (
                      <tr key={vendor._id} className="hover:bg-gray-50 dark:bg-slate-700">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900 dark:text-gray-100">{vendor.form_name}</div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">{vendor.vendor_type.replace('_', ' ')}</div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900 dark:text-gray-100">{vendor.vendor_name}</div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">{vendor.vendor_email}</div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900 dark:text-gray-100">
                            {weddings.find(w => w._id === vendor.wedding_id)?.couple_names || 'Unknown'}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {getStatusBadge(vendor.status)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                          {vendor.status === 'draft' && (
                            <button
                              onClick={() => sendVendorForm(vendor._id!)}
                              className="text-blue-600 hover:text-blue-900"
                            >
                              Send
                            </button>
                          )}
                          {vendor.status === 'submitted' && (
                            <button
                              onClick={() => router.push(`/admin/vendors/${vendor._id}/submission`)}
                              className="text-green-600 dark:text-green-300 hover:text-green-900"
                            >
                              View Submission
                            </button>
                          )}
                          {vendor._id && (
                            <Link
                              href={`/vendor-form/${vendor._id}`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-indigo-600 hover:text-indigo-900"
                            >
                              Preview
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}