import { useSyncExternalStore } from 'react';
import { getGpuBudget, subscribeGpuBudget } from '@/lib/gpu-budget';

/** Whether the expensive visual layer should run, and why not when it should not. */
export function useGpuBudget() {
  return useSyncExternalStore(subscribeGpuBudget, getGpuBudget, getGpuBudget);
}
