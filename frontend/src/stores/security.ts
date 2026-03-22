import { defineStore } from "pinia";

interface SecurityState {
  locked: boolean;
  inactivitySeconds: number;
  passcode: string;
  conversationKeys: Record<number, string>;
  lastActivityAt: number;
}

let timer: number | null = null;

export const useSecurityStore = defineStore("security", {
  state: (): SecurityState => ({
    locked: true,
    inactivitySeconds: Number(localStorage.getItem("sm_inactivity_seconds") ?? 120),
    passcode: localStorage.getItem("sm_passcode") ?? "1234",
    conversationKeys: {},
    lastActivityAt: Date.now(),
  }),
  actions: {
    unlock(passcode: string): boolean {
      if (passcode !== this.passcode) return false;
      this.locked = false;
      this.touch();
      this.startTimer();
      return true;
    },
    lockNow() {
      this.locked = true;
      this.wipeMemoryKeys();
      this.stopTimer();
    },
    wipeMemoryKeys() {
      this.conversationKeys = {};
    },
    setInactivityTimeout(seconds: number) {
      this.inactivitySeconds = seconds;
      localStorage.setItem("sm_inactivity_seconds", String(seconds));
      this.startTimer();
    },
    setPasscode(passcode: string) {
      this.passcode = passcode;
      localStorage.setItem("sm_passcode", passcode);
    },
    resetLocalSecurity() {
      this.passcode = "1234";
      this.inactivitySeconds = 120;
      this.wipeMemoryKeys();
      this.locked = true;
      this.stopTimer();
      localStorage.setItem("sm_passcode", "1234");
      localStorage.setItem("sm_inactivity_seconds", "120");
    },
    setConversationKey(conversationId: number, key: string) {
      this.conversationKeys[conversationId] = key;
      this.touch();
    },
    getConversationKey(conversationId: number): string | undefined {
      return this.conversationKeys[conversationId];
    },
    touch() {
      this.lastActivityAt = Date.now();
    },
    startTimer() {
      this.stopTimer();
      timer = window.setInterval(() => {
        if (!this.locked && Date.now() - this.lastActivityAt > this.inactivitySeconds * 1000) {
          this.lockNow();
        }
      }, 1000);
    },
    stopTimer() {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    },
  },
});
