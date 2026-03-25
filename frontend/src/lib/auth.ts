import { apiClient } from "./axios";
import type { AuthTokens, AuthUser } from "../store/authStore";

type LoginPayload = {
  email: string;
  password: string;
  tenantSlug: string;
};

type LoginResponse = {
  status: string;
  tokens: AuthTokens;
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

export async function fetchMe(): Promise<MeResponse> {
  const response = await apiClient.get<MeResponse>("/api/auth/me");
  return response.data;
}

export async function logout(): Promise<void> {
  await apiClient.post("/api/auth/logout");
}
