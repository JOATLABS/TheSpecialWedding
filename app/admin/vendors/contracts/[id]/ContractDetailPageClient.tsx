'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter, useParams } from 'next/navigation';
import { toast } from 'sonner';
import { formatAdminTimestamp, formatAdminDate } from '@/utils/dateFormat';
import VendorContractPreview from '@/components/contracts/VendorContractPreview';
import { PaymentMilestones } from '../../components/PaymentMilestones';
import {
  buildContractKeyDates,
  buildEditableContractState,
  getContractDetailControlState,
  sortContractRevisionHistory,
} from '../contractDetailViewState';
import {
  getCategoryLabel,
} from '@/services/vendorManagementApi';
import {
  getContract,
  getContractRevisions,
  getContractActivity,
  updateContract,
  sendContract,
  createContractRevision,
  duplicateContract,
  getContractFormData,
  applyFormDataToContract,
  type VendorContract,
  type ContractSection,
  type VendorContractActivityItem,
  type VendorContractActivityResponse,
  type VendorContractFormDataResponse,
  type VendorContractRevisionHistoryResponse,
  getContractStatusColor,
} from '@/services/vendorContractsApi';

type TabId = 'details' | 'sections' | 'payments' | 'activity';

interface ContractDetailPageServices {
  getCategoryLabel: typeof getCategoryLabel;
  getContract: typeof getContract;
  getContractRevisions: typeof getContractRevisions;
  getContractActivity: typeof getContractActivity;
  updateContract: typeof updateContract;
  sendContract: typeof sendContract;
  createContractRevision: typeof createContractRevision;
  duplicateContract: typeof duplicateContract;
  getContractFormData: typeof getContractFormData;
  applyFormDataToContract: typeof applyFormDataToContract;
}

const defaultContractDetailPageServices: ContractDetailPageServices = {
  getCategoryLabel,
  getContract,
  getContractRevisions,
  getContractActivity,
  updateContract,
  sendContract,
  createContractRevision,
  duplicateContract,
  getContractFormData,
  applyFormDataToContract,
};

interface ContractDetailPageRuntimeProps {
  token: string | null;
  contractId: string;
  router: { push: (href: string) => void };
  services?: ContractDetailPageServices;
  PaymentMilestonesComponent?: typeof PaymentMilestones;
  notifier?: Pick<typeof toast, 'success' | 'error'>;
}

interface ContractDetailPageProps {
  runtimeOverrides?: ContractDetailPageRuntimeProps;
}

function ContractDetailPageContent({
  token,
  contractId,
  router,
  services = defaultContractDetailPageServices,
  PaymentMilestonesComponent = PaymentMilestones,
  notifier = toast,
}: ContractDetailPageRuntimeProps) {

  // State
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [contract, setContract] = useState<VendorContract | null>(null);
  const [formData, setFormData] = useState<VendorContractFormDataResponse | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('details');
  const [editMode, setEditMode] = useState(false);
  const [sendMessage, setSendMessage] = useState('');
  const [showSendModal, setShowSendModal] = useState(false);
  const [revisions, setRevisions] = useState<VendorContractRevisionHistoryResponse | null>(null);
  const [showRevisionModal, setShowRevisionModal] = useState(false);
  const [revisionKind, setRevisionKind] = useState<'revision' | 'amendment'>('revision');
  const [revisionReason, setRevisionReason] = useState('');
  const [creatingRevision, setCreatingRevision] = useState(false);
  const [duplicating, setDuplicating] = useState(false);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activity, setActivity] = useState<VendorContractActivityResponse | null>(null);
  const [activityError, setActivityError] = useState<string | null>(null);

  // Editable state
  const [editedContract, setEditedContract] = useState<Partial<VendorContract>>({});
  const [editedSections, setEditedSections] = useState<ContractSection[]>([]);

  // Fetch contract
  const fetchContract = useCallback(async () => {
    if (!token || !contractId) return;

    setLoading(true);
    try {
      const data = await services.getContract(token, contractId);
      setContract(data);
      const nextState = buildEditableContractState(data);
      setEditedContract(nextState.editedContract);
      setEditedSections(nextState.editedSections);

      // Also fetch form data if available
      try {
        const formDataResult = await services.getContractFormData(token, contractId);
        setFormData(formDataResult);
      } catch {
        // Form data is optional
      }
    } catch (error) {
      console.error('Error fetching contract:', error);
      notifier.error('Failed to load contract');
    } finally {
      setLoading(false);
    }
  }, [token, contractId, notifier, services]);

  const fetchRevisions = useCallback(async () => {
    if (!token || !contractId) return;

    try {
      const data = await services.getContractRevisions(token, contractId);
      setRevisions(data);
    } catch (error) {
      console.error('Error fetching contract revisions:', error);
      setRevisions(null);
    }
  }, [token, contractId, services]);

  const fetchActivity = useCallback(async () => {
    if (!token || !contractId) return;

    setActivityLoading(true);
    setActivityError(null);
    try {
      const data = await services.getContractActivity(token, contractId);
      setActivity(data);
    } catch (error) {
      console.error('Error fetching contract activity:', error);
      setActivityError(
        error instanceof Error ? error.message : 'Failed to load contract activity'
      );
    } finally {
      setActivityLoading(false);
    }
  }, [token, contractId, services]);

  useEffect(() => {
    void fetchContract();
    void fetchRevisions();
    void fetchActivity();
  }, [fetchActivity, fetchContract, fetchRevisions]);

  // Save changes
  const handleSave = async () => {
    if (!token || !contractId) return;

    setSaving(true);
    try {
      const updatedContract = await services.updateContract(token, contractId, {
        ...editedContract,
        sections: editedSections,
      });
      setContract(updatedContract);
      setEditMode(false);
      void fetchActivity();
      notifier.success('Contract saved successfully');
    } catch (error) {
      console.error('Error saving contract:', error);
      notifier.error('Failed to save contract');
    } finally {
      setSaving(false);
    }
  };

  // Send contract
  const handleSend = async () => {
    if (!token || !contractId) return;

    setSending(true);
    try {
      const result = await services.sendContract(token, contractId, sendMessage || undefined);
      notifier.success(`Contract sent to ${result.sent_to}`);
      setShowSendModal(false);
      setSendMessage('');
      void fetchContract();
      void fetchRevisions();
      void fetchActivity();
    } catch (error) {
      console.error('Error sending contract:', error);
      notifier.error('Failed to send contract');
    } finally {
      setSending(false);
    }
  };

  const handleDuplicate = async () => {
    if (!token || !contractId) return;

    setDuplicating(true);
    try {
      const duplicated = await services.duplicateContract(token, contractId, {});
      notifier.success('Contract duplicated as a new draft');
      router.push(`/admin/vendors/contracts/${duplicated._id}`);
    } catch (error) {
      console.error('Error duplicating contract:', error);
      notifier.error(
        error instanceof Error ? error.message : 'Failed to duplicate contract'
      );
    } finally {
      setDuplicating(false);
    }
  };

  const handleCreateRevision = async () => {
    if (!token || !contractId) return;

    setCreatingRevision(true);
    try {
      const nextRevision = await services.createContractRevision(token, contractId, {
        revision_kind: revisionKind,
        reason: revisionReason || undefined,
      });
      notifier.success(
        revisionKind === 'amendment'
          ? 'Amendment draft created'
          : 'Revision draft created'
      );
      setShowRevisionModal(false);
      setRevisionReason('');
      router.push(`/admin/vendors/contracts/${nextRevision._id}`);
    } catch (error) {
      console.error('Error creating contract revision:', error);
      notifier.error(
        error instanceof Error ? error.message : 'Failed to create contract revision'
      );
    } finally {
      setCreatingRevision(false);
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

  const buildSuggestedFieldMappings = (
    data: VendorContractFormDataResponse
  ): Record<string, string> => {
    return Object.entries(data.suggested_contract_fields).reduce<Record<string, string>>(
      (mappings, [placeholder, suggestion]) => {
        if (suggestion?.source_field) {
          mappings[suggestion.source_field] = placeholder;
        }
        return mappings;
      },
      {}
    );
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

  const detailControlState = getContractDetailControlState(contract, revisions);
  const {
    canEdit,
    canSend,
    canCreateRevision,
    paymentsReadOnly,
    defaultRevisionLabel,
    showHistoricalBanner,
  } = detailControlState;
  const sortedRevisionHistory = sortContractRevisionHistory(revisions);
  const activityItems = activity?.items || [];
  const keyDates = buildContractKeyDates(contract);

  const getActivityAccentClass = (activityType: VendorContractActivityItem['activity_type']) => {
    switch (activityType) {
      case 'contract_signed':
      case 'payment_recorded':
        return 'bg-emerald-500';
      case 'contract_sent':
      case 'milestones_created':
        return 'bg-blue-500';
      case 'revision_created':
      case 'contract_superseded':
      case 'contract_duplicated':
        return 'bg-amber-500';
      case 'form_data_applied':
        return 'bg-violet-500';
      default:
        return 'bg-slate-400';
    }
  };

  const formatActivityActor = (item: VendorContractActivityItem) => {
    if (item.actor.display_name) return item.actor.display_name;
    if (item.actor.identifier) return item.actor.identifier;
    if (item.actor.type === 'planner') return 'Planner';
    if (item.actor.type === 'vendor') return 'Vendor';
    return 'System';
  };

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
          <div className="flex items-center justify-between min-h-16 py-3">
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
                <div className="flex flex-wrap items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                  <span>{contract.contract_number} - {contract.vendor_name}</span>
                  <span className="hidden sm:inline">•</span>
                  <span>Version {contract.version_number || 1}</span>
                  <span className="hidden sm:inline">•</span>
                  <span className="capitalize">{contract.contract_kind || 'original'}</span>
                  {contract.is_current_version === false && (
                    <>
                      <span className="hidden sm:inline">•</span>
                      <span className="text-amber-600 dark:text-amber-400">Historical version</span>
                    </>
                  )}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-3">
              {getStatusBadge(contract.status)}

              {canCreateRevision && (
                <button
                  onClick={() => {
                    setRevisionKind(contract.status === 'signed' ? 'amendment' : 'revision');
                    setRevisionReason('');
                    setShowRevisionModal(true);
                  }}
                  className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700 flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  {defaultRevisionLabel}
                </button>
              )}

              <button
                onClick={handleDuplicate}
                disabled={duplicating}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700 disabled:opacity-50 flex items-center gap-2"
                title="Create an independent copy of this contract as a new draft"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                {duplicating ? 'Duplicating...' : 'Duplicate'}
              </button>

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
        {showHistoricalBanner && (
          <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-amber-900 dark:border-amber-900/60 dark:bg-amber-900/20 dark:text-amber-100">
            <div className="flex items-start gap-3">
              <svg className="mt-0.5 h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p className="font-medium">This is a historical contract version.</p>
                <p className="mt-1 text-sm text-amber-800 dark:text-amber-200">
                  It remains visible for reference, but it is no longer the live version the vendor can review or sign.
                </p>
              </div>
            </div>
          </div>
        )}

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
                            const selectedSubmission = formData.vendor_submissions[0];
                            if (!selectedSubmission) {
                              notifier.error('No vendor submission is available to apply');
                              return;
                            }

                            services.applyFormDataToContract(
                              token,
                              contractId,
                              {
                                form_submission_id: selectedSubmission._id,
                                field_mappings: buildSuggestedFieldMappings(formData),
                              }
                            )
                              .then((updated) => {
                                const nextState = buildEditableContractState(updated);
                                setContract(nextState.contract);
                                setEditedContract(nextState.editedContract);
                                setEditedSections(nextState.editedSections);
                                void fetchActivity();
                                notifier.success('Form data applied to contract');
                              })
                              .catch(() => notifier.error('Failed to apply form data'));
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
              <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
                <div className="flex items-center justify-between gap-3 mb-4">
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100">Version History</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Lineage for this vendor contract.
                    </p>
                  </div>
                  <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600 dark:bg-slate-700 dark:text-gray-300">
                    {sortedRevisionHistory.length || 1} version{(sortedRevisionHistory.length || 1) === 1 ? '' : 's'}
                  </span>
                </div>

                <div className="space-y-3">
                  {sortedRevisionHistory.length > 0 ? (
                    sortedRevisionHistory.map((revision) => {
                      const isActiveRevision = revision.id === contract._id;
                      return (
                        <button
                          key={revision.id}
                          onClick={() => router.push(`/admin/vendors/contracts/${revision.id}`)}
                          className={`w-full rounded-xl border px-4 py-3 text-left transition-colors ${
                            isActiveRevision
                              ? 'border-wedding-rose bg-wedding-rose/5'
                              : 'border-gray-200 hover:border-wedding-rose/40 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-slate-700/60'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <div className="font-medium text-gray-900 dark:text-gray-100">
                                Version {revision.version_number}
                              </div>
                              <div className="text-xs text-gray-500 dark:text-gray-400 capitalize">
                                {revision.contract_kind} · {revision.status.replace('_', ' ')}
                              </div>
                            </div>
                            {revision.is_current_version && (
                              <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/40 dark:text-green-300">
                                Current
                              </span>
                            )}
                          </div>
                          <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                            {revision.contract_number || 'No contract number'} · Created {formatAdminTimestamp(revision.created_at)}
                          </div>
                        </button>
                      );
                    })
                  ) : (
                    <div className="rounded-xl border border-dashed border-gray-300 px-4 py-5 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
                      No revision history yet.
                    </div>
                  )}
                </div>
              </div>

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
                      {services.getCategoryLabel(contract.service_category, contract.custom_service_category)}
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

              {/* Key Dates */}
              <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
                <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Key Dates</h3>
                <div className="space-y-3">
                  {keyDates.map((item) => (
                    <div
                      key={item.label}
                      className="flex items-center justify-between gap-4 rounded-xl bg-gray-50 px-4 py-3 text-sm dark:bg-slate-900/60"
                    >
                      <span className="font-medium text-gray-700 dark:text-gray-300">{item.label}</span>
                      <span className="text-right text-gray-500 dark:text-gray-400">
                        {formatAdminTimestamp(item.value)}
                      </span>
                    </div>
                  ))}
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

            {editMode ? (
              <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-6">
                <div className="space-y-6">
                  {editedSections.map((section) => (
                    <div
                      key={section.id}
                      className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden"
                    >
                      <div className="bg-gray-50 dark:bg-slate-700 px-4 py-3 flex items-center justify-between">
                        <input
                          type="text"
                          value={section.title}
                          onChange={(e) => handleUpdateSection(section.id, 'title', e.target.value)}
                          className="flex-1 font-medium bg-transparent border-none focus:outline-none focus:ring-0 text-gray-900 dark:text-gray-100"
                        />
                        <button
                          onClick={() => handleDeleteSection(section.id)}
                          className="text-gray-400 hover:text-red-500"
                        >
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                      <div className="p-4">
                        <textarea
                          value={section.content}
                          onChange={(e) => handleUpdateSection(section.id, 'content', e.target.value)}
                          rows={6}
                          className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 font-mono text-sm resize-y"
                        />
                      </div>
                    </div>
                  ))}

                  <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
                    <div className="bg-gray-50 dark:bg-slate-700 px-4 py-3">
                      <h3 className="font-medium text-gray-900 dark:text-gray-100">Terms & Conditions</h3>
                    </div>
                    <div className="p-4">
                      <textarea
                        value={editedContract.terms_and_conditions || ''}
                        onChange={(e) => setEditedContract((prev) => ({ ...prev, terms_and_conditions: e.target.value }))}
                        rows={6}
                        className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 font-mono text-sm resize-y"
                        placeholder="Enter terms and conditions..."
                      />
                    </div>
                  </div>

                  <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
                    <div className="bg-gray-50 dark:bg-slate-700 px-4 py-3">
                      <h3 className="font-medium text-gray-900 dark:text-gray-100">Cancellation Policy</h3>
                    </div>
                    <div className="p-4">
                      <textarea
                        value={editedContract.cancellation_policy || ''}
                        onChange={(e) => setEditedContract((prev) => ({ ...prev, cancellation_policy: e.target.value }))}
                        rows={6}
                        className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 font-mono text-sm resize-y"
                        placeholder="Enter cancellation policy..."
                      />
                    </div>
                  </div>

                  <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
                    <div className="bg-gray-50 dark:bg-slate-700 px-4 py-3">
                      <h3 className="font-medium text-gray-900 dark:text-gray-100">Custom Clauses</h3>
                    </div>
                    <div className="p-4">
                      <textarea
                        value={editedContract.custom_clauses || ''}
                        onChange={(e) => setEditedContract((prev) => ({ ...prev, custom_clauses: e.target.value }))}
                        rows={6}
                        className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 font-mono text-sm resize-y"
                        placeholder="Enter any custom clauses..."
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Live Document Preview
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      This uses the same contract rendering path the vendor sees.
                    </p>
                  </div>
                  <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-slate-900/60 p-4 max-h-[900px] overflow-y-auto">
                    <VendorContractPreview
                      sections={editedSections}
                      termsAndConditions={editedContract.terms_and_conditions || ''}
                      cancellationPolicy={editedContract.cancellation_policy || ''}
                      customClauses={editedContract.custom_clauses || ''}
                    />
                  </div>
                </div>
              </div>
            ) : (
              <VendorContractPreview
                sections={contract.sections}
                termsAndConditions={contract.terms_and_conditions}
                cancellationPolicy={contract.cancellation_policy}
                customClauses={contract.custom_clauses}
              />
            )}
          </div>
        )}

        {/* Payments Tab */}
        {activeTab === 'payments' && (
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Payment Milestones</h2>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Track deposits and payments for this contract.
              </p>
            </div>

            {token ? (
              <PaymentMilestonesComponent
                token={token}
                contractId={contractId}
                vendorName={contract.vendor_name}
                vendorEmail={contract.vendor_email}
                coupleEmail={contract.couple_email ?? undefined}
                coupleNames={contract.couple_names ?? undefined}
                totalAmount={contract.total_amount}
                readOnly={paymentsReadOnly}
                onMilestoneUpdated={() => {
                  void fetchActivity();
                }}
              />
            ) : (
              <div className="rounded-xl border border-dashed border-gray-300 px-4 py-8 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
                Admin session is required to manage payment milestones.
              </div>
            )}
          </div>
        )}

        {/* Activity Tab */}
        {activeTab === 'activity' && (
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-6">Activity Log</h2>

            {activityLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="text-center">
                  <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-b-2 border-wedding-rose" />
                  <p className="text-sm text-gray-500 dark:text-gray-400">Loading activity...</p>
                </div>
              </div>
            ) : activityError ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-5 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-900/20 dark:text-red-200">
                {activityError}
              </div>
            ) : activityItems.length === 0 ? (
              <div className="rounded-xl border border-dashed border-gray-300 px-4 py-8 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
                No contract activity yet.
              </div>
            ) : (
              <div className="space-y-4">
                {activityItems.map((item) => (
                  <div key={item.id} className="flex items-start gap-4">
                    <div className={`mt-1 h-3 w-3 shrink-0 rounded-full ${getActivityAccentClass(item.activity_type)}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium text-gray-900 dark:text-gray-100">{item.title}</p>
                        <span className="text-xs text-gray-400 dark:text-gray-500">•</span>
                        <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                          {formatActivityActor(item)}
                        </p>
                      </div>
                      {item.description && (
                        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{item.description}</p>
                      )}
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {formatAdminTimestamp(item.created_at)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
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

      {showRevisionModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl w-full max-w-lg">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                {contract.status === 'signed' ? 'Create Amendment Draft' : 'Create Revision Draft'}
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                This creates a new draft version without changing the current live contract until the new version is sent.
              </p>
            </div>

            <div className="p-6 space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Draft Type
                </label>
                <select
                  value={revisionKind}
                  onChange={(e) => setRevisionKind(e.target.value as 'revision' | 'amendment')}
                  className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                >
                  <option value="revision">Revision</option>
                  <option value="amendment">Amendment</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Reason (optional)
                </label>
                <textarea
                  value={revisionReason}
                  onChange={(e) => setRevisionReason(e.target.value)}
                  rows={4}
                  className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  placeholder="Explain what changed in this new version..."
                />
              </div>

              <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 dark:border-blue-900/60 dark:bg-blue-900/20 dark:text-blue-100">
                The current version stays live until this new draft is sent to the vendor.
              </div>
            </div>

            <div className="p-6 bg-gray-50 dark:bg-slate-700 rounded-b-2xl flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowRevisionModal(false);
                  setRevisionReason('');
                }}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-600"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateRevision}
                disabled={creatingRevision}
                className="px-6 py-2 bg-gradient-to-r from-purple-600 to-wedding-rose text-white rounded-lg font-medium hover:opacity-90 disabled:opacity-50"
              >
                {creatingRevision ? 'Creating...' : 'Create Draft'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function RoutedContractDetailPage() {
  const { token } = useAdmin();
  const router = useRouter();
  const params = useParams();

  return (
    <ContractDetailPageContent
      token={token}
      contractId={params.id as string}
      router={router}
    />
  );
}

export default function ContractDetailPage({ runtimeOverrides }: ContractDetailPageProps = {}) {
  if (runtimeOverrides) {
    return <ContractDetailPageContent {...runtimeOverrides} />;
  }

  return <RoutedContractDetailPage />;
}
