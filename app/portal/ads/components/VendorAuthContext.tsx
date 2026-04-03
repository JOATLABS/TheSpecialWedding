'use client';

import { createContext, useContext } from 'react';

export interface VendorUser {
  _id: string;
  email: string;
  name: string;
  role: string;
  must_change_password?: boolean;
}

export interface VendorAuthContextType {
  token: string | null;
  user: VendorUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const VendorAuthContext = createContext<VendorAuthContextType>({
  token: null,
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
});

export function useVendorAuth() {
  return useContext(VendorAuthContext);
}
