export interface PublicContractErrorState {
  title: string;
  message: string;
  hint: string;
  isReplacedVersion: boolean;
}

export interface PublicContractErrorPayload {
  detail?: string;
  message?: string;
}

export function resolveVendorContractAccessToken(
  routeToken?: string | null,
  queryToken?: string | null
): string | null {
  return routeToken ?? queryToken ?? null;
}

export function getPublicContractErrorState(status: number): PublicContractErrorState {
  if (status === 410) {
    return {
      title: 'Contract Version Replaced',
      message: 'This contract version has been replaced. Please use the latest link sent by the planner.',
      hint: 'Please use the newest contract link sent by the wedding planner.',
      isReplacedVersion: true,
    };
  }

  if (status === 404) {
    return {
      title: 'Unable to Load Contract',
      message: 'Contract not found. It may have been removed or the link has expired.',
      hint: 'If you believe this is an error, please contact the wedding planner who sent you this contract.',
      isReplacedVersion: false,
    };
  }

  if (status === 403) {
    return {
      title: 'Unable to Load Contract',
      message: 'Access denied. This link may have expired or is invalid.',
      hint: 'If you believe this is an error, please contact the wedding planner who sent you this contract.',
      isReplacedVersion: false,
    };
  }

  return {
    title: 'Unable to Load Contract',
    message: 'Failed to load contract. Please try again later.',
    hint: 'If you believe this is an error, please contact the wedding planner who sent you this contract.',
    isReplacedVersion: false,
  };
}

export function getPublicContractSignErrorMessage(
  status: number,
  payload?: PublicContractErrorPayload | null
): string {
  if (status === 410) {
    return getPublicContractErrorState(410).message;
  }

  const detail = payload?.detail?.trim() || payload?.message?.trim();
  if (detail) {
    return detail;
  }

  if (status === 503) {
    return 'Contract signing is temporarily unavailable. Please try again later.';
  }

  return "We couldn't complete the signature. Please try again.";
}

export function isPublicContractAlreadySigned(status?: string | null): boolean {
  return status === 'signed' || status === 'completed';
}

export function canShowPublicContractSignControls(
  signed: boolean,
  isReplacedVersion: boolean
): boolean {
  return !signed && !isReplacedVersion;
}
