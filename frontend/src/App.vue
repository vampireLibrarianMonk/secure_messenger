<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useAuthStore, type NotificationPreferencePayload } from "./stores/auth";
import { useChatStore } from "./stores/chat";
import { useSecurityStore } from "./stores/security";
import { useVideoStore } from "./stores/video";
import { apiRequest } from "./lib/api";
import { decryptFile, encryptFile, encryptText, exportPublicKey, generateConversationKey, generateIdentityKeypair } from "./lib/crypto";
import AdminTestLabPanel from "./components/AdminTestLabPanel.vue";
import type { Attachment } from "./types";

interface TestLabBootstrapResponse {
  roles: string[];
  is_security_admin: boolean;
  can_access_test_lab: boolean;
  environment: {
    current: string;
    allowed: string[];
    is_allowed: boolean;
  };
  feature_flags: Record<string, boolean>;
  policy_limits: {
    max_active_admins: number;
    max_active_test_users_default: number;
    max_active_test_users_group_enabled: number;
  };
  governance_status: {
    active_admin_accounts: number;
    max_active_admins: number;
    active_test_users: number;
    max_active_test_users: number;
    group_testing_slot_enabled: boolean;
    group_testing_slot_usage: number;
    admin_limit_compliant: boolean;
    test_user_limit_compliant: boolean;
    active_admin_usernames: string[];
    active_test_usernames: string[];
  };
  stage: string;
}

const auth = useAuthStore();
const chat = useChatStore();
const security = useSecurityStore();
const video = useVideoStore();

const username = ref("");
const password = ref("");
const authError = ref("");
const showLoginPassword = ref(false);

const unlockPin = ref("");
const unlockError = ref("");
const showUnlockPin = ref(false);
const inactivityInput = ref(security.inactivitySeconds);

const draftMessage = ref("");
const composerError = ref("");
const createTitle = ref("");
const createKind = ref<"dm" | "group">("dm");
const createMembers = ref("");
const currentLoginPassword = ref("");
const newLoginPassword = ref("");
const confirmLoginPassword = ref("");
const loginPasswordMessage = ref("");
const loginPasswordError = ref("");
const showCurrentLoginPassword = ref(false);
const showNewLoginPassword = ref(false);
const showConfirmLoginPassword = ref(false);
const notificationPreferences = ref<NotificationPreferencePayload>({
  dm_sound: "chime",
  dm_document_sound: "pulse",
  video_ring_sound: "alert",
  chat_leave_sound: "soft",
});
const notificationMessage = ref("");
const notificationError = ref("");
const statusMessage = ref("");
const statusError = ref("");
const newPasscode = ref("");
const confirmPasscode = ref("");
const passcodeMessage = ref("");
const showNewPasscode = ref(false);
const showConfirmPasscode = ref(false);
const notificationsReady = ref(false);
const refreshingConversations = ref(false);
const nowTick = ref(Date.now());
const unreadByConversation = ref<Record<number, number>>({});
const memberNamesByConversation = ref<Record<number, Record<number, string>>>({});
const localVideoEl = ref<HTMLVideoElement | null>(null);
const remoteVideoEl = ref<HTMLVideoElement | null>(null);
const fileInputEl = ref<HTMLInputElement | null>(null);
const testLabBootstrap = ref<TestLabBootstrapResponse | null>(null);
const testLabError = ref("");
const showAdminTestLab = ref(false);

function nextMessageIndex(): number {
  // Backend currently validates against 32-bit signed max (2147483647),
  // so use unix seconds (safe through year 2038) instead of Date.now() ms.
  return Math.floor(Date.now() / 1000);
}

const activeMessageIds = new Set<number>();
let knownConversationIds = new Set<number>();
let knownMessageIds = new Set<number>();
let previousConversationIds = new Set<number>();
let outgoingRingTimer: number | null = null;
let incomingRingTimer: number | null = null;
let sharedAudioContext: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  const Impl = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Impl) return null;
  if (!sharedAudioContext || sharedAudioContext.state === "closed") {
    sharedAudioContext = new Impl();
  }
  if (sharedAudioContext.state === "suspended") {
    sharedAudioContext.resume();
  }
  return sharedAudioContext;
}

const notificationSoundOptions = [
  { value: "chime", label: "Digital Chime" },
  { value: "pulse", label: "Mobile Trill" },
  { value: "alert", label: "Classic Phone Ring" },
  { value: "soft", label: "Soft Bell" },
] as const;

const videoRingSoundOptions = [
  { value: "alert", label: "Classic Phone Ring" },
  { value: "pulse", label: "Modern Smartphone Ring" },
  { value: "chime", label: "Desk Bell" },
  { value: "soft", label: "Gentle Ring" },
] as const;

const activeConversation = computed(() =>
  chat.conversations.find((c) => c.id === chat.activeConversationId) ?? null,
);
const showStartCall = computed(() => Boolean(activeConversation.value) && !video.inCall && !video.hasIncomingCallIntent);
const showJoinCall = computed(() => Boolean(activeConversation.value) && !video.inCall && video.hasIncomingCallIntent);
const showEndCall = computed(() => video.inCall || video.status === "testing" || video.status === "active");
const showEndSignalingTest = computed(() => video.status === "testing");
const showLocalVideoPane = ref(true);
const showRemoteVideoPane = ref(true);
const visibleVideoPaneCount = computed(() => Number(showLocalVideoPane.value) + Number(showRemoteVideoPane.value));

function parseExpectedGroupEpochFromError(error: unknown): number | null {
  const message = error instanceof Error ? error.message : String(error);
  const match = message.match(/expected_group_epoch=(\d+)/);
  if (!match) return null;
  const parsed = Number.parseInt(match[1], 10);
  return Number.isFinite(parsed) ? parsed : null;
}

async function fetchCurrentGroupEpoch(conversationId: number): Promise<number> {
  if (!auth.accessToken) {
    throw new Error("Not authenticated");
  }
  const response = await apiRequest<{ conversation_id: number; group_epoch: number }>(
    `/conversations/${conversationId}/key-epoch/`,
    { token: auth.accessToken },
  );
  return response.group_epoch;
}

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
    mediaE2eeSupported: video.mediaE2eeSupported ? "yes" : "no",
    mediaE2eeEnabled: video.mediaE2eeEnabled ? "yes" : "no",
    mediaE2eeMode: video.mediaE2eeMode,
    mediaE2eeKeyFingerprint: video.mediaE2eeKeyFingerprint ?? "—",
    mediaE2eeKeyRotatedAt: video.mediaE2eeKeyRotatedAt
      ? new Date(video.mediaE2eeKeyRotatedAt).toLocaleTimeString()
      : "—",
    mediaE2eeRuntimeTransformClass: video.mediaE2eeRuntimeTransformClass,
    mediaE2eeRuntimeAttachmentCount: video.mediaE2eeRuntimeAttachmentCount,
  };
});

function bindActivityListeners() {
  const touch = () => security.touch();
  const warmAudio = () => {
    getAudioContext();
    window.removeEventListener("click", warmAudio);
    window.removeEventListener("keydown", warmAudio);
  };
  window.addEventListener("mousemove", touch);
  window.addEventListener("keydown", touch);
  window.addEventListener("click", warmAudio);
  window.addEventListener("keydown", warmAudio);
  return () => {
    window.removeEventListener("mousemove", touch);
    window.removeEventListener("keydown", touch);
    window.removeEventListener("click", warmAudio);
    window.removeEventListener("keydown", warmAudio);
  };
}

let unbindActivity = () => undefined;
let refreshTimer: number | null = null;
let countdownTimer: number | null = null;

const notificationCount = computed(() => Object.values(unreadByConversation.value).reduce((sum, v) => sum + v, 0));
const hasNotifications = computed(() => notificationCount.value > 0);
const canOpenAdminTestLab = computed(() => Boolean(testLabBootstrap.value?.can_access_test_lab));
const secondsUntilLock = computed(() => {
  if (security.locked) return 0;
  const elapsed = Math.floor((nowTick.value - security.lastActivityAt) / 1000);
  return Math.max(0, security.inactivitySeconds - elapsed);
});

function playPattern(steps: Array<{ frequency: number; durationMs: number; delayMs?: number }>) {
  try {
    const context = getAudioContext();
    if (!context) return;

    steps.forEach((step) => {
      const startAt = context.currentTime + ((step.delayMs ?? 0) / 1000);
      const endAt = startAt + step.durationMs / 1000;
      const oscillator = context.createOscillator();
      const gainNode = context.createGain();
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(step.frequency, startAt);
      gainNode.gain.setValueAtTime(0.001, startAt);
      gainNode.gain.exponentialRampToValueAtTime(0.12, startAt + 0.01);
      gainNode.gain.exponentialRampToValueAtTime(0.001, endAt);
      oscillator.connect(gainNode);
      gainNode.connect(context.destination);
      oscillator.start(startAt);
      oscillator.stop(endAt);
    });
  } catch {
    // best-effort only
  }
}

function playNamedSound(sound: string) {
  switch (sound) {
    case "pulse":
      playPattern([
        { frequency: 710, durationMs: 130 },
        { frequency: 790, durationMs: 130, delayMs: 150 },
        { frequency: 870, durationMs: 130, delayMs: 320 },
      ]);
      break;
    case "alert":
      playPattern([
        { frequency: 440, durationMs: 180 },
        { frequency: 495, durationMs: 180, delayMs: 210 },
        { frequency: 440, durationMs: 180, delayMs: 820 },
        { frequency: 495, durationMs: 180, delayMs: 1030 },
      ]);
      break;
    case "soft":
      playPattern([
        { frequency: 540, durationMs: 220 },
        { frequency: 620, durationMs: 180, delayMs: 250 },
      ]);
      break;
    case "chime":
    default:
      playPattern([
        { frequency: 880, durationMs: 170 },
        { frequency: 1040, durationMs: 150, delayMs: 190 },
      ]);
      break;
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
  playPattern([{ frequency: 740, durationMs: 220 }]);
  outgoingRingTimer = window.setInterval(() => {
    playPattern([{ frequency: 740, durationMs: 220 }]);
  }, 1500);
}

function startIncomingRing() {
  if (incomingRingTimer !== null) return;
  playNamedSound(notificationPreferences.value.video_ring_sound);
  incomingRingTimer = window.setInterval(() => {
    playNamedSound(notificationPreferences.value.video_ring_sound);
  }, 2000);
}

function triggerNotification(conversationId: number, kind: "dm" | "document" = "dm", increment = 1, isIncoming = true) {
  // Only increment unread count if the user is not actively viewing this conversation
  if (conversationId !== chat.activeConversationId) {
    unreadByConversation.value[conversationId] = (unreadByConversation.value[conversationId] ?? 0) + increment;
  }
  
  // Always play sound for incoming messages if notifications are ready
  if (notificationsReady.value && isIncoming) {
    playNamedSound(kind === "document" ? notificationPreferences.value.dm_document_sound : notificationPreferences.value.dm_sound);
  }
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
        triggerNotification(conversation.id, "dm", 1);
      }

      // Detect new messages in existing (non-active) conversations
      for (const conversation of chat.conversations) {
        if (conversation.id === chat.activeConversationId) continue;
        if (!conversation.last_message_id) continue;
        if (knownMessageIds.has(conversation.last_message_id)) continue;
        if (conversation.last_message_sender === auth.user?.id) {
          knownMessageIds.add(conversation.last_message_id);
          continue;
        }
        knownMessageIds.add(conversation.last_message_id);
        triggerNotification(conversation.id, "dm", 1, true);
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
  notificationPreferences.value = await auth.loadNotificationPreferences();
  await loadTestLabBootstrap();
  loadSeenNotificationState();
  await ensureDeviceRegistration();
  await refreshConversations();
  if (chat.activeConversationId) {
    await chat.loadMessages(chat.activeConversationId);
  }
}

async function loadTestLabBootstrap() {
  if (!auth.accessToken) return;
  testLabError.value = "";
  try {
    testLabBootstrap.value = await apiRequest<TestLabBootstrapResponse>("/test-lab/bootstrap/", {
      token: auth.accessToken,
    });
  } catch (error) {
    testLabBootstrap.value = null;
    testLabError.value = error instanceof Error ? error.message : "Failed to load test-lab guardrails";
  }
}

function openAdminTestLab() {
  if (!canOpenAdminTestLab.value) {
    testLabError.value = "Admin Test Lab is unavailable for this account or environment.";
    return;
  }
  testLabError.value = "";
  showAdminTestLab.value = true;
}

function closeAdminTestLab() {
  showAdminTestLab.value = false;
}

async function submitAuth() {
  authError.value = "";
  notificationsReady.value = false;
  try {
    await auth.login(username.value, password.value);
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
  showAdminTestLab.value = false;
  testLabBootstrap.value = null;
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
  showAdminTestLab.value = false;
  testLabBootstrap.value = null;
  await auth.logout();
}

async function updateLoginPassword() {
  loginPasswordMessage.value = "";
  loginPasswordError.value = "";

  if (!currentLoginPassword.value || !newLoginPassword.value || !confirmLoginPassword.value) {
    loginPasswordError.value = "All login password fields are required.";
    return;
  }

  if (newLoginPassword.value !== confirmLoginPassword.value) {
    loginPasswordError.value = "New login passwords do not match.";
    return;
  }

  try {
    const response = await auth.changePassword(
      currentLoginPassword.value,
      newLoginPassword.value,
      confirmLoginPassword.value,
    );
    currentLoginPassword.value = "";
    newLoginPassword.value = "";
    confirmLoginPassword.value = "";
    loginPasswordMessage.value = response.detail;
    await logout();
  } catch (error) {
    loginPasswordError.value = error instanceof Error ? error.message : "Failed to update login password";
  }
}

function previewNotificationSound(kind: keyof NotificationPreferencePayload) {
  playNamedSound(notificationPreferences.value[kind]);
}

async function saveNotificationPreferences() {
  notificationMessage.value = "";
  notificationError.value = "";
  try {
    notificationPreferences.value = await auth.saveNotificationPreferences(notificationPreferences.value);
    notificationMessage.value = "Notification sounds updated.";
  } catch (error) {
    notificationError.value = error instanceof Error ? error.message : "Failed to save notification sounds";
  }
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

async function onConversationSelectionChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  const selectedConversationId = Number.parseInt(target.value, 10);
  if (!Number.isFinite(selectedConversationId)) return;
  await selectConversation(selectedConversationId);
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

function endSignalingTest() {
  video.endSignalingTest();
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
    const aadPayload: Record<string, unknown> = { kind: "text", shared_key: key };
    if (activeConversation.value?.kind === "group") {
      aadPayload.group_epoch = await fetchCurrentGroupEpoch(chat.activeConversationId);
    }

    const attemptSend = async (aad: Record<string, unknown>) =>
      apiRequest("/messages/", {
        method: "POST",
        token: auth.accessToken,
        body: {
          conversation: chat.activeConversationId,
          ciphertext: encrypted.ciphertext,
          nonce: encrypted.nonce,
          aad: JSON.stringify(aad),
          message_index: nextMessageIndex(),
        },
      });

    try {
      await attemptSend(aadPayload);
    } catch (error) {
      const expectedGroupEpoch = parseExpectedGroupEpochFromError(error);
      if (activeConversation.value?.kind === "group" && expectedGroupEpoch !== null) {
        await attemptSend({ ...aadPayload, group_epoch: expectedGroupEpoch });
      } else {
        throw error;
      }
    }

    await refreshCurrentConversationMessages();
    draftMessage.value = "";
    
    // Removed outgoing message sound to fix asymmetry logic
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
    const aadPayload: Record<string, unknown> = { kind: "attachment", shared_key: key };
    if (activeConversation.value?.kind === "group") {
      aadPayload.group_epoch = await fetchCurrentGroupEpoch(chat.activeConversationId);
    }

    const sendAttachmentMarker = async (aad: Record<string, unknown>) =>
      apiRequest<{ id: number }>("/messages/", {
        method: "POST",
        token: auth.accessToken,
        body: {
          conversation: chat.activeConversationId,
          ciphertext: marker.ciphertext,
          nonce: marker.nonce,
          aad: JSON.stringify(aad),
          message_index: nextMessageIndex(),
        },
      });

    let message: { id: number };
    try {
      message = await sendAttachmentMarker(aadPayload);
    } catch (error) {
      const expectedGroupEpoch = parseExpectedGroupEpochFromError(error);
      if (activeConversation.value?.kind === "group" && expectedGroupEpoch !== null) {
        message = await sendAttachmentMarker({ ...aadPayload, group_epoch: expectedGroupEpoch });
      } else {
        throw error;
      }
    }

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
    
    // Removed outgoing file upload sound to fix asymmetry logic
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
    const attachmentDownloadUrl = `${apiBase}/attachments/${attachment.id}/download/`;

    const response = await fetch(attachmentDownloadUrl, {
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
  const createdConversationId = chat.activeConversationId;
  if (createdConversationId) {
    security.setConversationKey(createdConversationId, key);
    await selectConversation(createdConversationId);
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

async function leaveActiveConversation() {
  if (!chat.activeConversationId) return;
  const confirmed = window.confirm("Leave this conversation? You will no longer receive messages or be able to participate.");
  if (!confirmed) return;
  
  statusMessage.value = "";
  statusError.value = "";
  
  try {
    await apiRequest(`/conversations/${chat.activeConversationId}/leave/`, {
      method: "POST",
      token: auth.accessToken,
    });
    
    playNamedSound(notificationPreferences.value.chat_leave_sound);
    statusMessage.value = "Left conversation successfully.";
    
    await refreshConversations();
  } catch (error) {
    statusError.value = error instanceof Error ? error.message : "Failed to leave conversation";
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
    if (!auth.isAuthenticated) return;
    // Continue refreshing conversations even when locked to maintain notification counts
    await refreshConversations();
    if (!security.locked) {
      await refreshCurrentConversationMessages();
    }
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
    if (notificationsReady.value && previousConversationIds.size > 0) {
      const removed = [...previousConversationIds].filter((id) => !allowed.has(id));
      if (removed.length > 0) {
        playNamedSound(notificationPreferences.value.chat_leave_sound);
      }
    }
    for (const key of Object.keys(unreadByConversation.value)) {
      const id = Number(key);
      if (!allowed.has(id)) {
        delete unreadByConversation.value[id];
      }
    }
    previousConversationIds = allowed;
  },
  { deep: true },
);

// Helper to parse whether a message is an attachment
function isMessageDocument(message: any): boolean {
  return Boolean(message.attachments?.length) || (message.plaintext && message.plaintext.startsWith("[file]"));
}

watch(
  () => chat.messagesByConversation,
  (messagesMap) => {
    let hasNewIncoming = false;
    for (const [convIdStr, messages] of Object.entries(messagesMap)) {
      const convId = Number(convIdStr);
      if (!messages || !Array.isArray(messages)) continue;

      // Extract unseen messages specific to this array
      const unseenMessages = messages.filter((m) => !knownMessageIds.has(m.id));
      
      // Of those unseen, filter for actual new incoming messages (from someone else)
      const newIncoming = unseenMessages.filter((m) => m.sender !== auth.user?.id);

      // Track ALL unseen messages so we don't process them again
      unseenMessages.forEach((m) => knownMessageIds.add(m.id));

      // Only trigger sounds/badges if notifications are ready AND we actually have incoming messages
      if (newIncoming.length > 0 && notificationsReady.value) {
        hasNewIncoming = true;
        for (const message of newIncoming) {
          const isDocumentEvent = Boolean(message.attachments?.length) || (message.plaintext && message.plaintext.startsWith("[file]"));
          triggerNotification(convId, isDocumentEvent ? "document" : "dm", 1, true);
        }
      }
    }

    // Save state if we processed new incoming messages OR new outgoing messages
    saveSeenNotificationState();
  },
  { deep: true },
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
    // Clear unread count when switching to this conversation
    if (conversationId && unreadByConversation.value[conversationId]) {
      delete unreadByConversation.value[conversationId];
    }
  },
);

// We still need to track active message IDs for the UI loop
watch(
  () => chat.activeMessages,
  (messages) => {
    activeMessageIds.clear();
    messages.forEach((m) => activeMessageIds.add(m.id));
  },
  { deep: true }
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

defineExpose({
  playNamedSound,
  playPattern,
  triggerNotification,
  refreshConversations,
  notificationsReady,
  notificationPreferences,
  notificationSoundOptions,
  videoRingSoundOptions,
  unreadByConversation,
});
</script>

<template>
  <div class="app" @click="security.touch()">
    <header class="topbar">
      <h1>Secure Messenger</h1>
      <div v-if="auth.user" class="topbar-actions">
        <span class="muted">{{ auth.user.username }}</span>
        <button class="ghost" :disabled="!canOpenAdminTestLab" @click="openAdminTestLab">Admin Test Lab</button>
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
      <h2>Sign in</h2>
      <input v-model="username" placeholder="Username" />
      <div class="password-field-row">
        <input
          v-model="password"
          :type="showLoginPassword ? 'text' : 'password'"
          placeholder="Password"
          @keydown.enter="submitAuth"
        />
        <button class="ghost password-toggle" type="button" @click="showLoginPassword = !showLoginPassword">
          {{ showLoginPassword ? "🙈" : "👁" }}
        </button>
      </div>
      <button @click="submitAuth">Login</button>
      <p v-if="authError" class="error">{{ authError }}</p>
    </section>

    <section v-else-if="security.locked" class="card lock-screen">
      <h2>Session Locked</h2>
      <p>Enter passcode to restore in-memory keys and continue. Default passcode is <strong>1234</strong>.</p>
      <div class="password-field-row">
        <input
          v-model="unlockPin"
          :type="showUnlockPin ? 'text' : 'password'"
          placeholder="Passcode"
          @keydown.enter="unlock"
        />
        <button class="ghost password-toggle" type="button" @click="showUnlockPin = !showUnlockPin">
          {{ showUnlockPin ? "🙈" : "👁" }}
        </button>
      </div>
      <button @click="unlock">Unlock</button>
      <button class="ghost" @click="resetLockedSession">Reset locked session</button>
      <p v-if="unlockError" class="error">{{ unlockError }}</p>
    </section>

    <section v-else-if="showAdminTestLab" class="admin-test-lab-wrapper">
      <AdminTestLabPanel
        v-if="testLabBootstrap"
        :bootstrap="testLabBootstrap"
        :access-token="auth.accessToken ?? undefined"
        @close="closeAdminTestLab"
      />
      <article v-else class="card">
        <h2>Admin Secure Test Lab</h2>
        <p class="error">{{ testLabError || "Unable to load test-lab bootstrap data." }}</p>
        <button class="ghost" @click="closeAdminTestLab">Back to Messenger</button>
      </article>
    </section>

    <main v-else class="layout">
      <aside class="sidebar card">
        <h3>Conversations</h3>
        <label class="conversation-select-label" for="conversation-select">Select conversation</label>
        <select
          id="conversation-select"
          class="conversation-select"
          :value="String(chat.activeConversationId ?? '')"
          size="8"
          @change="onConversationSelectionChange"
        >
          <option v-if="chat.conversations.length === 0" value="" disabled>No conversations yet</option>
          <option v-for="conversation in chat.conversations" :key="conversation.id" :value="String(conversation.id)">
            {{ conversation.title || `${conversation.kind} #${conversation.id}` }}{{ unreadByConversation[conversation.id] ? ` (${unreadByConversation[conversation.id]})` : '' }}
          </option>
        </select>
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

        <details class="new-conversation settings-collapsible">
          <summary>Notification sounds</summary>
          <div class="settings-content">
            <label>
              DM message
              <div class="inline-preference-row">
                <select v-model="notificationPreferences.dm_sound">
                  <option v-for="option in notificationSoundOptions" :key="`dm-${option.value}`" :value="option.value">{{ option.label }}</option>
                </select>
                <button class="ghost" type="button" @click="previewNotificationSound('dm_sound')">Preview</button>
              </div>
            </label>
            <label>
              DM document/file
              <div class="inline-preference-row">
                <select v-model="notificationPreferences.dm_document_sound">
                  <option v-for="option in notificationSoundOptions" :key="`doc-${option.value}`" :value="option.value">{{ option.label }}</option>
                </select>
                <button class="ghost" type="button" @click="previewNotificationSound('dm_document_sound')">Preview</button>
              </div>
            </label>
            <label>
              Video incoming ring
              <div class="inline-preference-row">
                <select v-model="notificationPreferences.video_ring_sound">
                  <option v-for="option in videoRingSoundOptions" :key="`video-${option.value}`" :value="option.value">{{ option.label }}</option>
                </select>
                <button class="ghost" type="button" @click="previewNotificationSound('video_ring_sound')">Preview</button>
              </div>
            </label>
            <label>
              User left chat
              <div class="inline-preference-row">
                <select v-model="notificationPreferences.chat_leave_sound">
                  <option v-for="option in notificationSoundOptions" :key="`leave-${option.value}`" :value="option.value">{{ option.label }}</option>
                </select>
                <button class="ghost" type="button" @click="previewNotificationSound('chat_leave_sound')">Preview</button>
              </div>
            </label>
            <button @click="saveNotificationPreferences">Save notification sounds</button>
            <p v-if="notificationMessage" class="muted">{{ notificationMessage }}</p>
            <p v-if="notificationError" class="error">{{ notificationError }}</p>
          </div>
        </details>

        <details class="new-conversation settings-collapsible">
          <summary>Security settings</summary>
          <div class="settings-content">
            <h4>Change login password</h4>
            <div class="password-field-row">
              <input
                v-model="currentLoginPassword"
                :type="showCurrentLoginPassword ? 'text' : 'password'"
                placeholder="Current login password"
                autocomplete="current-password"
                name="current-login-password"
              />
              <button class="ghost password-toggle" type="button" @click="showCurrentLoginPassword = !showCurrentLoginPassword">
                {{ showCurrentLoginPassword ? "🙈" : "👁" }}
              </button>
            </div>
            <div class="password-field-row">
              <input
                v-model="newLoginPassword"
                :type="showNewLoginPassword ? 'text' : 'password'"
                placeholder="New login password"
                autocomplete="new-password"
                name="new-login-password"
              />
              <button class="ghost password-toggle" type="button" @click="showNewLoginPassword = !showNewLoginPassword">
                {{ showNewLoginPassword ? "🙈" : "👁" }}
              </button>
            </div>
            <div class="password-field-row">
              <input
                v-model="confirmLoginPassword"
                :type="showConfirmLoginPassword ? 'text' : 'password'"
                placeholder="Confirm new login password"
                autocomplete="new-password"
                name="confirm-login-password"
                @keydown.enter="updateLoginPassword"
              />
              <button class="ghost password-toggle" type="button" @click="showConfirmLoginPassword = !showConfirmLoginPassword">
                {{ showConfirmLoginPassword ? "🙈" : "👁" }}
              </button>
            </div>
            <button @click="updateLoginPassword">Update login password</button>
            <p v-if="loginPasswordMessage" class="muted">{{ loginPasswordMessage }}</p>
            <p v-if="loginPasswordError" class="error">{{ loginPasswordError }}</p>

            <h4>Change lock passcode</h4>
            <div class="password-field-row">
              <input
                v-model="newPasscode"
                :type="showNewPasscode ? 'text' : 'password'"
                placeholder="New passcode"
                autocomplete="new-password"
                name="new-lock-passcode"
              />
              <button class="ghost password-toggle" type="button" @click="showNewPasscode = !showNewPasscode">
                {{ showNewPasscode ? "🙈" : "👁" }}
              </button>
            </div>
            <div class="password-field-row">
              <input
                v-model="confirmPasscode"
                :type="showConfirmPasscode ? 'text' : 'password'"
                placeholder="Confirm passcode"
                autocomplete="new-password"
                name="confirm-lock-passcode"
              />
              <button class="ghost password-toggle" type="button" @click="showConfirmPasscode = !showConfirmPasscode">
                {{ showConfirmPasscode ? "🙈" : "👁" }}
              </button>
            </div>
            <button @click="updatePasscode">Update passcode</button>
            <p v-if="passcodeMessage" class="muted">{{ passcodeMessage }}</p>
          </div>
        </details>
      </aside>

      <section class="chat card">
        <header class="chat-head">
          <div>
            <h3>{{ activeConversation?.title || "No conversation selected" }}</h3>
            <button v-if="activeConversation" @click="leaveActiveConversation">Leave conversation</button>
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

        <div v-if="statusMessage || statusError" class="status-messages">
          <p v-if="statusMessage" class="muted">{{ statusMessage }}</p>
          <p v-if="statusError" class="error">{{ statusError }}</p>
        </div>

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
          <div class="video-grid" :class="{ 'single-pane': visibleVideoPaneCount === 1 }">
            <div v-if="showLocalVideoPane" class="video-frame">
              <video ref="localVideoEl" autoplay playsinline muted></video>
              <span>Local</span>
            </div>
            <div v-if="showRemoteVideoPane" class="video-frame">
              <video ref="remoteVideoEl" autoplay playsinline></video>
              <span>Remote</span>
            </div>
            <div v-if="visibleVideoPaneCount === 0" class="video-pane-hidden">Both video panes are hidden</div>
          </div>
          <div class="video-actions">
            <button v-if="showStartCall" @click="startVideoCall">Start Call</button>
            <button v-if="showJoinCall" class="join-btn" @click="joinVideoCall">Join Call</button>
            <button v-if="video.localStream" class="ghost" @click="toggleMic">{{ video.micEnabled ? "Mute" : "Unmute" }}</button>
            <button v-if="video.localStream" class="ghost" @click="toggleCamera">{{ video.cameraEnabled ? "Camera Off" : "Camera On" }}</button>
            <button class="ghost" @click="showLocalVideoPane = !showLocalVideoPane">{{ showLocalVideoPane ? "Hide Local Pane" : "Show Local Pane" }}</button>
            <button class="ghost" @click="showRemoteVideoPane = !showRemoteVideoPane">{{ showRemoteVideoPane ? "Hide Remote Pane" : "Show Remote Pane" }}</button>
            <button v-if="showEndCall" class="danger" @click="endVideoCall">End</button>
          </div>
          <div class="muted video-visibility-note">Pane visibility only affects this screen and does not mute/stop media transmission.</div>
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
            <div>Media E2EE supported: {{ formattedVideoDiagnostics.mediaE2eeSupported }}</div>
            <div>Media E2EE enabled: {{ formattedVideoDiagnostics.mediaE2eeEnabled }}</div>
            <div>Media E2EE mode: {{ formattedVideoDiagnostics.mediaE2eeMode }}</div>
            <div>Media E2EE key fingerprint: {{ formattedVideoDiagnostics.mediaE2eeKeyFingerprint }}</div>
            <div>Media E2EE key rotated: {{ formattedVideoDiagnostics.mediaE2eeKeyRotatedAt }}</div>
            <div>Media E2EE runtime transform class: {{ formattedVideoDiagnostics.mediaE2eeRuntimeTransformClass }}</div>
            <div>Media E2EE runtime attachments: {{ formattedVideoDiagnostics.mediaE2eeRuntimeAttachmentCount }}</div>
            <div v-if="video.diagnosticsError" class="error">{{ video.diagnosticsError }}</div>
          </div>
          <details class="video-debug">
            <summary>Debug tools</summary>
            <div class="video-actions">
              <button class="ghost" @click="runVideoStreamTest">Test Camera/Mic</button>
              <button class="ghost" @click="runSignalingTest">Signaling Test</button>
              <button v-if="showEndSignalingTest" class="danger" @click="endSignalingTest">End Signaling Test</button>
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
      </section>
    </main>

    <p v-if="testLabError && auth.isAuthenticated && !showAdminTestLab" class="error test-lab-error">{{ testLabError }}</p>
  </div>
</template>
