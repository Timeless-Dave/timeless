import { createContext, useContext } from 'react';

/** Shared day state. Kept apart from the provider component so that file can
 * export only a component and stay fast-refreshable. */
export const TodayContext = createContext(null);

export function useToday() {
  const value = useContext(TodayContext);
  if (!value) throw new Error('useToday must be used within TodayProvider');
  return value;
}
