// hooks/useIsAdmin.js
import { getStoredTokens, getUserFromTokens } from '../utils/auth';

export function useIsAdmin() {
  const tokens = getStoredTokens();
  const user = getUserFromTokens(tokens);
  const raw = user?.['cognito:groups'] ?? [];
  // Cognito puts groups as an array in the decoded JWT
  const groups = Array.isArray(raw) ? raw : [raw];
  
  return {
    isAdmin: groups.includes('admins') || groups.includes('superadmins'),
    isSuperAdmin: groups.includes('superadmins'),
    groups,
  };
}