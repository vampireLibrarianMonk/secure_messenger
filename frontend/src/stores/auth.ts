import { defineStore } from "pinia";
import { apiRequest } from "../lib/api";
import type { AuthResponse } from "../types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: { id: number; username: string; email: string } | null;
}

export interface NotificationPreferencePayload {
  dm_sound: string;
  dm_document_sound: string;
  video_ring_sound: string;
  chat_leave_sound: string;
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
    async changePassword(currentPassword: string, newPassword: string, confirmNewPassword: string) {
      if (!this.accessToken) {
        throw new Error("Not authenticated");
      }
      return apiRequest<{ detail: string }>("/auth/change-password/", {
        method: "POST",
        token: this.accessToken,
        body: {
          current_password: currentPassword,
          new_password: newPassword,
          confirm_new_password: confirmNewPassword,
        },
      });
    },
    async loadNotificationPreferences() {
      if (!this.accessToken) {
        throw new Error("Not authenticated");
      }
      return apiRequest<NotificationPreferencePayload>("/auth/notification-preferences/", {
        token: this.accessToken,
      });
    },
    async saveNotificationPreferences(preferences: NotificationPreferencePayload) {
      if (!this.accessToken) {
        throw new Error("Not authenticated");
      }
      return apiRequest<NotificationPreferencePayload>("/auth/notification-preferences/", {
        method: "PUT",
        token: this.accessToken,
        body: preferences,
      });
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
