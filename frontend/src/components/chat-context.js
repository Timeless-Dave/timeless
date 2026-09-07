import { createContext, useContext } from 'react';

/** Chat panel state, kept out of the component file for fast refresh. */
export const ChatContext = createContext(null);

export function useChatPanel() {
  const value = useContext(ChatContext);
  if (!value) throw new Error('useChatPanel must be used within ChatProvider');
  return value;
}
