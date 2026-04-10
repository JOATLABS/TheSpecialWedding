import type {
  VendorContract,
  VendorContractRevisionHistoryResponse,
} from '@/services/vendorContractsApi';

export interface ContractDetailControlState {
  hasLiveSupersededSource: boolean;
  canEdit: boolean;
  canSend: boolean;
  canCreateRevision: boolean;
  paymentsReadOnly: boolean;
  showHistoricalBanner: boolean;
  defaultRevisionLabel: string;
}

export interface ContractDetailKeyDate {
  label: string;
  value: string;
}

export function hasLiveSupersededSource(
  contract: VendorContract | null,
  revisions: VendorContractRevisionHistoryResponse | null
): boolean {
  return (
    !contract?.supersedes_contract_id ||
    revisions?.current_contract_id === contract.supersedes_contract_id
  );
}

export function getContractDetailControlState(
  contract: VendorContract | null,
  revisions: VendorContractRevisionHistoryResponse | null
): ContractDetailControlState {
  const liveSupersededSource = hasLiveSupersededSource(contract, revisions);
  const isEditableStatus = !!contract && ['draft', 'pending_review'].includes(contract.status);
  const isCurrentVersion = contract?.is_current_version !== false;

  return {
    hasLiveSupersededSource: liveSupersededSource,
    canEdit: !!contract && isEditableStatus && (isCurrentVersion || liveSupersededSource),
    canSend: !!contract && isEditableStatus && (isCurrentVersion || liveSupersededSource),
    canCreateRevision:
      !!contract &&
      isCurrentVersion &&
      ['sent', 'viewed', 'signed'].includes(contract.status),
    paymentsReadOnly: contract?.is_current_version === false,
    showHistoricalBanner: contract?.is_current_version === false,
    defaultRevisionLabel: contract?.status === 'signed' ? 'Create Amendment' : 'Create Revision',
  };
}

export function sortContractRevisionHistory(
  revisions: VendorContractRevisionHistoryResponse | null
) {
  return [...(revisions?.versions || [])].sort(
    (left, right) => right.version_number - left.version_number
  );
}

export function buildContractKeyDates(
  contract: VendorContract | null
): ContractDetailKeyDate[] {
  if (!contract) {
    return [];
  }

  return ([
    { label: 'Created', value: contract.created_at },
    contract.sent_at ? { label: 'Sent', value: contract.sent_at } : null,
    contract.viewed_at ? { label: 'Viewed', value: contract.viewed_at } : null,
    contract.signed_at ? { label: 'Signed', value: contract.signed_at } : null,
  ].filter(Boolean) as ContractDetailKeyDate[]);
}

export function buildEditableContractState(contract: VendorContract) {
  return {
    contract,
    editedContract: contract,
    editedSections: contract.sections || [],
  };
}
