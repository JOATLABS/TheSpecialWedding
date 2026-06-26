export function isAbortLikeFetchError(error: unknown) {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return true;
  }

  return error instanceof TypeError && error.message === 'Failed to fetch';
}
