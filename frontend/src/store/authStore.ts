import { create } from "zustand";
import { persist } from "zustand/middleware";

type AuthUser = {
  id: number;
  email: string;
  full_name: string;
  organization_id: number;
  roles: string[];
  permissions: string[];
  mfa?: {
    totp_enabled?: boolean;
  };
};

type AuthTokens = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

type AuthState = {
  tenantSlug: string;
  user: AuthUser | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  setTenantSlug: (slug: string) => void;
  setAuth: (tokens: AuthTokens, user: AuthUser) => void;
  setUser: (user: AuthUser | null) => void;
  clearAuth: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      tenantSlug: "default",
      user: null,
      tokens: null,
      isAuthenticated: false,
      setTenantSlug: (slug) => set({ tenantSlug: slug.trim().toLowerCase() || "default" }),
      setAuth: (tokens, user) =>
        set({
          tokens,
          user,
          isAuthenticated: true,
        }),
      setUser: (user) =>
        set({
          user,
          isAuthenticated: Boolean(user),
        }),
      clearAuth: () =>
        set({
          user: null,
          tokens: null,
          isAuthenticated: false,
        }),
    }),
    {
      name: "aaditech-spa-auth",
      partialize: (state) => ({
        tenantSlug: state.tenantSlug,
        tokens: state.tokens,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

export type { AuthUser, AuthTokens };
