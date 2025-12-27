'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';
import {
  getVendorDirectory,
  getContractTemplates,
  getContractTemplate,
  createContract,
  type VendorProfile,
  type ContractTemplate,
  type ContractSection,
  type VendorCategory,
  VENDOR_CATEGORIES,
  getCategoryLabel,
} from '@/services/vendorManagementApi';

// Placeholder definitions for auto-fill
const AVAILABLE_PLACEHOLDERS = [
  { key: '{{vendor_name}}', label: 'Vendor Business Name', category: 'vendor' },
  { key: '{{vendor_email}}', label: 'Vendor Email', category: 'vendor' },
  { key: '{{vendor_phone}}', label: 'Vendor Phone', category: 'vendor' },
  { key: '{{vendor_address}}', label: 'Vendor Address', category: 'vendor' },
  { key: '{{couple_names}}', label: 'Couple Names', category: 'wedding' },
  { key: '{{wedding_date}}', label: 'Wedding Date', category: 'wedding' },
  { key: '{{wedding_venue}}', label: 'Wedding Venue', category: 'wedding' },
  { key: '{{total_amount}}', label: 'Total Contract Amount', category: 'contract' },
  { key: '{{deposit_amount}}', label: 'Deposit Amount', category: 'contract' },
  { key: '{{service_category}}', label: 'Service Category', category: 'vendor' },
  { key: '{{planner_name}}', label: 'Planner Name', category: 'planner' },
  { key: '{{planner_email}}', label: 'Planner Email', category: 'planner' },
  { key: '{{planner_company}}', label: 'Planner Company', category: 'planner' },
  { key: '{{contract_date}}', label: 'Contract Date', category: 'system' },
  { key: '{{contract_number}}', label: 'Contract Number', category: 'system' },
];

type Step = 'select-vendor' | 'select-template' | 'customize' | 'review';

interface ContractDraft {
  vendorId: string;
  vendor?: VendorProfile;
  templateId?: string;
  template?: ContractTemplate;
  weddingId: string;
  sections: ContractSection[];
  termsAndConditions: string;
  cancellationPolicy: string;
  customClauses: string;
  totalAmount: number;
  depositPercentage: number;
  serviceDate: string;
  serviceLocation: string;
}

interface Wedding {
  _id: string;
  couple_names?: string;
  partner1_name?: string;
  date: string;
}

export default function ContractCanvasPage() {
  const { token, userProfile } = useAdmin();
  const router = useRouter();
  const searchParams = useSearchParams();

  // URL params for pre-selection
  const preSelectedVendorId = searchParams.get('vendor_id');
  const preSelectedWeddingId = searchParams.get('wedding_id');

  // State
  const [currentStep, setCurrentStep] = useState<Step>('select-vendor');
  const [loading, setLoading] = useState(false);
  const [vendors, setVendors] = useState<VendorProfile[]>([]);
  const [templates, setTemplates] = useState<ContractTemplate[]>([]);
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [vendorSearch, setVendorSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');

  // Contract draft state
  const [draft, setDraft] = useState<ContractDraft>({
    vendorId: preSelectedVendorId || '',
    weddingId: preSelectedWeddingId || '',
    sections: [],
    termsAndConditions: '',
    cancellationPolicy: '',
    customClauses: '',
    totalAmount: 0,
    depositPercentage: 50,
    serviceDate: '',
    serviceLocation: '',
  });

  // Editor state
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [showPlaceholders, setShowPlaceholders] = useState(false);
  const [previewMode, setPreviewMode] = useState(false);

  // Fetch vendors
  useEffect(() => {
    async function fetchVendors() {
      if (!token) return;
      try {
        const data = await getVendorDirectory(token, {
          search: vendorSearch || undefined,
          category: categoryFilter || undefined,
        });
        setVendors(data);
      } catch (error) {
        console.error('Error fetching vendors:', error);
      }
    }
    fetchVendors();
  }, [token, vendorSearch, categoryFilter]);

  // Fetch weddings
  useEffect(() => {
    async function fetchWeddings() {
      if (!token) return;
      try {
        const { getApiBaseUrl } = await import('@/utils/env');
        const API_BASE = getApiBaseUrl();
        const response = await fetch(`${API_BASE}/admin/weddings`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          // Backend returns list directly, not wrapped in {weddings: [...]}
          setWeddings(Array.isArray(data) ? data : data.weddings || []);
        }
      } catch (error) {
        console.error('Error fetching weddings:', error);
      }
    }
    fetchWeddings();
  }, [token]);

  // Fetch templates when vendor is selected
  useEffect(() => {
    async function fetchTemplates() {
      if (!token || !draft.vendor) return;
      try {
        const data = await getContractTemplates(token, draft.vendor.service_category);
        setTemplates(data);
      } catch (error) {
        console.error('Error fetching templates:', error);
      }
    }
    if (draft.vendor) {
      fetchTemplates();
    }
  }, [token, draft.vendor]);

  // Pre-select vendor from URL
  useEffect(() => {
    if (preSelectedVendorId && vendors.length > 0 && !draft.vendor) {
      const vendor = vendors.find((v) => v._id === preSelectedVendorId);
      if (vendor) {
        setDraft((prev) => ({ ...prev, vendorId: vendor._id, vendor }));
        setCurrentStep('select-template');
      }
    }
  }, [preSelectedVendorId, vendors, draft.vendor]);

  // Handle vendor selection
  const handleSelectVendor = (vendor: VendorProfile) => {
    setDraft((prev) => ({
      ...prev,
      vendorId: vendor._id,
      vendor,
    }));
    setCurrentStep('select-template');
  };

  // Handle template selection
  const handleSelectTemplate = async (template: ContractTemplate | null) => {
    if (template) {
      // Load full template details
      try {
        const fullTemplate = await getContractTemplate(token!, template._id);
        setDraft((prev) => ({
          ...prev,
          templateId: template._id,
          template: fullTemplate,
          sections: fullTemplate.sections.map((s, i) => ({
            id: s.id || `section-${i}`,
            title: s.title,
            content: s.content,
            order: s.order ?? i,
          })),
          termsAndConditions: fullTemplate.terms_and_conditions || '',
          cancellationPolicy: fullTemplate.cancellation_policy || '',
          depositPercentage: fullTemplate.default_deposit_percentage || 50,
        }));
      } catch (error) {
        toast.error('Failed to load template');
        return;
      }
    } else {
      // Start from scratch
      setDraft((prev) => ({
        ...prev,
        templateId: undefined,
        template: undefined,
        sections: [
          {
            id: 'section-1',
            title: 'Parties',
            content: `This Agreement is entered into as of {{contract_date}}

BETWEEN:

**Service Provider:**
{{vendor_name}}
{{vendor_address}}
Email: {{vendor_email}}
Phone: {{vendor_phone}}

AND

**Client:**
{{couple_names}}
Planning Contact: {{planner_name}} ({{planner_email}})
Company: {{planner_company}}

Contract Reference: {{contract_number}}`,
            order: 0,
          },
          {
            id: 'section-2',
            title: 'Event Details',
            content: `**Event Date:** {{wedding_date}}
**Venue:** {{wedding_venue}}
**Service Type:** {{service_category}}`,
            order: 1,
          },
          {
            id: 'section-3',
            title: 'Services & Deliverables',
            content: `[Describe the services to be provided]`,
            order: 2,
          },
          {
            id: 'section-4',
            title: 'Investment & Payment',
            content: '**Total Investment:** $' + '{{total_amount}}' + '\n\n**Payment Schedule:**\n- Deposit: $' + '{{deposit_amount}}' + ' due upon signing\n- Balance: Due before the event date',
            order: 3,
          },
        ],
        termsAndConditions: '',
        cancellationPolicy: '',
      }));
    }
    setCurrentStep('customize');
    setActiveSection(null);
  };

  // Add new section
  const handleAddSection = () => {
    const newSection: ContractSection = {
      id: `section-${Date.now()}`,
      title: 'New Section',
      content: '',
      order: draft.sections.length,
    };
    setDraft((prev) => ({
      ...prev,
      sections: [...prev.sections, newSection],
    }));
    setActiveSection(newSection.id);
  };

  // Update section
  const handleUpdateSection = (sectionId: string, field: 'title' | 'content', value: string) => {
    setDraft((prev) => ({
      ...prev,
      sections: prev.sections.map((s) =>
        s.id === sectionId ? { ...s, [field]: value } : s
      ),
    }));
  };

  // Delete section
  const handleDeleteSection = (sectionId: string) => {
    setDraft((prev) => ({
      ...prev,
      sections: prev.sections.filter((s) => s.id !== sectionId),
    }));
    if (activeSection === sectionId) {
      setActiveSection(null);
    }
  };

  // Move section
  const handleMoveSection = (sectionId: string, direction: 'up' | 'down') => {
    setDraft((prev) => {
      const sections = [...prev.sections];
      const index = sections.findIndex((s) => s.id === sectionId);
      if (
        (direction === 'up' && index === 0) ||
        (direction === 'down' && index === sections.length - 1)
      ) {
        return prev;
      }
      const newIndex = direction === 'up' ? index - 1 : index + 1;
      [sections[index], sections[newIndex]] = [sections[newIndex], sections[index]];
      return { ...prev, sections: sections.map((s, i) => ({ ...s, order: i })) };
    });
  };

  // Insert placeholder at cursor
  const insertPlaceholder = (placeholder: string) => {
    if (!activeSection) return;

    const textarea = document.querySelector(
      `textarea[data-section-id="${activeSection}"]`
    ) as HTMLTextAreaElement;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const content = draft.sections.find((s) => s.id === activeSection)?.content || '';
    const newContent = content.substring(0, start) + placeholder + content.substring(end);

    handleUpdateSection(activeSection, 'content', newContent);
    setShowPlaceholders(false);

    // Refocus and set cursor position
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + placeholder.length, start + placeholder.length);
    }, 0);
  };

  // Preview with placeholders replaced
  const getPreviewContent = (content: string): string => {
    let preview = content;

    // Replace with sample data for preview
    const sampleData: Record<string, string> = {
      '{{vendor_name}}': draft.vendor?.business_name || 'Vendor Name',
      '{{vendor_email}}': draft.vendor?.email || 'vendor@example.com',
      '{{vendor_phone}}': draft.vendor?.phone || '(555) 123-4567',
      '{{vendor_address}}': draft.vendor?.address || 'Vendor Address',
      '{{couple_names}}': 'Sarah & Michael',
      '{{wedding_date}}': draft.serviceDate || 'TBD',
      '{{wedding_venue}}': draft.serviceLocation || 'Wedding Venue',
      '{{service_category}}': draft.vendor ? getCategoryLabel(draft.vendor.service_category) : 'Service',
      '{{total_amount}}': draft.totalAmount.toLocaleString(),
      '{{deposit_amount}}': ((draft.totalAmount * draft.depositPercentage) / 100).toLocaleString(),
      '{{planner_name}}': `${userProfile?.first_name || ''} ${userProfile?.last_name || ''}`.trim() || 'Planner Name',
      '{{planner_email}}': userProfile?.email || 'planner@example.com',
      '{{planner_company}}': (userProfile?.user_data?.company_name as string) || 'Planning Company',
      '{{contract_date}}': new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }),
      '{{contract_number}}': 'CON-PREVIEW-001',
    };

    Object.entries(sampleData).forEach(([placeholder, value]) => {
      preview = preview.replace(new RegExp(placeholder.replace(/[{}]/g, '\\$&'), 'g'), value);
    });

    return preview;
  };

  // Create contract
  const handleCreateContract = async () => {
    if (!token || !draft.vendorId || !draft.weddingId) {
      toast.error('Please select a vendor and wedding');
      return;
    }

    if (draft.totalAmount <= 0) {
      toast.error('Please enter a valid total amount');
      return;
    }

    setLoading(true);
    try {
      const contract = await createContract(token, {
        wedding_id: draft.weddingId,
        vendor_profile_id: draft.vendorId,
        total_amount: draft.totalAmount,
        template_id: draft.templateId,
        deposit_percentage: draft.depositPercentage,
        service_date: draft.serviceDate || undefined,
        service_location: draft.serviceLocation || undefined,
        custom_sections: draft.sections,
      });

      toast.success('Contract created successfully!');
      router.push(`/admin/vendors/contracts/${contract._id}`);
    } catch (error) {
      toast.error('Failed to create contract');
      console.error('Error creating contract:', error);
    } finally {
      setLoading(false);
    }
  };

  // Step navigation
  const getStepNumber = (step: Step): number => {
    const steps: Step[] = ['select-vendor', 'select-template', 'customize', 'review'];
    return steps.indexOf(step) + 1;
  };

  const steps = [
    { id: 'select-vendor' as Step, label: 'Select Vendor' },
    { id: 'select-template' as Step, label: 'Choose Template' },
    { id: 'customize' as Step, label: 'Customize Contract' },
    { id: 'review' as Step, label: 'Review & Create' },
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      {/* Header */}
      <div className="bg-white dark:bg-slate-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.back()}
                className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
              </button>
              <div>
                <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Contract Canvas</h1>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Create professional vendor contracts with ease
                </p>
              </div>
            </div>

            {/* Step indicator */}
            <div className="hidden md:flex items-center gap-2">
              {steps.map((step, index) => (
                <React.Fragment key={step.id}>
                  <div
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                      currentStep === step.id
                        ? 'bg-wedding-rose text-white'
                        : getStepNumber(currentStep) > getStepNumber(step.id)
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                    }`}
                  >
                    <span className="w-5 h-5 rounded-full bg-current/20 flex items-center justify-center text-xs">
                      {getStepNumber(currentStep) > getStepNumber(step.id) ? '✓' : index + 1}
                    </span>
                    <span className="hidden lg:inline">{step.label}</span>
                  </div>
                  {index < steps.length - 1 && (
                    <div className="w-8 h-px bg-gray-300 dark:bg-gray-600" />
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Step 1: Select Vendor */}
        {currentStep === 'select-vendor' && (
          <div className="space-y-6">
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
                Who is this contract for?
              </h2>
              <p className="text-gray-600 dark:text-gray-400 mb-6">
                Select a vendor from your directory or add a new one.
              </p>

              {/* Wedding selector */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  For Wedding
                </label>
                <select
                  value={draft.weddingId}
                  onChange={(e) => setDraft((prev) => ({ ...prev, weddingId: e.target.value }))}
                  className="w-full md:w-96 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                >
                  <option value="">Select a wedding</option>
                  {weddings?.map((wedding) => (
                    <option key={wedding._id} value={wedding._id}>
                      {wedding.couple_names || wedding.partner1_name} - {new Date(wedding.date).toLocaleDateString()}
                    </option>
                  ))}
                </select>
              </div>

              {/* Search and filter */}
              <div className="flex flex-col sm:flex-row gap-4 mb-6">
                <div className="flex-1">
                  <input
                    type="text"
                    placeholder="Search vendors..."
                    value={vendorSearch}
                    onChange={(e) => setVendorSearch(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  />
                </div>
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                >
                  <option value="">All Categories</option>
                  {VENDOR_CATEGORIES.map((cat) => (
                    <option key={cat.value} value={cat.value}>
                      {cat.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Vendor grid */}
              {vendors.length === 0 ? (
                <div className="text-center py-12 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl">
                  <svg className="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                  <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No vendors found</h3>
                  <p className="text-gray-500 dark:text-gray-400 mb-4">
                    Add vendors to your directory first, or adjust your search.
                  </p>
                  <button
                    onClick={() => router.push('/admin/vendors?action=add')}
                    className="px-4 py-2 bg-wedding-rose text-white rounded-lg font-medium hover:bg-wedding-rose/90"
                  >
                    Add Vendor
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {vendors.map((vendor) => (
                    <button
                      key={vendor._id}
                      onClick={() => handleSelectVendor(vendor)}
                      className={`text-left p-4 border-2 rounded-xl transition-all hover:shadow-lg ${
                        draft.vendorId === vendor._id
                          ? 'border-wedding-rose bg-wedding-rose/5'
                          : 'border-gray-200 dark:border-gray-700 hover:border-wedding-rose/50'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className="w-12 h-12 bg-gradient-to-br from-wedding-rose to-wedding-gold rounded-lg flex items-center justify-center text-white font-bold shrink-0">
                          {vendor.business_name.charAt(0)}
                        </div>
                        <div className="min-w-0">
                          <div className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                            <span className="truncate">{vendor.business_name}</span>
                            {vendor.is_preferred && (
                              <svg className="w-4 h-4 text-yellow-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                              </svg>
                            )}
                          </div>
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            {getCategoryLabel(vendor.service_category)}
                          </div>
                          <div className="text-sm text-gray-500 dark:text-gray-400 truncate">
                            {vendor.email}
                          </div>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Step 2: Select Template */}
        {currentStep === 'select-template' && (
          <div className="space-y-6">
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    Choose a Template
                  </h2>
                  <p className="text-gray-600 dark:text-gray-400">
                    Start with a template or create from scratch for {draft.vendor?.business_name}
                  </p>
                </div>
                <button
                  onClick={() => setCurrentStep('select-vendor')}
                  className="text-sm text-wedding-rose hover:text-wedding-rose/80"
                >
                  Change Vendor
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Blank template option */}
                <button
                  onClick={() => handleSelectTemplate(null)}
                  className="text-left p-6 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl hover:border-wedding-rose hover:bg-wedding-rose/5 transition-all group"
                >
                  <div className="w-12 h-12 bg-gray-100 dark:bg-gray-700 rounded-lg flex items-center justify-center mb-4 group-hover:bg-wedding-rose/10">
                    <svg className="w-6 h-6 text-gray-400 group-hover:text-wedding-rose" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                  </div>
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">
                    Start from Scratch
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Create a custom contract with your own sections
                  </p>
                </button>

                {/* Template options */}
                {templates.map((template) => (
                  <button
                    key={template._id}
                    onClick={() => handleSelectTemplate(template)}
                    className="text-left p-6 border-2 border-gray-200 dark:border-gray-700 rounded-xl hover:border-wedding-rose hover:shadow-lg transition-all"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-wedding-rose rounded-lg flex items-center justify-center">
                        <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      {template.is_system_template && (
                        <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 rounded-full">
                          System
                        </span>
                      )}
                    </div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">
                      {template.name}
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2">
                      {template.description || `Template for ${getCategoryLabel(template.service_category)} services`}
                    </p>
                    <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
                      <span>{template.sections.length} sections</span>
                      <span>•</span>
                      <span>Used {template.usage_count} times</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Customize Contract */}
        {currentStep === 'customize' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left sidebar - Section list */}
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-4 h-fit sticky top-24">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-900 dark:text-gray-100">Sections</h3>
                <button
                  onClick={handleAddSection}
                  className="p-1.5 text-wedding-rose hover:bg-wedding-rose/10 rounded-lg transition-colors"
                  title="Add section"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                </button>
              </div>

              <div className="space-y-2">
                {draft.sections.map((section, index) => (
                  <div
                    key={section.id}
                    className={`group flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors ${
                      activeSection === section.id
                        ? 'bg-wedding-rose/10 border border-wedding-rose'
                        : 'hover:bg-gray-100 dark:hover:bg-slate-700 border border-transparent'
                    }`}
                    onClick={() => setActiveSection(section.id)}
                  >
                    <div className="flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleMoveSection(section.id, 'up'); }}
                        disabled={index === 0}
                        className="p-0.5 hover:text-wedding-rose disabled:opacity-30"
                      >
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                        </svg>
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleMoveSection(section.id, 'down'); }}
                        disabled={index === draft.sections.length - 1}
                        className="p-0.5 hover:text-wedding-rose disabled:opacity-30"
                      >
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>
                    </div>
                    <span className="flex-1 text-sm font-medium text-gray-700 dark:text-gray-300 truncate">
                      {section.title}
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteSection(section.id); }}
                      className="p-1 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-all"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>

              {/* Additional sections */}
              <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
                <button
                  onClick={() => setActiveSection('terms')}
                  className={`w-full text-left p-2 rounded-lg text-sm transition-colors ${
                    activeSection === 'terms'
                      ? 'bg-wedding-rose/10 text-wedding-rose'
                      : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-slate-700'
                  }`}
                >
                  Terms & Conditions
                </button>
                <button
                  onClick={() => setActiveSection('cancellation')}
                  className={`w-full text-left p-2 rounded-lg text-sm transition-colors ${
                    activeSection === 'cancellation'
                      ? 'bg-wedding-rose/10 text-wedding-rose'
                      : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-slate-700'
                  }`}
                >
                  Cancellation Policy
                </button>
              </div>
            </div>

            {/* Main editor area */}
            <div className="lg:col-span-2 space-y-6">
              {/* Contract details */}
              <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
                <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Contract Details</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Total Amount ($)
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={draft.totalAmount || ''}
                      onChange={(e) => setDraft((prev) => ({ ...prev, totalAmount: parseFloat(e.target.value) || 0 }))}
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                      placeholder="0.00"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Deposit ({draft.depositPercentage}%)
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={draft.depositPercentage}
                      onChange={(e) => setDraft((prev) => ({ ...prev, depositPercentage: parseInt(e.target.value) }))}
                      className="w-full"
                    />
                    <div className="text-sm text-gray-500 mt-1">
                      ${((draft.totalAmount * draft.depositPercentage) / 100).toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Service Date
                    </label>
                    <input
                      type="date"
                      value={draft.serviceDate}
                      onChange={(e) => setDraft((prev) => ({ ...prev, serviceDate: e.target.value }))}
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Service Location
                    </label>
                    <input
                      type="text"
                      value={draft.serviceLocation}
                      onChange={(e) => setDraft((prev) => ({ ...prev, serviceLocation: e.target.value }))}
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                      placeholder="Venue name or address"
                    />
                  </div>
                </div>
              </div>

              {/* Section editor */}
              <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                    {activeSection === 'terms'
                      ? 'Terms & Conditions'
                      : activeSection === 'cancellation'
                      ? 'Cancellation Policy'
                      : draft.sections.find((s) => s.id === activeSection)?.title || 'Select a section'}
                  </h3>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowPlaceholders(!showPlaceholders)}
                      className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                        showPlaceholders
                          ? 'bg-wedding-rose text-white'
                          : 'bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200'
                      }`}
                    >
                      {'{{'} Placeholders {'}}'}
                    </button>
                    <button
                      onClick={() => setPreviewMode(!previewMode)}
                      className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                        previewMode
                          ? 'bg-green-600 text-white'
                          : 'bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200'
                      }`}
                    >
                      {previewMode ? 'Edit' : 'Preview'}
                    </button>
                  </div>
                </div>

                {/* Placeholder panel */}
                {showPlaceholders && (
                  <div className="mb-4 p-4 bg-gray-50 dark:bg-slate-700 rounded-lg">
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                      Click a placeholder to insert it at cursor position:
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {AVAILABLE_PLACEHOLDERS.map((p) => (
                        <button
                          key={p.key}
                          onClick={() => insertPlaceholder(p.key)}
                          className="px-2 py-1 text-xs bg-white dark:bg-slate-600 border border-gray-200 dark:border-gray-500 rounded hover:border-wedding-rose hover:text-wedding-rose transition-colors"
                          title={p.label}
                        >
                          {p.key}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Editor content */}
                {activeSection && activeSection !== 'terms' && activeSection !== 'cancellation' && (
                  <>
                    {/* Section title */}
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Section Title
                      </label>
                      <input
                        type="text"
                        value={draft.sections.find((s) => s.id === activeSection)?.title || ''}
                        onChange={(e) => handleUpdateSection(activeSection, 'title', e.target.value)}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                      />
                    </div>

                    {/* Section content */}
                    {previewMode ? (
                      <div className="prose dark:prose-invert max-w-none p-4 bg-gray-50 dark:bg-slate-700 rounded-lg min-h-[200px] whitespace-pre-wrap">
                        {getPreviewContent(draft.sections.find((s) => s.id === activeSection)?.content || '')}
                      </div>
                    ) : (
                      <textarea
                        data-section-id={activeSection}
                        value={draft.sections.find((s) => s.id === activeSection)?.content || ''}
                        onChange={(e) => handleUpdateSection(activeSection, 'content', e.target.value)}
                        rows={12}
                        className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 font-mono text-sm resize-y"
                        placeholder="Enter section content... Use {{placeholders}} for auto-fill data."
                      />
                    )}
                  </>
                )}

                {activeSection === 'terms' && (
                  previewMode ? (
                    <div className="prose dark:prose-invert max-w-none p-4 bg-gray-50 dark:bg-slate-700 rounded-lg min-h-[200px] whitespace-pre-wrap">
                      {getPreviewContent(draft.termsAndConditions)}
                    </div>
                  ) : (
                    <textarea
                      value={draft.termsAndConditions}
                      onChange={(e) => setDraft((prev) => ({ ...prev, termsAndConditions: e.target.value }))}
                      rows={12}
                      className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 font-mono text-sm resize-y"
                      placeholder="Enter terms and conditions..."
                    />
                  )
                )}

                {activeSection === 'cancellation' && (
                  previewMode ? (
                    <div className="prose dark:prose-invert max-w-none p-4 bg-gray-50 dark:bg-slate-700 rounded-lg min-h-[200px] whitespace-pre-wrap">
                      {getPreviewContent(draft.cancellationPolicy)}
                    </div>
                  ) : (
                    <textarea
                      value={draft.cancellationPolicy}
                      onChange={(e) => setDraft((prev) => ({ ...prev, cancellationPolicy: e.target.value }))}
                      rows={12}
                      className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 font-mono text-sm resize-y"
                      placeholder="Enter cancellation policy..."
                    />
                  )
                )}

                {!activeSection && (
                  <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                    <svg className="w-12 h-12 mx-auto mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    <p>Select a section from the left to start editing</p>
                  </div>
                )}
              </div>

              {/* Navigation buttons */}
              <div className="flex items-center justify-between">
                <button
                  onClick={() => setCurrentStep('select-template')}
                  className="px-6 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700"
                >
                  Back to Templates
                </button>
                <button
                  onClick={() => setCurrentStep('review')}
                  className="px-6 py-2 bg-wedding-rose text-white rounded-lg font-medium hover:bg-wedding-rose/90"
                >
                  Review Contract
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Review & Create */}
        {currentStep === 'review' && (
          <div className="space-y-6">
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl overflow-hidden">
              {/* Header */}
              <div className="bg-gradient-to-r from-wedding-navy via-purple-900 to-wedding-gold p-6 text-white">
                <h2 className="text-2xl font-bold mb-1">Review Your Contract</h2>
                <p className="text-blue-100">
                  Please review all details before creating the contract
                </p>
              </div>

              <div className="p-6">
                {/* Summary cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                  <div className="p-4 bg-gray-50 dark:bg-slate-700 rounded-xl">
                    <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">Vendor</div>
                    <div className="font-semibold text-gray-900 dark:text-gray-100">
                      {draft.vendor?.business_name}
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      {draft.vendor && getCategoryLabel(draft.vendor.service_category)}
                    </div>
                  </div>
                  <div className="p-4 bg-gray-50 dark:bg-slate-700 rounded-xl">
                    <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">Total Amount</div>
                    <div className="font-semibold text-gray-900 dark:text-gray-100 text-2xl">
                      ${draft.totalAmount.toLocaleString()}
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      Deposit: ${((draft.totalAmount * draft.depositPercentage) / 100).toLocaleString()} ({draft.depositPercentage}%)
                    </div>
                  </div>
                  <div className="p-4 bg-gray-50 dark:bg-slate-700 rounded-xl">
                    <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">Service Date</div>
                    <div className="font-semibold text-gray-900 dark:text-gray-100">
                      {draft.serviceDate ? new Date(draft.serviceDate).toLocaleDateString() : 'Not set'}
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400 truncate">
                      {draft.serviceLocation || 'Location not set'}
                    </div>
                  </div>
                </div>

                {/* Contract preview */}
                <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
                  <div className="bg-gray-100 dark:bg-slate-700 px-4 py-2 border-b border-gray-200 dark:border-gray-600">
                    <span className="font-medium text-gray-700 dark:text-gray-300">Contract Preview</span>
                  </div>
                  <div className="p-6 max-h-[500px] overflow-y-auto">
                    <div className="prose dark:prose-invert max-w-none">
                      {draft.sections.map((section) => (
                        <div key={section.id} className="mb-8">
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2 pb-2 border-b">
                            {section.title}
                          </h3>
                          <div className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                            {getPreviewContent(section.content)}
                          </div>
                        </div>
                      ))}

                      {draft.termsAndConditions && (
                        <div className="mb-8">
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2 pb-2 border-b">
                            Terms & Conditions
                          </h3>
                          <div className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                            {getPreviewContent(draft.termsAndConditions)}
                          </div>
                        </div>
                      )}

                      {draft.cancellationPolicy && (
                        <div className="mb-8">
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2 pb-2 border-b">
                            Cancellation Policy
                          </h3>
                          <div className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                            {getPreviewContent(draft.cancellationPolicy)}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex items-center justify-between">
              <button
                onClick={() => setCurrentStep('customize')}
                className="px-6 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700"
              >
                Back to Edit
              </button>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => router.push('/admin/vendors')}
                  className="px-6 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateContract}
                  disabled={loading || draft.totalAmount <= 0}
                  className="px-8 py-2 bg-gradient-to-r from-purple-600 to-wedding-rose text-white rounded-lg font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {loading ? (
                    <>
                      <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Creating...
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Create Contract
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
