import { apiClient } from "./axios";
import type { AuthTokens, AuthUser } from "../store/authStore";

type LoginPayload = {
  email: string;
  password: string;
  tenantSlug: string;
};

type LoginResponse = {
  status: string;
  tokens?: AuthTokens;
  challenge?: {
    challenge_token: string;
    token_type: string;
    expires_in: number;
  };
  challenge_type?: "totp";
  mfa_required?: boolean;
  user: Omit<AuthUser, "permissions">;
};

type MeResponse = {
  status: string;
  user: AuthUser;
};

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>("/api/auth/login", {
    email: payload.email,
    password: payload.password,
  }, {
    headers: {
      "X-Tenant-Slug": payload.tenantSlug,
    },
  });
  return response.data;
}

export async function verifyTotpLogin(challengeToken: string, code: string): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>("/api/auth/mfa/totp/verify-login", {
    challenge_token: challengeToken,
    code,
  });
  return response.data;
}

export async function fetchMe(): Promise<MeResponse> {
  const response = await apiClient.get<MeResponse>("/api/auth/me");
  return response.data;
}

export async function fetchMeWithAuth(accessToken: string, tenantSlug: string): Promise<MeResponse> {
  const headers: Record<string, string> = {};
  headers.Authorization = `Bearer ${accessToken}`;
  headers["X-Tenant-Slug"] = tenantSlug;

  const response = await apiClient.get<MeResponse>("/api/auth/me", {
    headers,
  });
  return response.data;
}

export async function logout(): Promise<void> {
  await apiClient.post("/api/auth/logout");
}
