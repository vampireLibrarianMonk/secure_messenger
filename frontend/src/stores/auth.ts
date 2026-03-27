import { defineStore } from "pinia";
import { apiRequest } from "../lib/api";
import type { AuthResponse } from "../types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: {
    id: number;
    username: string;
    email: string;
    must_reset_password?: boolean;
    is_security_admin?: boolean;
  } | null;
}

const ACCESS_KEY = "sm_access";
const REFRESH_KEY = "sm_refresh";

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    accessToken: localStorage.getItem(ACCESS_KEY),
    refreshToken: localStorage.getItem(REFRESH_KEY),
    user: null,
  }),
  getters: {
    isAuthenticated: (s) => Boolean(s.accessToken),
  },
  actions: {
    async register(username: string, email: string, password: string) {
      const res = await apiRequest<AuthResponse>("/auth/register/", {
        method: "POST",
        body: { username, email, password },
      });
      this.setTokens(res.access, res.refresh);
      this.user = res.user;
    },
    async login(username: string, password: string) {
      const res = await apiRequest<{ access: string; refresh: string }>("/auth/login/", {
        method: "POST",
        body: { username, password },
      });
      this.setTokens(res.access, res.refresh);
      await this.loadMe();
    },
    async loadMe() {
      if (!this.accessToken) return;
      this.user = await apiRequest("/auth/me/", { token: this.accessToken });
    },
    async logout() {
      if (this.accessToken && this.refreshToken) {
        await apiRequest("/auth/logout/", {
          method: "POST",
          token: this.accessToken,
          body: { refresh: this.refreshToken },
        }).catch(() => undefined);
      }
      this.accessToken = null;
      this.refreshToken = null;
      this.user = null;
      localStorage.removeItem(ACCESS_KEY);
      localStorage.removeItem(REFRESH_KEY);
    },
    setTokens(access: string, refresh: string) {
      this.accessToken = access;
      this.refreshToken = refresh;
      localStorage.setItem(ACCESS_KEY, access);
      localStorage.setItem(REFRESH_KEY, refresh);
    },
  },
});
