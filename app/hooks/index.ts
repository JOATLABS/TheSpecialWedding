/**
 * Central export point for all API hooks
 *
 * Import from @/hooks instead of @/hooks/useApi etc.
 */

// Core hooks
export { useApi, type ApiOptions, type ApiResponse } from './useApi';
export { useFetch, type UseFetchOptions, type UseFetchResult } from './useFetch';
export { useMutation, useCreateMutation, useUpdateMutation, useDeleteMutation, type UseMutationOptions, type UseMutationResult } from './useMutation';
export { usePaginatedFetch, type PaginationMeta, type UsePaginatedFetchOptions, type UsePaginatedFetchResult } from './usePaginatedFetch';

// Existing hooks (for backward compatibility)
export { useBudget } from './useBudget';
export { useTheme } from './useTheme';
export { useSlideshow } from './useSlideshow';
export { useWedding } from './useWedding';
