<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useAuthStore } from "./stores/auth";
import { useChatStore } from "./stores/chat";
import { useSecurityStore } from "./stores/security";
import { useVideoStore } from "./stores/video";
import { apiRequest } from "./lib/api";
import { decryptFile, encryptFile, encryptText, exportPublicKey, generateConversationKey, generateIdentityKeypair } from "./lib/crypto";
import type { Attachment, SecurityAnalysisRun, SecurityJourneyReport } from "./types";

const auth = useAuthStore();
const chat = useChatStore();
const security = useSecurityStore();
const video = useVideoStore();

const authMode = ref<"login" | "register">("login");
const username = ref("");
const email = ref("");
const password = ref("");
const authError = ref("");

const unlockPin = ref("");
const unlockError = ref("");
const inactivityInput = ref(security.inactivitySeconds);

const draftMessage = ref("");
const composerError = ref("");
const createTitle = ref("");
const createKind = ref<"dm" | "group">("dm");
const createMembers = ref("");
const newPasscode = ref("");
const confirmPasscode = ref("");
const passcodeMessage = ref("");
const notificationsReady = ref(false);
const refreshingConversations = ref(false);
const nowTick = ref(Date.now());
const unreadByConversation = ref<Record<number, number>>({});
const memberNamesByConversation = ref<Record<number, Record<number, string>>>({});
const localVideoEl = ref<HTMLVideoElement | null>(null);
const remoteVideoEl = ref<HTMLVideoElement | null>(null);
const fileInputEl = ref<HTMLInputElement | null>(null);

const adminMenuSections = ref<Array<{ key: string; label: string }>>([]);
const adminActiveTab = ref("overview");
const adminReports = ref<SecurityJourneyReport[]>([]);
const adminSelectedReportId = ref<number | null>(null);
const adminDashboard = ref<Record<string, unknown> | null>(null);
const adminCompiled = ref<Record<string, unknown> | null>(null);
const adminRuns = ref<SecurityAnalysisRun[]>([]);
const adminAuditEvents = ref<Array<Record<string, unknown>>>([]);
const adminSnapshots = ref<Array<Record<string, unknown>>>([]);
const adminSnapshotVerify = ref<Record<number, { match: boolean; stored_sha256: string; recomputed_sha256: string }>>({});
const adminError = ref("");
const adminStatus = ref("");
const adminBusy = ref(false);
const adminRunInProgress = ref(false);
const adminStatusLog = ref<Array<{ ts: string; message: string }>>([]);
const adminNewReportTitle = ref("Security Journey Analysis");
const adminRunFlowType = ref<"dm" | "video" | "both">("both");
const adminSelectedChecks = ref<string[]>(["dm", "video", "logging"]);
const adminResetOldPassword = ref("");
const adminResetNewPassword = ref("");
const adminResetConfirmPassword = ref("");
const adminResetStatus = ref("");

const adminTestCatalog: Array<{ key: string; title: string; plainEnglish: string }> = [
  {
    key: "dm",
    title: "Direct Message Journey",
    plainEnglish: "Checks how a message is created, protected, transported, stored, and opened by the recipient.",
  },
  {
    key: "video",
    title: "Live Video Journey",
    plainEnglish: "Checks call setup, signaling, ICE/TURN routing, and media protection visibility.",
  },
  {
    key: "logging",
    title: "Logging & Exposure Controls",
    plainEnglish: "Checks whether logs/telemetry avoid sensitive plaintext and keep only safe metadata.",
  },
];

const compiledDmStages = computed(
  () => ((adminCompiled.value?.dm_stage_by_stage_journey as Array<Record<string, unknown>>) ?? []),
);
const compiledVideoStages = computed(
  () => ((adminCompiled.value?.video_stage_by_stage_journey as Array<Record<string, unknown>>) ?? []),
);
const compiledVerification = computed(
  () => ((adminCompiled.value?.verification_matrix as Array<Record<string, unknown>>) ?? []),
);
const compiledScopeCoverage = computed(
  () => ((adminCompiled.value?.scope_coverage as Array<Record<string, unknown>>) ?? []),
);
const compiledLoggingDesign = computed(
  () => ((adminCompiled.value?.logging_design as Array<Record<string, unknown>>) ?? []),
);
const compiledThreatModel = computed(
  () => ((adminCompiled.value?.threat_model as Array<Record<string, unknown>>) ?? []),
);
const compiledGaps = computed(
  () => ((adminCompiled.value?.top_10_likely_security_gaps as Array<Record<string, unknown>>) ?? []),
);
const compiledNextTests = computed(
  () => ((adminCompiled.value?.highest_value_next_tests as Array<Record<string, unknown>>) ?? []),
);
const compiledReality = computed(
  () => ((adminCompiled.value?.reality_check_answers as Record<string, string>) ?? {}),
);

function pushAdminStatus(message: string) {
  const stamp = new Date().toLocaleTimeString();
  adminStatus.value = message;
  adminStatusLog.value.unshift({ ts: stamp, message });
  adminStatusLog.value = adminStatusLog.value.slice(0, 8);
}

function describeCheck(check: string): string {
  return adminTestCatalog.find((item) => item.key === check)?.title ?? check;
}

function nextMessageIndex(): number {
  // Backend currently validates against 32-bit signed max (2147483647),
  // so use unix seconds (safe through year 2038) instead of Date.now() ms.
  return Math.floor(Date.now() / 1000);
}

const activeMessageIds = new Set<number>();
let knownConversationIds = new Set<number>();
let knownMessageIds = new Set<number>();
let outgoingRingTimer: number | null = null;
let incomingRingTimer: number | null = null;

const activeConversation = computed(() =>
  chat.conversations.find((c) => c.id === chat.activeConversationId) ?? null,
);
const showStartCall = computed(() => Boolean(activeConversation.value) && !video.inCall && !video.hasIncomingCallIntent);
const showJoinCall = computed(() => Boolean(activeConversation.value) && !video.inCall && video.hasIncomingCallIntent);
const showEndCall = computed(() => video.inCall || video.status === "testing" || video.status === "active");
const isSecurityAdmin = computed(() => Boolean(auth.user?.is_security_admin) && !auth.user?.must_reset_password);

const formattedVideoDiagnostics = computed(() => {
  const d = video.diagnostics;
  const fmt = (value: number | null, digits = 1) => (value === null ? "—" : value.toFixed(digits));
  return {
    localFps: fmt(d.localFps),
    remoteFps: fmt(d.remoteFps),
    localResolution: d.localResolution ?? "—",
    remoteResolution: d.remoteResolution ?? "—",
    outboundKbps: fmt(d.outboundKbps),
    inboundKbps: fmt(d.inboundKbps),
    packetLossPct: fmt(d.packetLossPct, 2),
    rttMs: fmt(d.rttMs),
    updatedAt: d.updatedAt ? new Date(d.updatedAt).toLocaleTimeString() : "—",
  };
});

function bindActivityListeners() {
  const touch = () => security.touch();
  window.addEventListener("mousemove", touch);
  window.addEventListener("keydown", touch);
  return () => {
    window.removeEventListener("mousemove", touch);
    window.removeEventListener("keydown", touch);
  };
}

let unbindActivity = () => undefined;
let refreshTimer: number | null = null;
let countdownTimer: number | null = null;

const notificationCount = computed(() => Object.values(unreadByConversation.value).reduce((sum, v) => sum + v, 0));
const hasNotifications = computed(() => notificationCount.value > 0);
const secondsUntilLock = computed(() => {
  if (security.locked) return 0;
  const elapsed = Math.floor((nowTick.value - security.lastActivityAt) / 1000);
  return Math.max(0, security.inactivitySeconds - elapsed);
});

function playNotificationDing() {
  try {
    const AudioContextImpl = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextImpl) return;
    const context = new AudioContextImpl();
    const oscillator = context.createOscillator();
    const gainNode = context.createGain();
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(880, context.currentTime);
    gainNode.gain.setValueAtTime(0.001, context.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.15, context.currentTime + 0.01);
    gainNode.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.22);
    oscillator.connect(gainNode);
    gainNode.connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.24);
  } catch {
    // best-effort only
  }
}

function playTone(frequency: number, durationMs: number) {
  try {
    const AudioContextImpl =
      window.AudioContext ||
      (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextImpl) return;
    const context = new AudioContextImpl();
    const oscillator = context.createOscillator();
    const gainNode = context.createGain();
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(frequency, context.currentTime);
    gainNode.gain.setValueAtTime(0.001, context.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.08, context.currentTime + 0.01);
    gainNode.gain.exponentialRampToValueAtTime(0.001, context.currentTime + durationMs / 1000);
    oscillator.connect(gainNode);
    gainNode.connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + durationMs / 1000);
  } catch {
    // best effort
  }
}

function stopOutgoingRing() {
  if (outgoingRingTimer !== null) {
    window.clearInterval(outgoingRingTimer);
    outgoingRingTimer = null;
  }
}

function stopIncomingRing() {
  if (incomingRingTimer !== null) {
    window.clearInterval(incomingRingTimer);
    incomingRingTimer = null;
  }
}

function startOutgoingRing() {
  if (outgoingRingTimer !== null) return;
  playTone(740, 220);
  outgoingRingTimer = window.setInterval(() => {
    playTone(740, 220);
  }, 1500);
}

function startIncomingRing() {
  if (incomingRingTimer !== null) return;
  playTone(560, 160);
  window.setTimeout(() => playTone(660, 160), 170);
  incomingRingTimer = window.setInterval(() => {
    playTone(560, 160);
    window.setTimeout(() => playTone(660, 160), 170);
  }, 2000);
}

function triggerNotification(conversationId: number, increment = 1) {
  unreadByConversation.value[conversationId] = (unreadByConversation.value[conversationId] ?? 0) + increment;
  playNotificationDing();
}

function clearNotifications() {
  unreadByConversation.value = {};
}

function seenConversationsStorageKey() {
  return auth.user ? `sm_seen_conversations_${auth.user.id}` : null;
}

function seenMessagesStorageKey() {
  return auth.user ? `sm_seen_messages_${auth.user.id}` : null;
}

function loadSeenNotificationState() {
  knownConversationIds = new Set<number>();
  knownMessageIds = new Set<number>();

  const conversationsKey = seenConversationsStorageKey();
  const messagesKey = seenMessagesStorageKey();
  if (!conversationsKey || !messagesKey) return;

  try {
    const seenConversations = JSON.parse(localStorage.getItem(conversationsKey) ?? "[]") as number[];
    seenConversations.forEach((id) => knownConversationIds.add(id));
  } catch {
    // ignore malformed local state
  }

  try {
    const seenMessages = JSON.parse(localStorage.getItem(messagesKey) ?? "[]") as number[];
    seenMessages.forEach((id) => knownMessageIds.add(id));
  } catch {
    // ignore malformed local state
  }
}

function saveSeenNotificationState() {
  const conversationsKey = seenConversationsStorageKey();
  const messagesKey = seenMessagesStorageKey();
  if (!conversationsKey || !messagesKey) return;
  localStorage.setItem(conversationsKey, JSON.stringify([...knownConversationIds]));
  localStorage.setItem(messagesKey, JSON.stringify([...knownMessageIds]));
}

async function refreshConversations(showErrors = false) {
  if (refreshingConversations.value) return;
  refreshingConversations.value = true;
  try {
    await chat.loadConversations();
    const unseenConversations = chat.conversations.filter((c) => !knownConversationIds.has(c.id));

    if (notificationsReady.value) {
      const newConversations = unseenConversations.filter(
        (c) => c.created_by !== auth.user?.id,
      );
      for (const conversation of newConversations) {
        triggerNotification(conversation.id, 1);
      }
    }

    unseenConversations.forEach((c) => knownConversationIds.add(c.id));
    saveSeenNotificationState();
  } catch (error) {
    if (showErrors) {
      composerError.value = error instanceof Error ? error.message : "Failed to refresh conversations";
    }
  } finally {
    refreshingConversations.value = false;
  }
}

async function refreshCurrentConversationMessages() {
  if (!chat.activeConversationId) return;
  try {
    await chat.refreshMessages(chat.activeConversationId);
  } catch {
    // Conversation may have been deleted/nuked by another participant.
    await refreshConversations();
    const stillExists = chat.conversations.some((c) => c.id === chat.activeConversationId);
    if (!stillExists) {
      chat.activeConversationId = chat.conversations[0]?.id ?? null;
      if (chat.activeConversationId) {
        await chat.loadMessages(chat.activeConversationId);
      } else {
        chat.disconnectSocket();
      }
    }
  }
}

async function ensureDeviceRegistration() {
  if (!auth.accessToken) return;
  const devices = await apiRequest<Array<{ id: number }>>("/devices/", { token: auth.accessToken });
  if (devices.length > 0) return;
  const keypair = await generateIdentityKeypair();
  const identityKey = await exportPublicKey(keypair.publicKey);
  await apiRequest("/devices/", {
    method: "POST",
    token: auth.accessToken,
    body: {
      name: `browser-${navigator.platform}`,
      identity_key: identityKey,
      signed_prekey: identityKey,
      one_time_prekeys: [],
      fingerprint: identityKey.slice(0, 32),
    },
  });
}

async function bootstrap() {
  if (!auth.accessToken) return;
  await auth.loadMe();
  loadSeenNotificationState();
  await ensureDeviceRegistration();
  await refreshConversations();
  if (chat.activeConversationId) {
    await chat.loadMessages(chat.activeConversationId);
  }
  if (isSecurityAdmin.value) {
    await loadAdminWorkspace();
  }
}

async function loadAdminWorkspace() {
  if (!auth.accessToken || !isSecurityAdmin.value) return;
  adminError.value = "";
  adminStatus.value = "";
  adminBusy.value = true;
  try {
    const [menu, reports] = await Promise.all([
      apiRequest<{ sections: Array<{ key: string; label: string }> }>("/admin/security/menu/", { token: auth.accessToken }),
      apiRequest<SecurityJourneyReport[]>("/admin/security/reports/", { token: auth.accessToken }),
    ]);
    adminMenuSections.value = menu.sections;
    adminReports.value = reports;
    if (!adminSelectedReportId.value && reports.length > 0) {
      adminSelectedReportId.value = reports[0].id;
    }
    if (adminSelectedReportId.value) {
      await loadAdminReportData(adminSelectedReportId.value);
    }
  } catch (error) {
    adminError.value = error instanceof Error ? error.message : "Failed loading admin workspace";
  } finally {
    adminBusy.value = false;
  }
}

async function loadAdminReportData(reportId: number) {
  if (!auth.accessToken) return;
  adminBusy.value = true;
  adminError.value = "";
  try {
    const [dashboard, compiled, runs, audits, snapshots] = await Promise.all([
      apiRequest<Record<string, unknown>>(`/admin/security/dashboard/?report=${reportId}`, { token: auth.accessToken }),
      apiRequest<Record<string, unknown>>(`/admin/security/reports/${reportId}/compiled/`, { token: auth.accessToken }),
      apiRequest<SecurityAnalysisRun[]>(`/admin/security/runs/?report=${reportId}`, { token: auth.accessToken }),
      apiRequest<Array<Record<string, unknown>>>(`/admin/security/audit-events/?report=${reportId}`, { token: auth.accessToken }),
      apiRequest<Array<Record<string, unknown>>>(`/admin/security/snapshots/?report=${reportId}`, { token: auth.accessToken }),
    ]);
    adminDashboard.value = dashboard;
    adminCompiled.value = compiled;
    adminRuns.value = runs;
    adminAuditEvents.value = audits;
    adminSnapshots.value = snapshots;
  } catch (error) {
    adminError.value = error instanceof Error ? error.message : "Failed loading report data";
  } finally {
    adminBusy.value = false;
  }
}

async function createAdminReport() {
  if (!auth.accessToken) return;
  adminBusy.value = true;
  adminError.value = "";
  try {
    const report = await apiRequest<SecurityJourneyReport>("/admin/security/reports/", {
      method: "POST",
      token: auth.accessToken,
      body: {
        title: adminNewReportTitle.value.trim() || "Security Journey Analysis",
        flow_type: "both",
        status: "draft",
      },
    });
    adminReports.value.unshift(report);
    adminSelectedReportId.value = report.id;
    pushAdminStatus(`Created report #${report.id}.`);
    await loadAdminReportData(report.id);
  } catch (error) {
    adminError.value = error instanceof Error ? error.message : "Failed creating report";
  } finally {
    adminBusy.value = false;
  }
}

async function runAdminAnalysis() {
  if (!auth.accessToken) return;
  if (!adminSelectedReportId.value) {
    adminError.value = "Select a report first (or create one) before triggering a run.";
    return;
  }
  const checks = adminSelectedChecks.value.filter((v) => ["dm", "video", "logging"].includes(v));
  if (checks.length === 0) {
    adminError.value = "Select at least one check (DM, Video, or Logging).";
    return;
  }
  adminBusy.value = true;
  adminRunInProgress.value = true;
  adminError.value = "";
  pushAdminStatus(`Run requested for flow=${adminRunFlowType.value}.`);
  checks.forEach((check) => {
    pushAdminStatus(`Queued test: ${describeCheck(check)}.`);
  });
  try {
    const response = await apiRequest<{ run_id: number; run_status: string }>("/admin/security/run/", {
      method: "POST",
      token: auth.accessToken,
      body: {
        report_id: adminSelectedReportId.value,
        flow_type: adminRunFlowType.value,
        requested_checks: checks,
      },
    });
    pushAdminStatus(`Run #${response.run_id} ${response.run_status}. Refreshing dashboard artifacts...`);
    await loadAdminReportData(adminSelectedReportId.value);
    pushAdminStatus(`Run #${response.run_id} fully loaded.`);
  } catch (error) {
    adminError.value = error instanceof Error ? error.message : "Failed triggering analysis run";
  } finally {
    adminRunInProgress.value = false;
    adminBusy.value = false;
  }
}

async function createSnapshot() {
  if (!auth.accessToken || !adminSelectedReportId.value) return;
  adminBusy.value = true;
  adminError.value = "";
  try {
    await apiRequest(`/admin/security/reports/${adminSelectedReportId.value}/snapshots/`, {
      method: "POST",
      token: auth.accessToken,
      body: { notes: "UI snapshot" },
    });
    pushAdminStatus("Snapshot created.");
    await loadAdminReportData(adminSelectedReportId.value);
  } catch (error) {
    adminError.value = error instanceof Error ? error.message : "Failed creating snapshot";
  } finally {
    adminBusy.value = false;
  }
}

async function verifySnapshot(snapshotId: number) {
  if (!auth.accessToken) return;
  adminError.value = "";
  try {
    const result = await apiRequest<{ match: boolean; stored_sha256: string; recomputed_sha256: string }>(
      `/admin/security/snapshots/${snapshotId}/verify/`,
      { token: auth.accessToken },
    );
    adminSnapshotVerify.value[snapshotId] = result;
    pushAdminStatus(`Snapshot #${snapshotId} integrity ${result.match ? "verified" : "mismatch"}.`);
  } catch (error) {
    adminError.value = error instanceof Error ? error.message : "Failed verifying snapshot";
  }
}

async function completeAdminPasswordReset() {
  if (!auth.accessToken) return;
  adminResetStatus.value = "";
  if (!adminResetOldPassword.value || !adminResetNewPassword.value) {
    adminResetStatus.value = "Current and new password are required.";
    return;
  }
  if (adminResetNewPassword.value !== adminResetConfirmPassword.value) {
    adminResetStatus.value = "New passwords do not match.";
    return;
  }
  try {
    await apiRequest("/auth/password-reset/", {
      method: "POST",
      token: auth.accessToken,
      body: {
        old_password: adminResetOldPassword.value,
        new_password: adminResetNewPassword.value,
      },
    });
    adminResetStatus.value = "Password reset complete. Reloading admin access...";
    adminResetOldPassword.value = "";
    adminResetNewPassword.value = "";
    adminResetConfirmPassword.value = "";
    await auth.loadMe();
    await loadAdminWorkspace();
  } catch (error) {
    adminResetStatus.value = error instanceof Error ? error.message : "Password reset failed.";
  }
}

function selectAdminReport(event: Event) {
  const value = Number((event.target as HTMLSelectElement).value);
  adminSelectedReportId.value = Number.isFinite(value) ? value : null;
}

async function submitAuth() {
  authError.value = "";
  notificationsReady.value = false;
  try {
    if (authMode.value === "login") {
      await auth.login(username.value, password.value);
    } else {
      await auth.register(username.value, email.value, password.value);
    }
    await bootstrap();
  } catch (error) {
    authError.value = error instanceof Error ? error.message : "Authentication failed";
  }
}

function unlock() {
  unlockError.value = "";
  if (!security.unlock(unlockPin.value)) {
    unlockError.value = "Invalid passcode";
  }
  unlockPin.value = "";
}

async function resetLockedSession() {
  security.resetLocalSecurity();
  await video.endCall(false);
  chat.disconnectSocket();
  await auth.logout();
}

async function lockNow() {
  if (auth.accessToken) {
    await apiRequest("/session-events/", {
      method: "POST",
      token: auth.accessToken,
      body: { event_type: "lock", metadata: { reason: "manual" } },
    }).catch(() => undefined);
  }
  security.lockNow();
}

async function logout() {
  security.lockNow();
  await video.endCall(false);
  chat.disconnectSocket();
  notificationsReady.value = false;
  clearNotifications();
  activeMessageIds.clear();
  await auth.logout();
}

async function selectConversation(conversationId: number) {
  if (video.callConversationId && video.callConversationId !== conversationId && video.inCall) {
    await video.endCall();
  }
  await chat.loadMessages(conversationId);
  await loadConversationMembers(conversationId);
  await video.listenForIncoming(conversationId);
  if (unreadByConversation.value[conversationId]) {
    delete unreadByConversation.value[conversationId];
  }
}

async function runVideoStreamTest() {
  await video.startStreamTest();
}

async function runLoopbackVideoTest() {
  await video.startLoopbackTest();
}

async function runSignalingTest() {
  if (!chat.activeConversationId) return;
  await video.runSignalingTest(chat.activeConversationId);
}

function toggleVideoDiagnostics(event: Event) {
  const input = event.target as HTMLInputElement;
  video.setDiagnosticsEnabled(input.checked);
}

async function startVideoCall() {
  if (!chat.activeConversationId) return;
  await video.startCall(chat.activeConversationId);
}

async function joinVideoCall() {
  if (!chat.activeConversationId) return;
  await video.joinCall(chat.activeConversationId);
}

async function endVideoCall() {
  await video.endCall();
  video.resetStatusIfIdle();
}

function toggleMic() {
  video.toggleMic();
}

function toggleCamera() {
  video.toggleCamera();
}

function triggerFilePicker() {
  fileInputEl.value?.click();
}

function isOwnMessage(senderId: number): boolean {
  return senderId === auth.user?.id;
}

function senderLabel(senderId: number): string {
  if (isOwnMessage(senderId)) return "You";
  const conversationId = chat.activeConversationId;
  const username = conversationId ? memberNamesByConversation.value[conversationId]?.[senderId] : undefined;
  return username ?? `User ${senderId}`;
}

async function loadConversationMembers(conversationId: number) {
  if (memberNamesByConversation.value[conversationId]) return;
  if (!auth.accessToken) return;
  try {
    const members = await apiRequest<Array<{ user: number; username: string }>>(
      `/conversations/${conversationId}/members/`,
      { token: auth.accessToken },
    );
    memberNamesByConversation.value[conversationId] = Object.fromEntries(
      members.map((m) => [m.user, m.username]),
    );
  } catch {
    memberNamesByConversation.value[conversationId] = {};
  }
}

async function sendMessage() {
  composerError.value = "";
  const text = draftMessage.value.trim();
  if (!text || !chat.activeConversationId || !auth.accessToken) return;

  let key = security.getConversationKey(chat.activeConversationId);
  if (!key) {
    key = await generateConversationKey();
    security.setConversationKey(chat.activeConversationId, key);
  }

  try {
    const encrypted = await encryptText(text, key);
    await apiRequest("/messages/", {
      method: "POST",
      token: auth.accessToken,
      body: {
        conversation: chat.activeConversationId,
        ciphertext: encrypted.ciphertext,
        nonce: encrypted.nonce,
        aad: JSON.stringify({ kind: "text", shared_key: key }),
        message_index: nextMessageIndex(),
      },
    });
    await refreshCurrentConversationMessages();
    draftMessage.value = "";
  } catch (error) {
    composerError.value = error instanceof Error ? error.message : "Failed to send message";
  }
}

async function sendEncryptedFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || !chat.activeConversationId || !auth.accessToken) return;

  let key = security.getConversationKey(chat.activeConversationId);
  if (!key) {
    key = await generateConversationKey();
    security.setConversationKey(chat.activeConversationId, key);
  }

  try {
    const marker = await encryptText(`[file] ${file.name}`, key);
    const message = await apiRequest<{ id: number }>("/messages/", {
      method: "POST",
      token: auth.accessToken,
      body: {
        conversation: chat.activeConversationId,
        ciphertext: marker.ciphertext,
        nonce: marker.nonce,
        aad: JSON.stringify({ kind: "attachment", shared_key: key }),
        message_index: nextMessageIndex(),
      },
    });

    await refreshCurrentConversationMessages();

    const encrypted = await encryptFile(file);
    const formData = new FormData();
    formData.append("message", String(message.id));
    formData.append("mime_type", file.type || "application/octet-stream");
    formData.append("sha256", encrypted.sha256);
    formData.append("wrapped_file_key", encrypted.key);
    formData.append("file_nonce", encrypted.nonce);
    formData.append("blob", encrypted.encrypted, `${file.name}.enc`);
    await apiRequest("/attachments/", {
      method: "POST",
      token: auth.accessToken,
      body: formData,
      isFormData: true,
    });
  } catch (error) {
    composerError.value = error instanceof Error ? error.message : "Failed to upload file";
  }
}

function guessAttachmentName(messageText: string, attachment: Attachment): string {
  const markerPrefix = "[file] ";
  if (messageText.startsWith(markerPrefix)) {
    return messageText.slice(markerPrefix.length).trim();
  }
  const blobName = attachment.blob.split("/").pop() ?? "download.enc";
  return blobName.replace(/\.enc$/i, "") || "download";
}

async function downloadAttachment(message: { plaintext: string; attachments: Attachment[] }, attachment: Attachment) {
  try {
    const authToken = auth.accessToken;
    if (!authToken) throw new Error("Not authenticated");

    const apiBase = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";
    const origin = new URL(apiBase).origin;
    const blobUrl = attachment.blob.startsWith("http") ? attachment.blob : `${origin}${attachment.blob}`;

    const response = await fetch(blobUrl, {
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    });
    if (!response.ok) {
      throw new Error(`Failed to fetch attachment: ${response.status}`);
    }

    const encryptedBlob = await response.blob();
    const decryptedBlob = await decryptFile(
      encryptedBlob,
      attachment.wrapped_file_key,
      attachment.file_nonce,
      attachment.mime_type || "application/octet-stream",
    );

    const filename = guessAttachmentName(message.plaintext, attachment);
    const objectUrl = URL.createObjectURL(decryptedBlob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 2000);
  } catch (error) {
    composerError.value = error instanceof Error ? error.message : "Failed to download attachment";
  }
}

async function createConversation() {
  const title = createTitle.value.trim();
  if (!title) return;
  const memberUsernames = createMembers.value
    .split(",")
    .map((v) => v.trim())
    .filter((v) => v.length > 0);
  await chat.createConversation({ kind: createKind.value, title, memberUsernames });
  const key = await generateConversationKey();
  if (chat.activeConversationId) {
    security.setConversationKey(chat.activeConversationId, key);
  }
  createTitle.value = "";
  createMembers.value = "";
}

async function deleteActiveConversation() {
  if (!chat.activeConversationId) return;
  const confirmed = window.confirm("Delete this conversation for all members?");
  if (!confirmed) return;
  try {
    await chat.deleteConversation(chat.activeConversationId);
  } catch (error) {
    composerError.value = error instanceof Error ? error.message : "Failed to delete conversation";
  }
}

async function nukeActiveDmConversation() {
  if (!chat.activeConversationId) return;
  const confirmed = window.confirm("NUKE this 1:1 conversation for all participants? This cannot be undone.");
  if (!confirmed) return;
  try {
    await chat.nukeConversation(chat.activeConversationId);
  } catch (error) {
    composerError.value = error instanceof Error ? error.message : "Failed to nuke conversation";
  }
}

function startRefreshLoop() {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
  }
  refreshTimer = window.setInterval(async () => {
    if (security.locked || !auth.isAuthenticated) return;
    await refreshConversations();
    await refreshCurrentConversationMessages();
  }, 3000);
}

watch(
  () => video.localStream,
  (stream) => {
    if (!localVideoEl.value) return;
    localVideoEl.value.srcObject = stream;
  },
);

watch(
  () => video.remoteStream,
  (stream) => {
    if (!remoteVideoEl.value) return;
    remoteVideoEl.value.srcObject = stream;
  },
);

watch(
  () => video.playOutgoingRing,
  (enabled) => {
    if (enabled) {
      stopIncomingRing();
      startOutgoingRing();
    } else {
      stopOutgoingRing();
    }
  },
);

watch(
  () => video.playIncomingRing,
  (enabled) => {
    if (enabled) {
      stopOutgoingRing();
      startIncomingRing();
    } else {
      stopIncomingRing();
    }
  },
);

watch(
  [localVideoEl, () => video.localStream],
  ([el, stream]) => {
    if (el) el.srcObject = stream;
  },
);

watch(
  [remoteVideoEl, () => video.remoteStream],
  ([el, stream]) => {
    if (el) el.srcObject = stream;
  },
);

watch(
  () => chat.activeConversationId,
  async (conversationId) => {
    activeMessageIds.clear();
    chat.activeMessages.forEach((m) => activeMessageIds.add(m.id));
    if (conversationId && !video.inCall) {
      await loadConversationMembers(conversationId);
      await video.listenForIncoming(conversationId);
    }
  },
);

watch(
  () => chat.conversations.map((c) => c.id),
  (conversationIds) => {
    const allowed = new Set(conversationIds);
    for (const key of Object.keys(unreadByConversation.value)) {
      const id = Number(key);
      if (!allowed.has(id)) {
        delete unreadByConversation.value[id];
      }
    }
  },
  { deep: true },
);

watch(
  () => chat.activeMessages,
  (messages) => {
    const unseenMessages = messages.filter((m) => !knownMessageIds.has(m.id));
    const newIncoming = unseenMessages.filter((m) => m.sender !== auth.user?.id);

    messages.forEach((m) => activeMessageIds.add(m.id));
    unseenMessages.forEach((m) => knownMessageIds.add(m.id));
    saveSeenNotificationState();

    if (!notificationsReady.value) return;
    for (const message of newIncoming) {
      triggerNotification(message.conversation, 1);
    }
  },
  { deep: true },
);

watch(
  () => adminSelectedReportId.value,
  async (reportId, prev) => {
    if (!reportId || reportId === prev || !isSecurityAdmin.value) return;
    await loadAdminReportData(reportId);
  },
);

function updatePasscode() {
  passcodeMessage.value = "";
  if (newPasscode.value.length < 4) {
    passcodeMessage.value = "Passcode must be at least 4 characters.";
    return;
  }
  if (newPasscode.value !== confirmPasscode.value) {
    passcodeMessage.value = "Passcodes do not match.";
    return;
  }
  security.setPasscode(newPasscode.value);
  newPasscode.value = "";
  confirmPasscode.value = "";
  passcodeMessage.value = "Passcode updated.";
}

onMounted(async () => {
  unbindActivity = bindActivityListeners();
  await bootstrap();
  activeMessageIds.clear();
  chat.activeMessages.forEach((m) => activeMessageIds.add(m.id));
  notificationsReady.value = true;
  countdownTimer = window.setInterval(() => {
    nowTick.value = Date.now();
  }, 1000);
  startRefreshLoop();
});

onUnmounted(() => {
  unbindActivity();
  chat.disconnectSocket();
  void video.endCall(false);
  stopOutgoingRing();
  stopIncomingRing();
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
  if (countdownTimer !== null) {
    window.clearInterval(countdownTimer);
    countdownTimer = null;
  }
});
</script>

<template>
  <div class="app" @click="security.touch()">
    <header class="topbar">
      <h1>Secure Messenger</h1>
      <div v-if="auth.user" class="topbar-actions">
        <span class="muted">{{ auth.user.username }}</span>
        <button
          class="ghost bell-button"
          :class="{ alerted: hasNotifications }"
          @click="clearNotifications"
          title="Notifications"
        >
          🔔
          <span v-if="hasNotifications" class="bell-badge">{{ notificationCount }}</span>
        </button>
        <button @click="lockNow">Lock now</button>
        <button class="danger" @click="logout">Logout</button>
      </div>
    </header>

    <section v-if="!auth.isAuthenticated" class="card auth-screen">
      <h2>{{ authMode === "login" ? "Sign in" : "Create account" }}</h2>
      <input v-model="username" placeholder="Username" />
      <input v-if="authMode === 'register'" v-model="email" placeholder="Email" />
      <input v-model="password" type="password" placeholder="Password" @keydown.enter="submitAuth" />
      <button @click="submitAuth">{{ authMode === "login" ? "Login" : "Register" }}</button>
      <button class="ghost" @click="authMode = authMode === 'login' ? 'register' : 'login'">
        Switch to {{ authMode === "login" ? "register" : "login" }}
      </button>
      <p v-if="authError" class="error">{{ authError }}</p>
    </section>

    <section v-else-if="security.locked" class="card lock-screen">
      <h2>Session Locked</h2>
      <p>Enter passcode to restore in-memory keys and continue. Default passcode is <strong>1234</strong>.</p>
      <input v-model="unlockPin" type="password" placeholder="Passcode" @keydown.enter="unlock" />
      <button @click="unlock">Unlock</button>
      <button class="ghost" @click="resetLockedSession">Reset locked session</button>
      <p v-if="unlockError" class="error">{{ unlockError }}</p>
    </section>

    <main v-else class="layout">
      <section v-if="auth.user?.must_reset_password" class="card" style="grid-column: 1 / -1;">
        <h3>Security Admin Password Reset Required</h3>
        <p class="muted">
          Your bootstrap account must reset password before admin security endpoints are enabled.
        </p>
        <div class="admin-controls">
          <input v-model="adminResetOldPassword" type="password" placeholder="Current password" />
          <input v-model="adminResetNewPassword" type="password" placeholder="New password" />
          <input v-model="adminResetConfirmPassword" type="password" placeholder="Confirm new password" />
          <button @click="completeAdminPasswordReset">Reset password</button>
        </div>
        <p v-if="adminResetStatus" class="muted">{{ adminResetStatus }}</p>
      </section>

      <aside class="sidebar card">
        <h3>Conversations</h3>
        <ul>
          <li v-for="conversation in chat.conversations" :key="conversation.id">
            <button
              class="conversation-btn"
              :class="{ active: conversation.id === chat.activeConversationId }"
              @click="selectConversation(conversation.id)"
            >
              {{ conversation.title || `${conversation.kind} #${conversation.id}` }}
            </button>
          </li>
        </ul>
        <div class="new-conversation">
          <h4>New conversation</h4>
          <select v-model="createKind">
            <option value="dm">DM</option>
            <option value="group">Group</option>
          </select>
          <input v-model="createTitle" placeholder="Title" />
          <input v-model="createMembers" placeholder="Member usernames (comma-separated)" />
          <button @click="createConversation">Create</button>
        </div>

        <div class="new-conversation">
          <h4>Change lock passcode</h4>
          <input
            v-model="newPasscode"
            type="password"
            placeholder="New passcode"
            autocomplete="new-password"
            name="new-lock-passcode"
          />
          <input
            v-model="confirmPasscode"
            type="password"
            placeholder="Confirm passcode"
            autocomplete="new-password"
            name="confirm-lock-passcode"
          />
          <button @click="updatePasscode">Update passcode</button>
          <p v-if="passcodeMessage" class="muted">{{ passcodeMessage }}</p>
        </div>
      </aside>

      <section class="chat card">
        <header class="chat-head">
          <div>
            <h3>{{ activeConversation?.title || "No conversation selected" }}</h3>
            <button v-if="activeConversation" class="danger" @click="deleteActiveConversation">Delete conversation</button>
            <button
              v-if="activeConversation && activeConversation.kind === 'dm'"
              class="danger"
              @click="nukeActiveDmConversation"
            >
              Nuke 1:1 DM
            </button>
          </div>
          <label>
            Auto-lock (sec)
            <input
              v-model.number="inactivityInput"
              type="number"
              min="15"
              @change="security.setInactivityTimeout(inactivityInput)"
            />
          </label>
          <span class="muted">Auto-lock in: {{ secondsUntilLock }}s</span>
          <button class="ghost" @click="refreshConversations(true)">Refresh conversations</button>
        </header>

        <section class="video-panel" v-if="activeConversation">
          <div class="video-head">
            <strong>Video Stream</strong>
            <div class="video-head-right">
              <span class="muted">{{ video.statusMessage }}</span>
              <label class="video-diagnostics-toggle">
                <input
                  type="checkbox"
                  :checked="video.diagnosticsEnabled"
                  @change="toggleVideoDiagnostics"
                />
                Diagnostics
              </label>
            </div>
          </div>
          <div class="video-grid">
            <div class="video-frame">
              <video ref="localVideoEl" autoplay playsinline muted></video>
              <span>Local</span>
            </div>
            <div class="video-frame">
              <video ref="remoteVideoEl" autoplay playsinline></video>
              <span>Remote</span>
            </div>
          </div>
          <div class="video-actions">
            <button v-if="showStartCall" @click="startVideoCall">Start Call</button>
            <button v-if="showJoinCall" class="join-btn" @click="joinVideoCall">Join Call</button>
            <button v-if="video.localStream" class="ghost" @click="toggleMic">{{ video.micEnabled ? "Mute" : "Unmute" }}</button>
            <button v-if="video.localStream" class="ghost" @click="toggleCamera">{{ video.cameraEnabled ? "Camera Off" : "Camera On" }}</button>
            <button v-if="showEndCall" class="danger" @click="endVideoCall">End</button>
          </div>
          <div v-if="video.diagnosticsEnabled" class="video-diagnostics-panel">
            <div>Local FPS: {{ formattedVideoDiagnostics.localFps }}</div>
            <div>Remote FPS: {{ formattedVideoDiagnostics.remoteFps }}</div>
            <div>Local resolution: {{ formattedVideoDiagnostics.localResolution }}</div>
            <div>Remote resolution: {{ formattedVideoDiagnostics.remoteResolution }}</div>
            <div>Outbound bitrate (kbps): {{ formattedVideoDiagnostics.outboundKbps }}</div>
            <div>Inbound bitrate (kbps): {{ formattedVideoDiagnostics.inboundKbps }}</div>
            <div>Packet loss (%): {{ formattedVideoDiagnostics.packetLossPct }}</div>
            <div>RTT (ms): {{ formattedVideoDiagnostics.rttMs }}</div>
            <div>Updated: {{ formattedVideoDiagnostics.updatedAt }}</div>
            <div v-if="video.diagnosticsError" class="error">{{ video.diagnosticsError }}</div>
          </div>
          <details class="video-debug">
            <summary>Debug tools</summary>
            <div class="video-actions">
              <button class="ghost" @click="runVideoStreamTest">Test Camera/Mic</button>
              <button class="ghost" @click="runSignalingTest">Signaling Test</button>
              <button class="ghost" @click="runLoopbackVideoTest">Local Loopback Test</button>
            </div>
          </details>
          <div v-if="showJoinCall" class="incoming-call-note">
            Incoming call detected — tap <strong>Join Call</strong>
          </div>
        </section>

        <div class="messages">
          <article
            v-for="message in chat.activeMessages"
            :key="message.id"
            class="message"
            :class="isOwnMessage(message.sender) ? 'own-message' : 'other-message'"
          >
            <div class="message-meta">{{ senderLabel(message.sender) }}</div>
            <p>{{ message.plaintext }}</p>
            <div v-if="message.attachments?.length" class="attachment-list">
              <button
                v-for="attachment in message.attachments"
                :key="attachment.id"
                class="ghost attachment-btn"
                type="button"
                @click="downloadAttachment(message, attachment)"
              >
                Download {{ guessAttachmentName(message.plaintext, attachment) }}
              </button>
            </div>
            <small>{{ new Date(message.created_at).toLocaleTimeString() }}</small>
          </article>
        </div>

        <footer class="composer">
          <input v-model="draftMessage" placeholder="Type encrypted message" @keydown.enter="sendMessage" />
          <button @click="sendMessage">Send</button>
          <button class="ghost" type="button" @click="triggerFilePicker">File</button>
          <input ref="fileInputEl" class="file-hidden" type="file" @change="sendEncryptedFile" />
        </footer>
        <p v-if="composerError" class="error">{{ composerError }}</p>

        <section v-if="isSecurityAdmin" class="admin-workspace">
          <header class="admin-head">
            <h3>Admin Security Journey Workspace</h3>
            <span v-if="adminBusy" class="muted">Loading…</span>
          </header>
          <p v-if="adminError" class="error">{{ adminError }}</p>
          <p v-if="adminStatus" class="muted">{{ adminStatus }}</p>
          <div v-if="adminStatusLog.length" class="admin-panel" style="margin-bottom:0.6rem;">
            <div v-for="item in adminStatusLog" :key="`${item.ts}-${item.message}`" class="admin-item">
              [{{ item.ts }}] {{ item.message }}
            </div>
          </div>

          <div class="admin-controls">
            <input v-model="adminNewReportTitle" placeholder="New report title" />
            <button class="ghost" @click="createAdminReport">Create report</button>
            <select :value="adminSelectedReportId ?? ''" @change="selectAdminReport">
              <option disabled value="">Select report</option>
              <option v-for="r in adminReports" :key="r.id" :value="r.id">
                #{{ r.id }} · {{ r.title }} ({{ r.status }})
              </option>
            </select>
          </div>

          <nav class="admin-tabs">
            <button
              v-for="section in adminMenuSections"
              :key="section.key"
              class="ghost"
              :class="{ active: adminActiveTab === section.key }"
              @click="adminActiveTab = section.key"
            >
              {{ section.label }}
            </button>
          </nav>

          <section v-if="adminActiveTab === 'run_analysis'" class="admin-panel">
            <div class="admin-controls">
              <select v-model="adminRunFlowType">
                <option value="both">DM + Video</option>
                <option value="dm">DM only</option>
                <option value="video">Video only</option>
              </select>
              <select v-model="adminSelectedChecks" multiple size="3" title="Select one or more tests">
                <option v-for="test in adminTestCatalog" :key="test.key" :value="test.key">
                  {{ test.title }}
                </option>
              </select>
              <button :disabled="!adminSelectedReportId || adminBusy || adminRunInProgress" @click="runAdminAnalysis">
                {{ adminRunInProgress ? "Running..." : "Trigger run" }}
              </button>
            </div>
            <div class="admin-item" v-for="test in adminTestCatalog" :key="`desc-${test.key}`">
              <strong>{{ test.title }}</strong>: {{ test.plainEnglish }}
            </div>
            <div v-for="run in adminRuns" :key="run.id" class="admin-item">
              Run #{{ run.id }} · {{ run.status }} · {{ new Date(run.created_at).toLocaleString() }}
            </div>
          </section>

          <section v-else-if="adminActiveTab === 'overview'" class="admin-panel">
            <pre>{{ adminDashboard }}</pre>
          </section>

          <section v-else-if="adminActiveTab === 'dm_journey'" class="admin-panel">
            <div v-for="stage in compiledDmStages" :key="String(stage.id)" class="admin-item">
              DM-{{ stage.stage_number }}: {{ stage.stage_name }}
            </div>
          </section>

          <section v-else-if="adminActiveTab === 'video_journey'" class="admin-panel">
            <div v-for="stage in compiledVideoStages" :key="String(stage.id)" class="admin-item">
              Video-{{ stage.stage_number }}: {{ stage.stage_name }}
            </div>
          </section>

          <section v-else-if="adminActiveTab === 'verification_matrix'" class="admin-panel">
            <div v-for="item in compiledVerification" :key="String(item.id)" class="admin-item">
              {{ item.stage_label }} — {{ item.expected_security_property }}
            </div>
          </section>

          <section v-else-if="adminActiveTab === 'scope_coverage'" class="admin-panel">
            <div v-for="item in compiledScopeCoverage" :key="String(item.id)" class="admin-item">
              {{ item.area }} · {{ item.present_in_implementation ? 'present' : 'unknown/unverified' }}
            </div>
          </section>

          <section v-else-if="adminActiveTab === 'logging_design'" class="admin-panel">
            <div v-for="item in compiledLoggingDesign" :key="String(item.id)" class="admin-item">
              {{ item.field_name }} → {{ item.classification }}
            </div>
          </section>

          <section v-else-if="adminActiveTab === 'threat_model'" class="admin-panel">
            <div v-for="item in compiledThreatModel" :key="String(item.id)" class="admin-item">
              {{ item.threat }} · {{ item.severity }}
            </div>
          </section>

          <section v-else-if="adminActiveTab === 'gaps_next_tests'" class="admin-panel">
            <h4>Top Gaps</h4>
            <div v-for="item in compiledGaps" :key="`gap-${String(item.id)}`" class="admin-item">
              {{ item.rank }}. {{ item.title }}
            </div>
            <h4>Next Tests</h4>
            <div v-for="item in compiledNextTests" :key="`test-${String(item.id)}`" class="admin-item">
              {{ item.priority }} · {{ item.name }}
            </div>
          </section>

          <section v-else-if="adminActiveTab === 'reality_check'" class="admin-panel">
            <div v-for="(value, key) in compiledReality" :key="key" class="admin-item">
              <strong>{{ key }}</strong>: {{ value }}
            </div>
          </section>

          <section v-else-if="adminActiveTab === 'evidence_snapshots'" class="admin-panel">
            <button class="ghost" @click="createSnapshot">Create snapshot</button>
            <div v-for="item in adminSnapshots" :key="String(item.id)" class="admin-item">
              Snapshot #{{ item.id }} · {{ item.payload_sha256 }}
              <button class="ghost" @click="verifySnapshot(Number(item.id))">Verify</button>
              <div v-if="adminSnapshotVerify[Number(item.id)]">
                match: {{ adminSnapshotVerify[Number(item.id)].match }}
              </div>
            </div>
          </section>

          <section v-else-if="adminActiveTab === 'audit_trail'" class="admin-panel">
            <div v-for="item in adminAuditEvents" :key="String(item.id)" class="admin-item">
              {{ item.action }} · {{ item.created_at }}
            </div>
          </section>
        </section>
      </section>
    </main>
  </div>
</template>
