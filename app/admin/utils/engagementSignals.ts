import { isAbortLikeFetchError } from './adminFetchErrors';

export function isIgnorableEngagementSignalsError(error: unknown) {
  return isAbortLikeFetchError(error);
}
