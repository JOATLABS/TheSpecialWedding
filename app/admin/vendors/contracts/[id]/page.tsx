'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter, useParams } from 'next/navigation';
import { toast } from 'sonner';
import { formatAdminTimestamp, formatAdminDate, DEFAULT_TIMEZONE } from '@/utils/dateFormat';
import {
  getCategoryLabel,
} from '@/services/vendorManagementApi';
import {
  getContract,
  updateContract,
  sendContract,
  getContractFormData,
  applyFormDataToContract,
  createPaymentMilestones,
  type VendorContract,
  type ContractSection,
  type FormDataForContract,
  getContractStatusColor,
} from '@/services/vendorContractsApi';

type TabId = 'details' | 'sections' | 'payments' | 'activity';

export default function ContractDetailPage() {
  const { token, userProfile } = useAdmin();
  const router = useRouter();
  const params = useParams();
  const contractId = params.id as string;

  // State
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [contract, setContract] = useState<VendorContract | null>(null);
  const [formData, setFormData] = useState<FormDataForContract | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('details');
  const [editMode, setEditMode] = useState(false);
  const [sendMessage, setSendMessage] = useState('');
  const [showSendModal, setShowSendModal] = useState(false);

  // Editable state
  const [editedContract, setEditedContract] = useState<Partial<VendorContract>>({});
  const [editedSections, setEditedSections] = useState<ContractSection[]>([]);

  // Fetch contract
  const fetchContract = useCallback(async () => {
    if (!token || !contractId) return;

    setLoading(true);
    try {
      const data = await getContract(token, contractId);
      setContract(data);
      setEditedContract(data);
      setEditedSections(data.sections || []);

      // Also fetch form data if available
      try {
        const formDataResult = await getContractFormData(token, contractId);
        setFormData(formDataResult);
      } catch {
        // Form data is optional
      }
    } catch (error) {
      console.error('Error fetching contract:', error);
      toast.error('Failed to load contract');
    } finally {
      setLoading(false);
    }
  }, [token, contractId]);

  useEffect(() => {
    fetchContract();
  }, [fetchContract]);

  // Save changes
  const handleSave = async () => {
    if (!token || !contractId) return;

    setSaving(true);
    try {
      const updatedContract = await updateContract(token, contractId, {
        ...editedContract,
        sections: editedSections,
      });
      setContract(updatedContract);
      setEditMode(false);
      toast.success('Contract saved successfully');
    } catch (error) {
      console.error('Error saving contract:', error);
      toast.error('Failed to save contract');
    } finally {
      setSaving(false);
    }
  };

  // Send contract
  const handleSend = async () => {
    if (!token || !contractId) return;

    setSending(true);
    try {
      const result = await sendContract(token, contractId, sendMessage || undefined);
      toast.success(`Contract sent to ${result.sent_to}`);
      setShowSendModal(false);
      setSendMessage('');
      fetchContract();
    } catch (error) {
      console.error('Error sending contract:', error);
      toast.error('Failed to send contract');
    } finally {
      setSending(false);
    }
  };

  // Update section
  const handleUpdateSection = (sectionId: string, field: 'title' | 'content', value: string) => {
    setEditedSections((prev) =>
      prev.map((s) => (s.id === sectionId ? { ...s, [field]: value } : s))
    );
  };

  // Add section
  const handleAddSection = () => {
    const newSection: ContractSection = {
      id: `section-${Date.now()}`,
      title: 'New Section',
      content: '',
      order: editedSections.length,
    };
    setEditedSections((prev) => [...prev, newSection]);
  };

  // Delete section
  const handleDeleteSection = (sectionId: string) => {
    setEditedSections((prev) => prev.filter((s) => s.id !== sectionId));
  };

  // Create payment milestones
  const handleCreateMilestones = async () => {
    if (!token || !contract) return;

    try {
      const depositAmount = contract.deposit_amount || contract.total_amount * 0.5;
      const balanceAmount = contract.total_amount - depositAmount;

      const milestones = [
        {
          description: 'Deposit - Due upon signing',
          amount: depositAmount,
          due_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
          percentage_of_total: (depositAmount / contract.total_amount) * 100,
        },
        {
          description: 'Final Balance - Due before event',
          amount: balanceAmount,
          due_date: contract.service_date || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
          percentage_of_total: (balanceAmount / contract.total_amount) * 100,
        },
      ];

      await createPaymentMilestones(token, contractId, milestones);
      toast.success('Payment milestones created');
    } catch (error) {
      console.error('Error creating milestones:', error);
      toast.error('Failed to create payment milestones');
    }
  };

  // Get status badge
  const getStatusBadge = (status: string) => {
    const colorClass = getContractStatusColor(status as VendorContract['status']);
    return (
      <span className={`px-3 py-1 text-sm font-medium rounded-full ${colorClass}`}>
        {status.replace('_', ' ').charAt(0).toUpperCase() + status.replace('_', ' ').slice(1)}
      </span>
    );
  };

  // Can edit check
  const canEdit = contract?.status === 'draft' || contract?.status === 'pending_review';
  const canSend = contract?.status === 'draft' || contract?.status === 'pending_review';

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-wedding-rose mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading contract...</p>
        </div>
      </div>
    );
  }

  if (!contract) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Contract Not Found</h2>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            The contract you&apos;re looking for doesn&apos;t exist or has been removed.
          </p>
          <button
            onClick={() => router.push('/admin/vendors')}
            className="px-4 py-2 bg-wedding-rose text-white rounded-lg"
          >
            Back to Vendors
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      {/* Header */}
      <div className="bg-white dark:bg-slate-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push('/admin/vendors')}
                className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
              </button>
              <div>
                <h1 className="text-xl sm:text-2xl font-semibold leading-tight text-slate-900 dark:text-white">{contract.contract_title}</h1>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {contract.contract_number} - {contract.vendor_name}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {getStatusBadge(contract.status)}

              {canEdit && (
                <>
                  {editMode ? (
                    <>
                      <button
                        onClick={() => {
                          setEditMode(false);
                          setEditedContract(contract);
                          setEditedSections(contract.sections || []);
                        }}
                        className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleSave}
                        disabled={saving}
                        className="px-4 py-2 bg-wedding-rose text-white rounded-lg font-medium hover:bg-wedding-rose/90 disabled:opacity-50"
                      >
                        {saving ? 'Saving...' : 'Save Changes'}
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => setEditMode(true)}
                      className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700 flex items-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                      Edit
                    </button>
                  )}
                </>
              )}

              {canSend && (
                <button
                  onClick={() => setShowSendModal(true)}
                  className="px-4 py-2 bg-gradient-to-r from-purple-600 to-wedding-rose text-white rounded-lg font-medium hover:opacity-90 flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                  Send to Vendor
                </button>
              )}
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 -mb-px">
            {[
              { id: 'details' as TabId, label: 'Details' },
              { id: 'sections' as TabId, label: 'Contract Sections' },
              { id: 'payments' as TabId, label: 'Payments' },
              { id: 'activity' as TabId, label: 'Activity' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-wedding-rose text-wedding-rose'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Details Tab */}
        {activeTab === 'details' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main details */}
            <div className="lg:col-span-2 space-y-6">
              <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Contract Information</h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
                      Contract Title
                    </label>
                    {editMode ? (
                      <input
                        type="text"
                        value={editedContract.contract_title || ''}
                        onChange={(e) => setEditedContract((prev) => ({ ...prev, contract_title: e.target.value }))}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                      />
                    ) : (
                      <p className="text-gray-900 dark:text-gray-100 font-medium">{contract.contract_title}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
                      Contract Number
                    </label>
                    <p className="text-gray-900 dark:text-gray-100 font-mono">{contract.contract_number || 'N/A'}</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
                      Total Amount
                    </label>
                    {editMode ? (
                      <input
                        type="number"
                        value={editedContract.total_amount || 0}
                        onChange={(e) => setEditedContract((prev) => ({ ...prev, total_amount: parseFloat(e.target.value) || 0 }))}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                      />
                    ) : (
                      <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                        ${contract.total_amount.toLocaleString()}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
                      Deposit Amount
                    </label>
                    <p className="text-gray-900 dark:text-gray-100">
                      ${(contract.deposit_amount || 0).toLocaleString()}
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
                      Service Date
                    </label>
                    {editMode ? (
                      <input
                        type="date"
                        value={editedContract.service_date?.split('T')[0] || ''}
                        onChange={(e) => setEditedContract((prev) => ({ ...prev, service_date: e.target.value }))}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                      />
                    ) : (
                      <p className="text-gray-900 dark:text-gray-100">
                        {contract.service_date ? formatAdminDate(contract.service_date) : 'Not set'}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
                      Service Location
                    </label>
                    {editMode ? (
                      <input
                        type="text"
                        value={editedContract.service_location || ''}
                        onChange={(e) => setEditedContract((prev) => ({ ...prev, service_location: e.target.value }))}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                      />
                    ) : (
                      <p className="text-gray-900 dark:text-gray-100">{contract.service_location || 'Not set'}</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Form data suggestion */}
              {formData && formData.vendor_submissions.length > 0 && (
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
                  <div className="flex items-start gap-3">
                    <svg className="w-5 h-5 text-blue-600 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div>
                      <h4 className="font-medium text-blue-900 dark:text-blue-200">Vendor Form Data Available</h4>
                      <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                        This vendor has submitted {formData.vendor_submissions.length} form(s) with data that can be used in this contract.
                      </p>
                      <button
                        onClick={() => {
                          if (formData && token && contractId) {
                            applyFormDataToContract(
                              token,
                              contractId,
                              (formData.vendor_submissions[0]?.data || {}) as Record<string, { value: unknown } | string>
                            )
                              .then((updated) => {
                                setContract(updated);
                                setEditedContract(updated);
                                setEditedSections(updated.sections || []);
                                toast.success('Form data applied to contract');
                              })
                              .catch(() => toast.error('Failed to apply form data'));
                          }
                        }}
                        className="text-sm text-blue-600 dark:text-blue-400 font-medium mt-2 hover:underline"
                      >
                        View & Apply Form Data
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Vendor info */}
              <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
                <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Vendor</h3>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 bg-gradient-to-br from-wedding-rose to-wedding-gold rounded-lg flex items-center justify-center text-white font-bold">
                    {contract.vendor_name.charAt(0)}
                  </div>
                  <div>
                    <div className="font-medium text-gray-900 dark:text-gray-100">{contract.vendor_name}</div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      {getCategoryLabel(contract.service_category, contract.custom_service_category)}
                    </div>
                  </div>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    {contract.vendor_email}
                  </div>
                  {contract.vendor_phone && (
                    <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                      </svg>
                      {contract.vendor_phone}
                    </div>
                  )}
                </div>
              </div>

              {/* Timeline */}
              <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
                <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Timeline</h3>
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
                      <svg className="w-4 h-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-gray-900 dark:text-gray-100">Created</div>
                      <div className="text-xs text-gray-500">{formatAdminTimestamp(contract.created_at)}</div>
                    </div>
                  </div>

                  {contract.sent_at && (
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                        <svg className="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                        </svg>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-900 dark:text-gray-100">Sent</div>
                        <div className="text-xs text-gray-500">{formatAdminTimestamp(contract.sent_at)}</div>
                      </div>
                    </div>
                  )}

                  {contract.viewed_at && (
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-indigo-100 dark:bg-indigo-900 flex items-center justify-center">
                        <svg className="w-4 h-4 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-900 dark:text-gray-100">Viewed</div>
                        <div className="text-xs text-gray-500">{formatAdminTimestamp(contract.viewed_at)}</div>
                      </div>
                    </div>
                  )}

                  {contract.signed_at && (
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-900 flex items-center justify-center">
                        <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-900 dark:text-gray-100">Signed</div>
                        <div className="text-xs text-gray-500">{formatAdminTimestamp(contract.signed_at)}</div>
                        {contract.signed_by_name && (
                          <div className="text-xs text-gray-500">by {contract.signed_by_name}</div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Sections Tab */}
        {activeTab === 'sections' && (
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Contract Sections</h2>
              {editMode && (
                <button
                  onClick={handleAddSection}
                  className="px-3 py-1.5 text-sm bg-wedding-rose text-white rounded-lg hover:bg-wedding-rose/90"
                >
                  + Add Section
                </button>
              )}
            </div>

            <div className="space-y-6">
              {(editMode ? editedSections : contract.sections).map((section, index) => (
                <div
                  key={section.id}
                  className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden"
                >
                  <div className="bg-gray-50 dark:bg-slate-700 px-4 py-3 flex items-center justify-between">
                    {editMode ? (
                      <input
                        type="text"
                        value={section.title}
                        onChange={(e) => handleUpdateSection(section.id, 'title', e.target.value)}
                        className="font-medium bg-transparent border-none focus:outline-none focus:ring-0 text-gray-900 dark:text-gray-100"
                      />
                    ) : (
                      <h3 className="font-medium text-gray-900 dark:text-gray-100">{section.title}</h3>
                    )}
                    {editMode && (
                      <button
                        onClick={() => handleDeleteSection(section.id)}
                        className="text-gray-400 hover:text-red-500"
                      >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    )}
                  </div>
                  <div className="p-4">
                    {editMode ? (
                      <textarea
                        value={section.content}
                        onChange={(e) => handleUpdateSection(section.id, 'content', e.target.value)}
                        rows={6}
                        className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 font-mono text-sm resize-y"
                      />
                    ) : (
                      <div className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                        {section.content}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {contract.terms_and_conditions && (
                <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
                  <div className="bg-gray-50 dark:bg-slate-700 px-4 py-3">
                    <h3 className="font-medium text-gray-900 dark:text-gray-100">Terms & Conditions</h3>
                  </div>
                  <div className="p-4">
                    <div className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                      {contract.terms_and_conditions}
                    </div>
                  </div>
                </div>
              )}

              {contract.cancellation_policy && (
                <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
                  <div className="bg-gray-50 dark:bg-slate-700 px-4 py-3">
                    <h3 className="font-medium text-gray-900 dark:text-gray-100">Cancellation Policy</h3>
                  </div>
                  <div className="p-4">
                    <div className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                      {contract.cancellation_policy}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Payments Tab */}
        {activeTab === 'payments' && (
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Payment Milestones</h2>
              <button
                onClick={handleCreateMilestones}
                className="px-4 py-2 bg-wedding-rose text-white rounded-lg font-medium hover:bg-wedding-rose/90"
              >
                Create Default Milestones
              </button>
            </div>

            <div className="text-center py-12 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl">
              <svg className="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No payment milestones</h3>
              <p className="text-gray-500 dark:text-gray-400">
                Create payment milestones to track deposits and payments for this contract.
              </p>
            </div>
          </div>
        )}

        {/* Activity Tab */}
        {activeTab === 'activity' && (
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-6">Activity Log</h2>

            <div className="space-y-4">
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                  <svg className="w-4 h-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                </div>
                <div>
                  <p className="text-gray-900 dark:text-gray-100">Contract created</p>
                  <p className="text-sm text-gray-500">{formatAdminTimestamp(contract.created_at)}</p>
                </div>
              </div>

              {contract.updated_at !== contract.created_at && (
                <div className="flex items-start gap-4">
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
                    <svg className="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-gray-900 dark:text-gray-100">Contract updated</p>
                    <p className="text-sm text-gray-500">{formatAdminTimestamp(contract.updated_at)}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Send Modal */}
      {showSendModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl w-full max-w-lg">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Send Contract</h2>
              <p className="text-sm text-gray-500 mt-1">
                Send this contract to {contract.vendor_name} for review and signing.
              </p>
            </div>

            <div className="p-6">
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Personal Message (optional)
                </label>
                <textarea
                  value={sendMessage}
                  onChange={(e) => setSendMessage(e.target.value)}
                  rows={4}
                  className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  placeholder="Add a personal note to accompany the contract..."
                />
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <svg className="w-5 h-5 text-blue-600 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                  <div>
                    <p className="text-sm text-blue-900 dark:text-blue-200">
                      An email will be sent to <strong>{contract.vendor_email}</strong> with a secure link to view and sign the contract.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="p-6 bg-gray-50 dark:bg-slate-700 rounded-b-2xl flex justify-end gap-3">
              <button
                onClick={() => setShowSendModal(false)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-600"
              >
                Cancel
              </button>
              <button
                onClick={handleSend}
                disabled={sending}
                className="px-6 py-2 bg-gradient-to-r from-purple-600 to-wedding-rose text-white rounded-lg font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
              >
                {sending ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Sending...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                    Send Contract
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
