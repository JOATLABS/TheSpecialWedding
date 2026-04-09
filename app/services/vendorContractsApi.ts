/**
 * Vendor Contracts API Service
 *
 * Handles planner-to-vendor contract templates, contracts, milestones,
 * section editing, contract form data, and public vendor contract access.
 */

import { getApiBaseUrl } from '@/utils/env';
import type { VendorCategory } from '@/services/vendorManagementApi';

const API_BASE = getApiBaseUrl();

function extractErrorMessage(errBody: any, fallback: string): string {
  const detail = errBody?.detail;
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (typeof detail === 'object' && !Array.isArray(detail) && detail.message) return detail.message;
  if (Array.isArray(detail) && detail.length > 0 && detail[0].msg) {
    return detail.map((d: any) => d.msg).join('; ');
  }
  return fallback;
}

export interface ContractSection {
  id: string;
  title: string;
  content: string;
  order: number;
}

export interface Placeholder {
  key: string;
  label: string;
  source: string;
  field_path?: string;
}

export interface PaymentScheduleItem {
  percentage: number;
  description: string;
  days_before_event?: number;
}

export interface ContractTemplate {
  _id: string;
  name: string;
  description?: string;
  service_category: VendorCategory;
  sections: ContractSection[];
  terms_and_conditions?: string;
  cancellation_policy?: string;
  placeholders: Placeholder[];
  default_deposit_percentage?: number;
  default_payment_schedule: PaymentScheduleItem[];
  is_system_template: boolean;
  is_public: boolean;
  usage_count: number;
}

export type ContractStatus =
  | 'draft'
  | 'pending_review'
  | 'sent'
  | 'viewed'
  | 'signed'
  | 'active'
  | 'completed'
  | 'cancelled'
  | 'expired';

export interface VendorContract {
  _id: string;
  id?: string;
  wedding_id: string;
  vendor_profile_id?: string;
  vendor_name: string;
  vendor_email: string;
  vendor_phone?: string;
  service_category: VendorCategory;
  custom_service_category?: string;
  contract_title: string;
  contract_number?: string;
  sections: ContractSection[];
  terms_and_conditions?: string;
  cancellation_policy?: string;
  custom_clauses?: string;
  total_amount: number;
  currency: string;
  deposit_amount?: number;
  deposit_due_date?: string;
  status: ContractStatus;
  sent_at?: string;
  viewed_at?: string;
  signed_at?: string;
  signed_by_name?: string;
  service_date?: string;
  service_location?: string;
  form_data_applied?: boolean;
  form_submission_id?: string;
  form_submission_ids?: string[];
  form_data_mappings?: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface PaymentMilestone {
  _id: string;
  contract_id: string;
  wedding_id: string;
  description: string;
  amount: number;
  currency: string;
  due_date: string;
  status: 'pending' | 'due' | 'overdue' | 'paid' | 'partial';
  paid_amount: number;
  paid_at?: string;
  payment_method?: string;
  vendor_name: string;
  vendor_email: string;
}

export interface VendorContractFormSubmissionSummary {
  _id: string;
  form_name: string;
  submitted_at?: string;
  source: string;
  data: Record<string, unknown>;
}

export interface VendorContractAvailableField {
  value: unknown;
  source: string;
  source_id: string;
  original_key: string;
}

export interface VendorContractSuggestedField {
  value: unknown;
  source_field: string;
}

export interface VendorContractFormDataResponse {
  vendor_submissions: VendorContractFormSubmissionSummary[];
  available_fields: Record<string, VendorContractAvailableField>;
  suggested_contract_fields: Record<string, VendorContractSuggestedField>;
}

export interface PublicContract {
  _id: string;
  id?: string;
  contract_title: string;
  contract_number?: string;
  vendor_name: string;
  vendor_email: string;
  planner_name?: string;
  planner_company?: string;
  couple_names?: string;
  wedding_date?: string;
  service_date?: string;
  service_location?: string;
  service_category: VendorCategory;
  sections: ContractSection[];
  terms_and_conditions?: string;
  cancellation_policy?: string;
  total_amount: number;
  deposit_amount?: number;
  currency: string;
  status: ContractStatus;
  sent_at?: string;
  viewed_at?: string;
  signed_at?: string;
  signed_by_name?: string;
}

export interface CreateVendorContractTemplateRequest {
  name: string;
  description?: string;
  service_category: VendorCategory;
  sections: ContractSection[];
  terms_and_conditions?: string;
  cancellation_policy?: string;
  default_deposit_percentage?: number;
  default_payment_schedule?: PaymentScheduleItem[];
  is_public?: boolean;
}

export interface CreateVendorContractRequest {
  wedding_id: string;
  vendor_profile_id: string;
  total_amount: number;
  template_id?: string;
  quote_id?: string;
  deposit_percentage?: number;
  service_date?: string;
  service_location?: string;
  custom_sections?: ContractSection[];
}

export interface UpdateVendorContractRequest {
  contract_title?: string;
  total_amount?: number;
  deposit_amount?: number;
  deposit_due_date?: string;
  terms_and_conditions?: string;
  cancellation_policy?: string;
  custom_clauses?: string;
  service_date?: string;
  service_start_time?: string;
  service_end_time?: string;
  service_location?: string;
  internal_notes?: string;
  sections?: ContractSection[];
}

export interface UpdateVendorContractSectionsRequest {
  sections: ContractSection[];
  terms_and_conditions?: string;
  cancellation_policy?: string;
  custom_clauses?: string;
}

export interface ApplyVendorContractFormDataRequest {
  form_submission_id: string;
  field_mappings?: Record<string, string>;
}

export interface SendVendorContractRequest {
  message?: string;
  cc_emails?: string[];
}

export interface PaymentMilestoneInput {
  description: string;
  amount: number;
  due_date: string;
  percentage_of_total?: number;
  days_before_event?: number;
}

export interface CreateVendorPaymentMilestonesRequest {
  milestones: PaymentMilestoneInput[];
}

export interface RecordVendorMilestonePaymentRequest {
  amount: number;
  payment_method: string;
  payment_date?: string;
  notes?: string;
  receipt_url?: string;
}

export async function getContractTemplates(
  token: string,
  category?: string
): Promise<ContractTemplate[]> {
  const url = category
    ? `${API_BASE}/admin/templates?category=${category}`
    : `${API_BASE}/admin/templates`;

  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(err, 'Failed to fetch contract templates'));
  }

  return response.json();
}

export async function getContractTemplate(
  token: string,
  templateId: string
): Promise<ContractTemplate> {
  const response = await fetch(`${API_BASE}/admin/templates/${templateId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to fetch template'));
  }

  return response.json();
}

export async function createContractTemplate(
  token: string,
  data: CreateVendorContractTemplateRequest
): Promise<ContractTemplate> {
  const response = await fetch(`${API_BASE}/admin/templates`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to create template'));
  }

  return response.json();
}

export async function createContract(
  token: string,
  data: CreateVendorContractRequest
): Promise<VendorContract> {
  const response = await fetch(`${API_BASE}/admin/contracts`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to create contract'));
  }

  return response.json();
}

export async function getContracts(
  token: string,
  params?: {
    wedding_id?: string;
    vendor_profile_id?: string;
    status?: ContractStatus;
  }
): Promise<VendorContract[]> {
  const queryParams = new URLSearchParams();
  if (params?.wedding_id) queryParams.append('wedding_id', params.wedding_id);
  if (params?.vendor_profile_id) queryParams.append('vendor_profile_id', params.vendor_profile_id);
  if (params?.status) queryParams.append('status', params.status);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/admin/contracts?${queryParams.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error('Contracts endpoint is not available. The backend endpoint may not be set up yet.');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to fetch contracts'));
  }

  return response.json();
}

export async function getContract(
  token: string,
  contractId: string
): Promise<VendorContract> {
  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to fetch contract'));
  }

  return response.json();
}

export async function updateContract(
  token: string,
  contractId: string,
  data: UpdateVendorContractRequest
): Promise<VendorContract> {
  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to update contract'));
  }

  return response.json();
}

export async function sendContract(
  token: string,
  contractId: string,
  message?: string,
  ccEmails: string[] = []
): Promise<{ message: string; sent_to: string }> {
  const requestBody: SendVendorContractRequest = {
    message,
    cc_emails: ccEmails,
  };

  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}/send`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to send contract'));
  }

  return response.json();
}

export async function uploadContractPdf(
  token: string,
  file: File,
  data: {
    wedding_id: string;
    vendor_profile_id: string;
    contract_title: string;
    total_amount: number;
    deposit_amount?: number;
    service_date?: string;
    service_location?: string;
    notes?: string;
  }
): Promise<VendorContract> {
  const formData = new FormData();
  formData.append('file', file);

  const params = new URLSearchParams();
  params.append('wedding_id', data.wedding_id);
  params.append('vendor_profile_id', data.vendor_profile_id);
  params.append('contract_title', data.contract_title);
  params.append('total_amount', String(data.total_amount));
  if (data.deposit_amount) params.append('deposit_amount', String(data.deposit_amount));
  if (data.service_date) params.append('service_date', data.service_date);
  if (data.service_location) params.append('service_location', data.service_location);
  if (data.notes) params.append('notes', data.notes);

  const response = await fetch(`${API_BASE}/admin/contracts/upload-pdf?${params.toString()}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to upload contract PDF'));
  }

  return response.json();
}

export async function getContractFormData(
  token: string,
  contractId: string
): Promise<VendorContractFormDataResponse> {
  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}/form-data`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    return { vendor_submissions: [], available_fields: {}, suggested_contract_fields: {} };
  }

  return response.json();
}

export async function applyFormDataToContract(
  token: string,
  contractId: string,
  data: ApplyVendorContractFormDataRequest
): Promise<VendorContract> {
  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}/apply-form-data`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      form_submission_id: data.form_submission_id,
      field_mappings: data.field_mappings ?? {},
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to apply form data'));
  }

  return response.json();
}

export async function updateContractSections(
  token: string,
  contractId: string,
  data: UpdateVendorContractSectionsRequest
): Promise<VendorContract> {
  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}/sections`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to update contract sections'));
  }

  return response.json();
}

export async function createPaymentMilestones(
  token: string,
  contractId: string,
  milestones: PaymentMilestoneInput[]
): Promise<PaymentMilestone[]> {
  const requestBody: CreateVendorPaymentMilestonesRequest = { milestones };

  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}/milestones`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to create milestones'));
  }

  return response.json();
}

export async function getPaymentMilestones(
  token: string,
  params?: {
    contract_id?: string;
    wedding_id?: string;
    status?: string;
  }
): Promise<PaymentMilestone[]> {
  const queryParams = new URLSearchParams();
  if (params?.contract_id) queryParams.append('contract_id', params.contract_id);
  if (params?.wedding_id) queryParams.append('wedding_id', params.wedding_id);
  if (params?.status) queryParams.append('status', params.status);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/admin/milestones?${queryParams.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error('Payment milestones endpoint is not available. The backend endpoint may not be set up yet.');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to fetch payment milestones'));
  }

  return response.json();
}

export async function recordPayment(
  token: string,
  milestoneId: string,
  data: RecordVendorMilestonePaymentRequest
): Promise<PaymentMilestone> {
  const response = await fetch(`${API_BASE}/admin/milestones/${milestoneId}/pay`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to record payment'));
  }

  return response.json();
}

export async function saveContractAsTemplate(
  token: string,
  contractId: string,
  templateName: string,
  description?: string
): Promise<ContractTemplate> {
  const contract = await getContract(token, contractId);

  return createContractTemplate(token, {
    name: templateName,
    description: description || `Template created from ${contract.contract_title}`,
    service_category: contract.service_category,
    sections: contract.sections,
    terms_and_conditions: contract.terms_and_conditions,
    cancellation_policy: contract.cancellation_policy,
    is_public: false,
  });
}

export async function getPublicContract(
  contractId: string,
  accessToken: string
): Promise<PublicContract> {
  const response = await fetch(
    `${API_BASE}/vendor-contract/public/contracts/${contractId}/${encodeURIComponent(accessToken)}`
  );

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Contract not found');
    }
    if (response.status === 403) {
      throw new Error('Access denied - invalid or expired link');
    }
    throw new Error('Failed to fetch contract');
  }

  return response.json();
}

export async function signPublicContract(
  contractId: string,
  accessToken: string,
  signerName: string,
  signerEmail: string
): Promise<{ message: string; signed_at: string }> {
  const response = await fetch(
    `${API_BASE}/vendor-contract/public/contracts/${contractId}/${encodeURIComponent(accessToken)}/sign`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        signer_name: signerName,
        signer_email: signerEmail,
      }),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to sign contract'));
  }

  return response.json();
}

export function getContractStatusColor(status: ContractStatus): string {
  const colors: Record<ContractStatus, string> = {
    draft: 'bg-gray-100 text-gray-800',
    pending_review: 'bg-yellow-100 text-yellow-800',
    sent: 'bg-blue-100 text-blue-800',
    viewed: 'bg-indigo-100 text-indigo-800',
    signed: 'bg-green-100 text-green-800',
    active: 'bg-teal-100 text-teal-800',
    completed: 'bg-emerald-100 text-emerald-800',
    cancelled: 'bg-red-100 text-red-800',
    expired: 'bg-orange-100 text-orange-800',
  };

  return colors[status] || 'bg-gray-100 text-gray-800';
}

export function getPaymentStatusColor(status: PaymentMilestone['status']): string {
  const colors = {
    pending: 'bg-gray-100 text-gray-800',
    due: 'bg-yellow-100 text-yellow-800',
    overdue: 'bg-red-100 text-red-800',
    paid: 'bg-green-100 text-green-800',
    partial: 'bg-blue-100 text-blue-800',
  };

  return colors[status] || 'bg-gray-100 text-gray-800';
}
