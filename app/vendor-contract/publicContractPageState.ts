export interface PublicContractErrorState {
  title: string;
  message: string;
  hint: string;
  isReplacedVersion: boolean;
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

export function isPublicContractAlreadySigned(status?: string | null): boolean {
  return status === 'signed' || status === 'completed';
}

export function canShowPublicContractSignControls(
  signed: boolean,
  isReplacedVersion: boolean
): boolean {
  return !signed && !isReplacedVersion;
}
