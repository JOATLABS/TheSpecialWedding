'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';
import { getApiBaseUrl } from '@/utils/env';
import { formatAdminDate, formatDate, DEFAULT_TIMEZONE } from '@/utils/dateFormat';
import ContractMarkdownRenderer from '@/components/contracts/ContractMarkdownRenderer';
import VendorContractPreview from '@/components/contracts/VendorContractPreview';
import {
  getVendorDirectory,
  type VendorProfile,
  type VendorCategory,
  VENDOR_CATEGORIES,
  getCategoryLabel,
} from '@/services/vendorManagementApi';
import {
  getContractTemplates,
  getContractTemplate,
  createContract,
  updateContract,
  type ContractTemplate,
  type ContractSection,
} from '@/services/vendorContractsApi';

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
type ActiveDocumentTarget = string | 'terms' | 'cancellation' | 'custom-clauses';

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
  partner2_name?: string;
  date: string;
  venue?: string;
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

  // AI Generation state
  const [aiModalOpen, setAiModalOpen] = useState(false);
  const [aiSectionType, setAiSectionType] = useState<string>('');
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiGeneratedContent, setAiGeneratedContent] = useState('');

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
    // Validate wedding is selected BEFORE advancing — the wedding selector
    // lives on this step but is visually disconnected from the vendor
    // grid. Without this check, planners could pick a vendor without a
    // wedding, sail through Template / Customize / Review, and only
    // discover the missing wedding when the final create button rejects
    // with "Please select a vendor and wedding" (handleCreateContract:506).
    // By that point the wedding selector is no longer visible and the
    // error reads as a vendor problem.
    if (!draft.weddingId) {
      toast.error('Pick a wedding first — the dropdown is at the top of this step.');
      return;
    }
    setDraft((prev) => ({
      ...prev,
      vendorId: vendor._id,
      vendor,
    }));
    setCurrentStep('select-template');
  };

  // Handle template selection
  const handleSelectTemplate = async (template: ContractTemplate | null) => {
    let nextActiveSection: ActiveDocumentTarget = 'section-1';

    if (template) {
      // Load full template details
      try {
        const fullTemplate = await getContractTemplate(token!, template._id);
        nextActiveSection = fullTemplate.sections[0]?.id || 'terms';
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
        customClauses: '',
      }));
      nextActiveSection = 'section-1';
    }
    setCurrentStep('customize');
    setActiveSection(nextActiveSection);
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
    const remainingSections = draft.sections.filter((s) => s.id !== sectionId);
    setDraft((prev) => ({
      ...prev,
      sections: remainingSections,
    }));
    if (activeSection === sectionId) {
      setActiveSection(remainingSections[0]?.id || 'terms');
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
      `textarea[data-editor-target="${activeSection}"]`
    ) as HTMLTextAreaElement;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    let content = '';
    if (activeSection === 'terms') {
      content = draft.termsAndConditions;
    } else if (activeSection === 'cancellation') {
      content = draft.cancellationPolicy;
    } else if (activeSection === 'custom-clauses') {
      content = draft.customClauses;
    } else {
      content = draft.sections.find((s) => s.id === activeSection)?.content || '';
    }
    const newContent = content.substring(0, start) + placeholder + content.substring(end);

    if (activeSection === 'terms') {
      setDraft((prev) => ({ ...prev, termsAndConditions: newContent }));
    } else if (activeSection === 'cancellation') {
      setDraft((prev) => ({ ...prev, cancellationPolicy: newContent }));
    } else if (activeSection === 'custom-clauses') {
      setDraft((prev) => ({ ...prev, customClauses: newContent }));
    } else {
      handleUpdateSection(activeSection, 'content', newContent);
    }
    setShowPlaceholders(false);

    // Refocus and set cursor position
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + placeholder.length, start + placeholder.length);
    }, 0);
  };

  // AI section generation
  const openAiModal = (sectionType: string) => {
    // Set default prompts based on section type
    const defaultPrompts: Record<string, string> = {
      payment_terms: `Generate payment terms for a ${draft.vendor?.service_category || 'wedding vendor'} contract.`,
      cancellation_policy: `Generate a cancellation policy for a ${draft.vendor?.service_category || 'wedding vendor'} contract.`,
      scope_of_work: `Generate a scope of work for ${draft.vendor?.business_name || 'a vendor'}.`,
      liability: `Generate a liability clause for a ${draft.vendor?.service_category || 'wedding vendor'} contract.`,
      custom: '',
    };

    setAiSectionType(sectionType);
    setAiPrompt(defaultPrompts[sectionType] || '');
    setAiGeneratedContent('');
    setAiModalOpen(true);
  };

  const handleAiGenerate = async () => {
    if (!token || !aiPrompt.trim()) return;

    setAiGenerating(true);
    try {
      const response = await fetch(`${getApiBaseUrl()}/admin/ai/generate-contract-section`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          section_type: aiSectionType,
          vendor_type: draft.vendor?.service_category || 'general',
          wedding_id: draft.weddingId || undefined,
          custom_prompt: aiPrompt,
        }),
      });

      if (response.status === 402) {
        toast.error('Insufficient AI credits');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to generate content');
      }

      const data = await response.json();
      setAiGeneratedContent(data.content || '');
      toast.success(`Generated! Used ${data.credits_used} credit(s)`);
    } catch {
      toast.error('Failed to generate content');
    } finally {
      setAiGenerating(false);
    }
  };

  const applyAiContent = () => {
    if (!aiGeneratedContent) return;

    if (activeSection === 'terms') {
      setDraft((prev) => ({ ...prev, termsAndConditions: aiGeneratedContent }));
    } else if (activeSection === 'cancellation') {
      setDraft((prev) => ({ ...prev, cancellationPolicy: aiGeneratedContent }));
    } else if (activeSection === 'custom-clauses') {
      setDraft((prev) => ({ ...prev, customClauses: aiGeneratedContent }));
    } else if (activeSection) {
      handleUpdateSection(activeSection, 'content', aiGeneratedContent);
    }

    setAiModalOpen(false);
    toast.success('Content applied!');
  };

  const getPreviewPlaceholderValues = (): Record<string, string> => ({
      ...(function () {
        const selectedWedding = weddings.find((wedding) => wedding._id === draft.weddingId);
        const resolvedCoupleNames =
          selectedWedding?.couple_names ||
          [selectedWedding?.partner1_name, selectedWedding?.partner2_name].filter(Boolean).join(' & ') ||
          'The Couple';

        return {
          '{{couple_names}}': resolvedCoupleNames,
          '{{wedding_date}}': selectedWedding?.date || draft.serviceDate || 'TBD',
          '{{wedding_venue}}': draft.serviceLocation || selectedWedding?.venue || 'Wedding Venue',
        };
      })(),
      '{{vendor_name}}': draft.vendor?.business_name || 'Vendor Name',
      '{{vendor_email}}': draft.vendor?.email || 'vendor@example.com',
      '{{vendor_phone}}': draft.vendor?.phone || '(555) 123-4567',
      '{{vendor_address}}': draft.vendor?.address || 'Vendor Address',
      '{{service_category}}': draft.vendor
        ? getCategoryLabel(draft.vendor.service_category, draft.vendor.custom_service_category)
        : 'Service',
      '{{total_amount}}': draft.totalAmount.toLocaleString(),
      '{{deposit_amount}}': ((draft.totalAmount * draft.depositPercentage) / 100).toLocaleString(),
      '{{planner_name}}': `${userProfile?.first_name || ''} ${userProfile?.last_name || ''}`.trim() || 'Planner Name',
      '{{planner_email}}': userProfile?.email || 'planner@example.com',
      '{{planner_company}}': (userProfile?.user_data?.company_name as string) || 'Planning Company',
      '{{contract_date}}': formatDate(new Date().toISOString(), { year: 'numeric', month: 'long', day: 'numeric' }, 'en-US', DEFAULT_TIMEZONE),
      '{{contract_number}}': 'CON-PREVIEW-001',
  });

  const buildResolvedDocument = (placeholderValues: Record<string, string>) => {
    const replacePlaceholders = (content: string) =>
      Object.entries(placeholderValues).reduce(
        (resolved, [placeholder, value]) => resolved.split(placeholder).join(value),
        content
      );

    return {
      sections: draft.sections.map((section) => ({
        ...section,
        content: replacePlaceholders(section.content),
      })),
      terms_and_conditions: replacePlaceholders(draft.termsAndConditions),
      cancellation_policy: replacePlaceholders(draft.cancellationPolicy),
      custom_clauses: replacePlaceholders(draft.customClauses),
    };
  };

  const getActiveDocumentTitle = (): string => {
    if (activeSection === 'terms') return 'Terms & Conditions';
    if (activeSection === 'cancellation') return 'Cancellation Policy';
    if (activeSection === 'custom-clauses') return 'Custom Clauses';
    return draft.sections.find((s) => s.id === activeSection)?.title || 'Select a section';
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
        template_id: draft.templateId || undefined,
        deposit_percentage: draft.depositPercentage,
        service_date: draft.serviceDate || undefined,
        service_location: draft.serviceLocation || undefined,
        custom_sections: draft.templateId ? [] : draft.sections,
      });

      const persistedDocument = buildResolvedDocument({
        ...getPreviewPlaceholderValues(),
        '{{contract_number}}': contract.contract_number || 'CONTRACT',
      });

      await updateContract(token, contract._id, persistedDocument);

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
                <h1 className="text-xl sm:text-2xl font-semibold leading-tight text-slate-900 dark:text-white">Contract Canvas</h1>
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
                      {wedding.couple_names || wedding.partner1_name} - {formatAdminDate(wedding.date)}
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
                            {getCategoryLabel(vendor.service_category, vendor.custom_service_category)}
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
                <button
                  onClick={() => setActiveSection('custom-clauses')}
                  className={`w-full text-left p-2 rounded-lg text-sm transition-colors ${
                    activeSection === 'custom-clauses'
                      ? 'bg-wedding-rose/10 text-wedding-rose'
                      : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-slate-700'
                  }`}
                >
                  Custom Clauses
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
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100">{getActiveDocumentTitle()}</h3>
                  <div className="flex items-center gap-2">
                    {/* AI Generate Button */}
                    {activeSection && (
                      <button
                        onClick={() => {
                          const sectionType = activeSection === 'terms' ? 'payment_terms' :
                            activeSection === 'cancellation' ? 'cancellation_policy' :
                            activeSection === 'custom-clauses' ? 'custom' :
                            draft.sections.find((s) => s.id === activeSection)?.title?.toLowerCase().includes('payment') ? 'payment_terms' :
                            draft.sections.find((s) => s.id === activeSection)?.title?.toLowerCase().includes('scope') ? 'scope_of_work' :
                            draft.sections.find((s) => s.id === activeSection)?.title?.toLowerCase().includes('liability') ? 'liability' :
                            'custom';
                          openAiModal(sectionType);
                        }}
                        className="px-3 py-1.5 text-sm rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-white hover:opacity-90 transition-opacity flex items-center gap-1.5"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        AI Generate
                      </button>
                    )}
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

                {activeSection ? (
                  <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-6">
                    <div className="space-y-4">
                      {activeSection !== 'terms' &&
                        activeSection !== 'cancellation' &&
                        activeSection !== 'custom-clauses' && (
                          <div>
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
                        )}

                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Markdown Source
                        </label>
                        {activeSection === 'terms' && (
                          <textarea
                            data-editor-target="terms"
                            value={draft.termsAndConditions}
                            onChange={(e) => setDraft((prev) => ({ ...prev, termsAndConditions: e.target.value }))}
                            rows={14}
                            className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 font-mono text-sm resize-y"
                            placeholder="Enter terms and conditions..."
                          />
                        )}
                        {activeSection === 'cancellation' && (
                          <textarea
                            data-editor-target="cancellation"
                            value={draft.cancellationPolicy}
                            onChange={(e) => setDraft((prev) => ({ ...prev, cancellationPolicy: e.target.value }))}
                            rows={14}
                            className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 font-mono text-sm resize-y"
                            placeholder="Enter cancellation policy..."
                          />
                        )}
                        {activeSection === 'custom-clauses' && (
                          <textarea
                            data-editor-target="custom-clauses"
                            value={draft.customClauses}
                            onChange={(e) => setDraft((prev) => ({ ...prev, customClauses: e.target.value }))}
                            rows={14}
                            className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 font-mono text-sm resize-y"
                            placeholder="Enter any custom clauses..."
                          />
                        )}
                        {activeSection !== 'terms' &&
                          activeSection !== 'cancellation' &&
                          activeSection !== 'custom-clauses' && (
                            <textarea
                              data-editor-target={activeSection}
                              value={draft.sections.find((s) => s.id === activeSection)?.content || ''}
                              onChange={(e) => handleUpdateSection(activeSection, 'content', e.target.value)}
                              rows={14}
                              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 font-mono text-sm resize-y"
                              placeholder="Enter section content... Use {{placeholders}} for auto-fill data."
                            />
                          )}
                      </div>
                    </div>

                    <div className="space-y-3">
                      <div>
                        <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Live Document Preview
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          This uses the same contract rendering path the vendor will see.
                        </p>
                      </div>
                      <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-slate-900/60 p-4 max-h-[720px] overflow-y-auto">
                        <VendorContractPreview
                          sections={draft.sections}
                          termsAndConditions={draft.termsAndConditions}
                          cancellationPolicy={draft.cancellationPolicy}
                          customClauses={draft.customClauses}
                          placeholderValues={getPreviewPlaceholderValues()}
                        />
                      </div>
                    </div>
                  </div>
                ) : (
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
              {/* Header — brand palette only. Previously used a
                  wedding-navy → purple-900 → wedding-gold gradient that
                  wasn't a platform token combination. Switched to the
                  wedding-rose → wedding-gold gradient used elsewhere in
                  planner CTAs. */}
              <div className="bg-gradient-to-r from-wedding-rose to-wedding-gold p-6 text-white">
                <h2 className="text-2xl font-bold mb-1">Review Your Contract</h2>
                <p className="text-white/80">
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
                      {draft.vendor && getCategoryLabel(draft.vendor.service_category, draft.vendor.custom_service_category)}
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
                      {draft.serviceDate ? formatAdminDate(draft.serviceDate) : 'Not set'}
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
                    <VendorContractPreview
                      sections={draft.sections}
                      termsAndConditions={draft.termsAndConditions}
                      cancellationPolicy={draft.cancellationPolicy}
                      customClauses={draft.customClauses}
                      placeholderValues={getPreviewPlaceholderValues()}
                    />
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
                  className="px-8 py-2 bg-wedding-rose hover:bg-wedding-gold text-white rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
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

      {/* AI Generation Modal */}
      {aiModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-indigo-500 to-purple-600">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">AI Content Generator</h3>
                    <p className="text-sm text-indigo-100">Generate professional contract content</p>
                  </div>
                </div>
                <button
                  onClick={() => setAiModalOpen(false)}
                  className="p-2 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              {/* Prompt Input */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  What would you like to generate?
                </label>
                <textarea
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  rows={3}
                  className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 resize-none"
                  placeholder="Describe what you want to generate..."
                />
              </div>

              {/* Section Type */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Section Type
                </label>
                <select
                  value={aiSectionType}
                  onChange={(e) => setAiSectionType(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                >
                  <option value="payment_terms">Payment Terms</option>
                  <option value="cancellation_policy">Cancellation Policy</option>
                  <option value="scope_of_work">Scope of Work</option>
                  <option value="liability">Liability Clause</option>
                  <option value="force_majeure">Force Majeure</option>
                  <option value="custom">Custom</option>
                </select>
              </div>

              {/* Generate Button */}
              <button
                onClick={handleAiGenerate}
                disabled={aiGenerating || !aiPrompt.trim()}
                className="w-full px-4 py-3 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg font-medium hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mb-4"
              >
                {aiGenerating ? (
                  <>
                    <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Generating...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    Generate (1 credit)
                  </>
                )}
              </button>

              {/* Generated Content Preview */}
              {aiGeneratedContent && (
                <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                  <div className="bg-gray-100 dark:bg-slate-700 px-4 py-2 border-b border-gray-200 dark:border-gray-600 flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Generated Content</span>
                    <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      Ready to apply
                    </span>
                  </div>
                  <div className="p-4 max-h-[200px] overflow-y-auto">
                    <ContractMarkdownRenderer content={aiGeneratedContent} className="text-sm" />
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-slate-800/50 flex items-center justify-end gap-3">
              <button
                onClick={() => setAiModalOpen(false)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={applyAiContent}
                disabled={!aiGeneratedContent}
                className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Apply to Section
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
