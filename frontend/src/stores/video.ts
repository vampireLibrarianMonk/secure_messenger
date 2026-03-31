import { defineStore } from "pinia";
import { videoWebsocketUrl } from "../lib/api";
import { generateConversationKey } from "../lib/crypto";
import { useAuthStore } from "./auth";

type CallStatus = "idle" | "testing" | "connecting" | "active" | "ended" | "error";

const transformedSenders = new WeakSet<RTCRtpSender>();
const transformedReceivers = new WeakSet<RTCRtpReceiver>();
let listenerReconnectTimer: number | null = null;

interface VideoState {
  ws: WebSocket | null;
  peer: RTCPeerConnection | null;
  loopbackPeer: RTCPeerConnection | null;
  localStream: MediaStream | null;
  remoteStream: MediaStream | null;
  pendingRemoteOffer: RTCSessionDescriptionInit | null;
  callConversationId: number | null;
  status: CallStatus;
  statusMessage: string;
  micEnabled: boolean;
  cameraEnabled: boolean;
  pendingIce: RTCIceCandidateInit[];
  clientId: string;
  hasIncomingCallIntent: boolean;
  playOutgoingRing: boolean;
  playIncomingRing: boolean;
  isDialing: boolean;
  diagnosticsEnabled: boolean;
  diagnostics: {
    localFps: number | null;
    remoteFps: number | null;
    localResolution: string | null;
    remoteResolution: string | null;
    outboundKbps: number | null;
    inboundKbps: number | null;
    packetLossPct: number | null;
    rttMs: number | null;
    updatedAt: number | null;
  };
  diagnosticsError: string;
  diagnosticsTimer: number | null;
  previousStats: {
    outboundBytes: number | null;
    inboundBytes: number | null;
    remoteFramesDecoded: number | null;
    timestampMs: number | null;
  };
  signalSequence: number;
  signalingSessionId: string | null;
  mediaE2eeSupported: boolean;
  mediaE2eeEnabled: boolean;
  mediaE2eeMode: "unavailable" | "scaffold" | "runtime_pipeline_active" | "runtime_obfuscation_active";
  mediaE2eeKeyFingerprint: string | null;
  mediaE2eeKeyRotatedAt: number | null;
  mediaE2eeRuntimeTransformClass: "none" | "xor_obfuscation_experimental";
  mediaE2eeRuntimeAttachmentCount: number;
  signalingTestSocket: WebSocket | null;
  signalingTestTimeout: number | null;
}

function parseIceServers(): RTCIceServer[] {
  const raw = import.meta.env.VITE_ICE_SERVERS;
  if (!raw) {
    return [{ urls: ["stun:stun.l.google.com:19302"] }];
  }
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.length > 0) {
      return parsed as RTCIceServer[];
    }
  } catch {
    // ignore invalid env and use fallback
  }
  return [{ urls: ["stun:stun.l.google.com:19302"] }];
}

const rtcConfig: RTCConfiguration = {
  iceServers: parseIceServers(),
};

function closeDetail(code?: number, reason?: string): string {
  const suffix = reason ? ` (${reason})` : "";
  if (code === 4401) return `unauthorized/token invalid [4401]${suffix}`;
  if (code === 4403) return `not a conversation member [4403]${suffix}`;
  if (typeof code === "number") return `closed [${code}]${suffix}`;
  return "closed";
}

export const useVideoStore = defineStore("video", {
  state: (): VideoState => ({
    ws: null,
    peer: null,
    loopbackPeer: null,
    localStream: null,
    remoteStream: null,
    pendingRemoteOffer: null,
    callConversationId: null,
    status: "idle",
    statusMessage: "Ready",
    micEnabled: true,
    cameraEnabled: true,
    pendingIce: [],
    clientId: crypto.randomUUID(),
    hasIncomingCallIntent: false,
    playOutgoingRing: false,
    playIncomingRing: false,
    isDialing: false,
    diagnosticsEnabled: false,
    diagnostics: {
      localFps: null,
      remoteFps: null,
      localResolution: null,
      remoteResolution: null,
      outboundKbps: null,
      inboundKbps: null,
      packetLossPct: null,
      rttMs: null,
      updatedAt: null,
    },
    diagnosticsError: "",
    diagnosticsTimer: null,
    previousStats: {
      outboundBytes: null,
      inboundBytes: null,
      remoteFramesDecoded: null,
      timestampMs: null,
    },
    signalSequence: 0,
    signalingSessionId: null,
    mediaE2eeSupported: false,
    mediaE2eeEnabled: false,
    mediaE2eeMode: "unavailable",
    mediaE2eeKeyFingerprint: null,
    mediaE2eeKeyRotatedAt: null,
    mediaE2eeRuntimeTransformClass: "none",
    mediaE2eeRuntimeAttachmentCount: 0,
    signalingTestSocket: null,
    signalingTestTimeout: null,
  }),
  getters: {
    inCall(state): boolean {
      return state.status === "connecting" || state.status === "active";
    },
  },
  actions: {
    clearListenerReconnect() {
      if (listenerReconnectTimer !== null) {
        window.clearTimeout(listenerReconnectTimer);
        listenerReconnectTimer = null;
      }
    },

    scheduleListenerReconnect(conversationId: number) {
      this.clearListenerReconnect();
      listenerReconnectTimer = window.setTimeout(() => {
        listenerReconnectTimer = null;
        if (!this.inCall && this.callConversationId === conversationId) {
          void this.listenForIncoming(conversationId);
        }
      }, 1000);
    },

    closeSignalingSocket() {
      this.clearListenerReconnect();
      this.ws?.close();
      this.ws = null;
      this.signalSequence = 0;
      this.signalingSessionId = null;
    },

    resetPeerState(preserveSocket = false, preservePendingOffer = false, preservePendingIce = false) {
      const cachedPendingOffer = preservePendingOffer ? this.pendingRemoteOffer : null;
      const cachedPendingIce = preservePendingIce ? [...this.pendingIce] : [];

      this.peer?.close();
      this.peer = null;
      this.loopbackPeer?.close();
      this.loopbackPeer = null;

      this.localStream?.getTracks().forEach((track) => track.stop());
      this.remoteStream?.getTracks().forEach((track) => track.stop());
      this.localStream = null;
      this.remoteStream = null;
      this.pendingRemoteOffer = cachedPendingOffer;

      this.pendingIce = cachedPendingIce;
      this.hasIncomingCallIntent = false;
      this.playOutgoingRing = false;
      this.playIncomingRing = false;
      this.isDialing = false;
      this.stopDiagnosticsLoop();
      this.mediaE2eeEnabled = false;
      this.mediaE2eeMode = this.mediaE2eeSupported ? "scaffold" : "unavailable";
      this.mediaE2eeKeyFingerprint = null;
      this.mediaE2eeKeyRotatedAt = null;
      this.mediaE2eeRuntimeTransformClass = "none";
      this.mediaE2eeRuntimeAttachmentCount = 0;

      if (!preserveSocket) {
        this.closeSignalingSocket();
        this.callConversationId = null;
      }
    },

    supportsInsertableStreams(): boolean {
      const senderProto = (
        window as typeof window & {
          RTCRtpSender?: { prototype?: { createEncodedStreams?: () => unknown; transform?: unknown } };
        }
      ).RTCRtpSender?.prototype;
      const receiverProto = (
        window as typeof window & {
          RTCRtpReceiver?: { prototype?: { createEncodedStreams?: () => unknown; transform?: unknown } };
        }
      ).RTCRtpReceiver?.prototype;

      const senderSupported = Boolean(
        senderProto &&
          (typeof senderProto.createEncodedStreams === "function" || "transform" in senderProto),
      );
      const receiverSupported = Boolean(
        receiverProto &&
          (typeof receiverProto.createEncodedStreams === "function" || "transform" in receiverProto),
      );
      return senderSupported && receiverSupported;
    },

    async initializeMediaE2eeScaffold() {
      const supported = this.supportsInsertableStreams();
      this.mediaE2eeSupported = supported;

      if (!supported) {
        this.mediaE2eeEnabled = false;
        this.mediaE2eeMode = "unavailable";
        this.mediaE2eeKeyFingerprint = null;
        this.mediaE2eeKeyRotatedAt = null;
        return;
      }

      const key = await generateConversationKey();
      this.mediaE2eeEnabled = true;
      this.mediaE2eeMode = "scaffold";
      this.mediaE2eeKeyFingerprint = key.slice(0, 16);
      this.mediaE2eeKeyRotatedAt = Date.now();
    },

    async rotateMediaE2eeScaffoldKey() {
      if (!this.mediaE2eeSupported) return;
      const key = await generateConversationKey();
      this.mediaE2eeEnabled = true;
      this.mediaE2eeMode = "scaffold";
      this.mediaE2eeKeyFingerprint = key.slice(0, 16);
      this.mediaE2eeKeyRotatedAt = Date.now();
    },

    xorObfuscateFrameData(data: ArrayBuffer, seed: number): void {
      const bytes = new Uint8Array(data);
      if (bytes.length === 0) return;
      for (let i = 0; i < bytes.length; i += 1) {
        const mask = (seed + i * 17) & 0xff;
        bytes[i] ^= mask;
      }
    },

    attachSenderTransform(sender: RTCRtpSender): boolean {
      if (transformedSenders.has(sender)) {
        return false;
      }
      const candidate = sender as RTCRtpSender & {
        createEncodedStreams?: () => { readable: ReadableStream<unknown>; writable: WritableStream<unknown> };
      };

      if (typeof candidate.createEncodedStreams !== "function") {
        return false;
      }

      try {
        const { readable, writable } = candidate.createEncodedStreams();
        const transform = new TransformStream<unknown, unknown>({
          transform: (frame, controller) => {
            const typedFrame = frame as { data?: ArrayBuffer; timestamp?: number };
            if (typedFrame.data instanceof ArrayBuffer) {
              const seed = Number((typedFrame.timestamp ?? 0) & 0xff) ^ (this.callConversationId ?? 0);
              this.xorObfuscateFrameData(typedFrame.data, seed);
            }
            controller.enqueue(frame);
          },
        });
        void readable.pipeThrough(transform).pipeTo(writable).catch(() => undefined);
        transformedSenders.add(sender);
        return true;
      } catch {
        return false;
      }
    },

    attachReceiverTransform(receiver: RTCRtpReceiver): boolean {
      if (transformedReceivers.has(receiver)) {
        return false;
      }
      const candidate = receiver as RTCRtpReceiver & {
        createEncodedStreams?: () => { readable: ReadableStream<unknown>; writable: WritableStream<unknown> };
      };

      if (typeof candidate.createEncodedStreams !== "function") {
        return false;
      }

      try {
        const { readable, writable } = candidate.createEncodedStreams();
        const transform = new TransformStream<unknown, unknown>({
          transform: (frame, controller) => {
            const typedFrame = frame as { data?: ArrayBuffer; timestamp?: number };
            if (typedFrame.data instanceof ArrayBuffer) {
              const seed = Number((typedFrame.timestamp ?? 0) & 0xff) ^ (this.callConversationId ?? 0);
              this.xorObfuscateFrameData(typedFrame.data, seed);
            }
            controller.enqueue(frame);
          },
        });
        void readable.pipeThrough(transform).pipeTo(writable).catch(() => undefined);
        transformedReceivers.add(receiver);
        return true;
      } catch {
        return false;
      }
    },

    activateRuntimeMediaE2eePipeline() {
      if (!this.peer || !this.mediaE2eeSupported) {
        return;
      }

      // Experimental XOR frame obfuscation is not interoperable enough yet
      // for reliable real-world video. Keep the scaffold capability metadata,
      // but do not attach runtime transforms during active calls.
      this.mediaE2eeEnabled = this.mediaE2eeSupported;
      this.mediaE2eeMode = this.mediaE2eeSupported ? "scaffold" : "unavailable";
      this.mediaE2eeRuntimeTransformClass = "none";
      this.mediaE2eeRuntimeAttachmentCount = 0;
      return;

      let attachedCount = 0;
      for (const sender of this.peer.getSenders()) {
        if (!sender.track) continue;
        if (sender.track.kind !== "audio" && sender.track.kind !== "video") continue;
        if (this.attachSenderTransform(sender)) {
          attachedCount += 1;
        }
      }

      for (const receiver of this.peer.getReceivers()) {
        if (this.attachReceiverTransform(receiver)) {
          attachedCount += 1;
        }
      }

      if (attachedCount > 0) {
        this.mediaE2eeEnabled = true;
        this.mediaE2eeMode = "runtime_obfuscation_active";
        this.mediaE2eeRuntimeTransformClass = "xor_obfuscation_experimental";
        this.mediaE2eeRuntimeAttachmentCount += attachedCount;
      }
    },

    setDiagnosticsEnabled(enabled: boolean) {
      this.diagnosticsEnabled = enabled;
      if (!enabled) {
        this.stopDiagnosticsLoop();
        return;
      }
      if (this.peer) {
        this.startDiagnosticsLoop();
      }
    },

    startDiagnosticsLoop() {
      if (!this.diagnosticsEnabled || !this.peer) return;
      if (this.diagnosticsTimer !== null) return;
      void this.collectDiagnostics();
      this.diagnosticsTimer = window.setInterval(() => {
        void this.collectDiagnostics();
      }, 1000);
    },

    stopDiagnosticsLoop() {
      if (this.diagnosticsTimer !== null) {
        window.clearInterval(this.diagnosticsTimer);
        this.diagnosticsTimer = null;
      }
      this.previousStats = {
        outboundBytes: null,
        inboundBytes: null,
        remoteFramesDecoded: null,
        timestampMs: null,
      };
    },

    async collectDiagnostics() {
      if (!this.peer) return;
      try {
        const stats = await this.peer.getStats();
        let localFps: number | null = null;
        let remoteFps: number | null = null;
        let localResolution: string | null = null;
        let remoteResolution: string | null = null;
        let outboundBytes: number | null = null;
        let inboundBytes: number | null = null;
        let packetsLost = 0;
        let packetsTotal = 0;
        let rttMs: number | null = null;

        for (const report of stats.values()) {
          if (report.type === "outbound-rtp" && report.kind === "video") {
            const r = report as RTCOutboundRtpStreamStats;
            outboundBytes = typeof r.bytesSent === "number" ? r.bytesSent : outboundBytes;
          }
          if (report.type === "inbound-rtp" && report.kind === "video") {
            const r = report as RTCInboundRtpStreamStats;
            inboundBytes = typeof r.bytesReceived === "number" ? r.bytesReceived : inboundBytes;
            if (typeof r.framesPerSecond === "number") {
              remoteFps = r.framesPerSecond;
            }
            packetsLost += typeof r.packetsLost === "number" ? r.packetsLost : 0;
            packetsTotal += typeof r.packetsReceived === "number" ? r.packetsReceived : 0;
          }
          if (report.type === "candidate-pair") {
            const r = report as RTCIceCandidatePairStats;
            if (r.state === "succeeded" && typeof r.currentRoundTripTime === "number") {
              rttMs = r.currentRoundTripTime * 1000;
            }
          }
        }

        const localTrack = this.localStream?.getVideoTracks()[0];
        if (localTrack) {
          const settings = localTrack.getSettings();
          localFps = typeof settings.frameRate === "number" ? settings.frameRate : null;
          if (settings.width && settings.height) {
            localResolution = `${settings.width}x${settings.height}`;
          }
        }

        const remoteTrack = this.remoteStream?.getVideoTracks()[0];
        if (remoteTrack) {
          const settings = remoteTrack.getSettings();
          if (settings.width && settings.height) {
            remoteResolution = `${settings.width}x${settings.height}`;
          }
        }

        const now = Date.now();
        const prevTs = this.previousStats.timestampMs;
        let outboundKbps: number | null = null;
        let inboundKbps: number | null = null;

        if (prevTs && outboundBytes !== null && this.previousStats.outboundBytes !== null) {
          const seconds = (now - prevTs) / 1000;
          if (seconds > 0) {
            outboundKbps = ((outboundBytes - this.previousStats.outboundBytes) * 8) / 1000 / seconds;
          }
        }
        if (prevTs && inboundBytes !== null && this.previousStats.inboundBytes !== null) {
          const seconds = (now - prevTs) / 1000;
          if (seconds > 0) {
            inboundKbps = ((inboundBytes - this.previousStats.inboundBytes) * 8) / 1000 / seconds;
          }
        }

        const packetLossPct = packetsTotal > 0 ? (packetsLost / (packetsTotal + packetsLost)) * 100 : null;

        this.diagnostics = {
          localFps,
          remoteFps,
          localResolution,
          remoteResolution,
          outboundKbps,
          inboundKbps,
          packetLossPct,
          rttMs,
          updatedAt: now,
        };
        this.diagnosticsError = "";
        this.previousStats = {
          outboundBytes,
          inboundBytes,
          remoteFramesDecoded: this.previousStats.remoteFramesDecoded,
          timestampMs: now,
        };
      } catch (error) {
        this.diagnosticsError = error instanceof Error ? error.message : "Diagnostics failed";
      }
    },

    async listenForIncoming(conversationId: number) {
      const auth = useAuthStore();
      if (!auth.accessToken) return;
      if (this.inCall) return;
      this.clearListenerReconnect();

      if (this.ws && this.ws.readyState === WebSocket.OPEN && this.callConversationId === conversationId) {
        return;
      }

      this.ws?.close();
      this.ws = null;
      this.callConversationId = conversationId;

      await new Promise<void>((resolve, reject) => {
        const signalingUrl = videoWebsocketUrl(conversationId, auth.accessToken!);
        const ws = new WebSocket(videoWebsocketUrl(conversationId, auth.accessToken!));
        let sessionReady = false;
        ws.onopen = () => {
          this.ws = ws;
          this.callConversationId = conversationId;
          this.signalSequence = 0;
          this.signalingSessionId = null;
        };
        ws.onerror = () => {
          reject(new Error("Incoming call listener failed to connect"));
        };
        ws.onmessage = async (event) => {
          const data = JSON.parse(event.data) as {
            type: "session" | "ready" | "offer" | "answer" | "ice" | "hangup" | "error";
            sender_client_id?: string;
            payload?: RTCSessionDescriptionInit | RTCIceCandidateInit | { ok: boolean } | { signaling_session_id: string };
            detail?: string;
          };
          if (data.type === "session") {
            const sessionPayload = data.payload as { signaling_session_id?: string } | undefined;
            this.signalingSessionId = sessionPayload?.signaling_session_id ?? null;
            if (!sessionReady && this.signalingSessionId) {
              sessionReady = true;
              if (!this.inCall) {
                this.status = "idle";
                this.statusMessage = "Ready";
              }
              resolve();
            }
            return;
          }
          if (data.type === "error") {
            this.status = "error";
            this.statusMessage = `Signaling error: ${data.detail ?? "unknown"}`;
            return;
          }
          if (data.sender_client_id && data.sender_client_id === this.clientId) {
            return;
          }

          if (data.type === "offer" && !this.inCall && !this.isDialing) {
            this.pendingRemoteOffer = data.payload as RTCSessionDescriptionInit;
            this.hasIncomingCallIntent = true;
            this.playIncomingRing = true;
            this.playOutgoingRing = false;
            this.statusMessage = "Incoming call...";
            return;
          }

          if (data.type === "ready" && !this.inCall && !this.isDialing) {
            this.hasIncomingCallIntent = true;
            this.playIncomingRing = true;
            this.playOutgoingRing = false;
            this.statusMessage = "Incoming call...";
            return;
          }

          await this.handleSignal(data.type, data.payload);
        };
        ws.onclose = () => {
          if (this.ws === ws) {
            this.ws = null;
            this.signalingSessionId = null;
            this.signalSequence = 0;
            if (!this.inCall && this.callConversationId === conversationId) {
              this.scheduleListenerReconnect(conversationId);
            }
          }
        };
      }).catch((error) => {
        this.status = "error";
        this.statusMessage = error instanceof Error ? error.message : "Incoming listener failed";
      });
    },

    async runSignalingTest(conversationId: number) {
      const auth = useAuthStore();
      if (!auth.accessToken) {
        this.status = "error";
        this.statusMessage = "Signaling test failed: not authenticated";
        return;
      }

      this.status = "testing";
      this.statusMessage = "Running signaling test...";

      const testClientId = `signal-test-${crypto.randomUUID()}`;
      this.signalingTestSocket?.close();
      if (this.signalingTestTimeout !== null) {
        window.clearTimeout(this.signalingTestTimeout);
      }

      const ws = new WebSocket(videoWebsocketUrl(conversationId, auth.accessToken));
      this.signalingTestSocket = ws;
      this.signalingTestTimeout = null;

      await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(() => {
          ws.close();
          reject(new Error("Signaling test timeout (no echo received)"));
        }, 5000);
        this.signalingTestTimeout = timeout;
        let settled = false;
        let signalingSessionId: string | null = null;

        const failOnce = (error: Error) => {
          if (settled) return;
          settled = true;
          window.clearTimeout(timeout);
          this.signalingTestTimeout = null;
          if (this.signalingTestSocket === ws) {
            this.signalingTestSocket = null;
          }
          try {
            ws.close();
          } catch {
            // ignore
          }
          reject(error);
        };

        const passOnce = () => {
          if (settled) return;
          settled = true;
          window.clearTimeout(timeout);
          this.signalingTestTimeout = null;
          if (this.signalingTestSocket === ws) {
            this.signalingTestSocket = null;
          }
          ws.close();
          resolve();
        };

        ws.onopen = () => {
          // Wait for server-issued signaling session before transmitting.
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as {
              type?: string;
              sender_client_id?: string;
              detail?: string;
              payload?: { signaling_session_id?: string };
            };
            if (data.type === "session") {
              signalingSessionId = data.payload?.signaling_session_id ?? null;
              if (signalingSessionId) {
                ws.send(
                  JSON.stringify({
                    type: "ready",
                    payload: { signal_test: true, ts: Date.now() },
                    client_id: testClientId,
                    sequence: 1,
                    signaling_session_id: signalingSessionId,
                  }),
                );
              }
              return;
            }
            if (data.type === "error") {
              failOnce(new Error(`Signaling rejected: ${data.detail ?? "unknown"}`));
              return;
            }
            if (data.type === "ready" && data.sender_client_id === testClientId) {
              passOnce();
            }
          } catch {
            // ignore malformed test messages
          }
        };

        ws.onerror = () => {
          // wait for onclose when possible to get authz/error code
          window.setTimeout(() => {
            if (!settled) {
              failOnce(new Error("Signaling websocket connection failed"));
            }
          }, 120);
        };

        ws.onclose = (event) => {
          if (settled) return;
          failOnce(new Error(`Signaling websocket ${closeDetail(event.code, event.reason)}`));
        };
      })
        .then(() => {
          this.status = "idle";
          this.statusMessage = "Signaling test passed ✅";
        })
        .catch((error) => {
          this.status = "error";
          this.statusMessage = error instanceof Error ? error.message : "Signaling test failed";
        });
    },

    endSignalingTest() {
      if (this.signalingTestTimeout !== null) {
        window.clearTimeout(this.signalingTestTimeout);
        this.signalingTestTimeout = null;
      }

      if (this.signalingTestSocket) {
        try {
          this.signalingTestSocket.close();
        } catch {
          // ignore
        }
      }
      this.signalingTestSocket = null;

      if (this.status === "testing") {
        this.status = "ended";
        this.statusMessage = "Signaling test ended.";
      }
    },

    async startLoopbackTest() {
      try {
        await this.endCall(false);
        this.status = "connecting";
        this.statusMessage = "Starting local loopback test (no signaling)...";
        await this.ensureLocalStream();

        const caller = new RTCPeerConnection(rtcConfig);
        const callee = new RTCPeerConnection(rtcConfig);
        this.peer = caller;
        this.loopbackPeer = callee;

        this.remoteStream = new MediaStream();

        this.localStream?.getTracks().forEach((track) => {
          caller.addTrack(track, this.localStream!);
        });

        caller.onicecandidate = async (event) => {
          if (event.candidate) {
            await callee.addIceCandidate(event.candidate);
          }
        };
        callee.onicecandidate = async (event) => {
          if (event.candidate) {
            await caller.addIceCandidate(event.candidate);
          }
        };

        callee.ontrack = (event) => {
          const stream = this.remoteStream ?? new MediaStream();
          this.remoteStream = stream;
          event.streams[0]?.getTracks().forEach((track) => {
            if (!stream.getTracks().some((t) => t.id === track.id)) {
              stream.addTrack(track);
            }
          });
        };

        const offer = await caller.createOffer();
        await caller.setLocalDescription(offer);
        await callee.setRemoteDescription(offer);

        const answer = await callee.createAnswer();
        await callee.setLocalDescription(answer);
        await caller.setRemoteDescription(answer);

        this.status = "active";
        this.statusMessage = "Loopback test active (signaling bypassed).";
      } catch (error) {
        this.status = "error";
        this.statusMessage = error instanceof Error ? error.message : "Loopback test failed";
      }
    },

    async startStreamTest() {
      try {
        if (this.status === "testing") return;
        this.status = "testing";
        this.statusMessage = "Requesting camera/microphone...";
        await this.ensureLocalStream();
        this.statusMessage = "Stream test running. Camera + mic are active.";
      } catch (error) {
        this.status = "error";
        this.statusMessage = error instanceof Error ? error.message : "Failed to start local stream test";
      }
    },

    async startCall(conversationId: number) {
      try {
        this.resetPeerState(true);
        this.status = "connecting";
        this.statusMessage = "Starting call...";
        this.callConversationId = conversationId;
        this.isDialing = true;
        this.playOutgoingRing = true;
        this.playIncomingRing = false;
        this.hasIncomingCallIntent = false;

        await this.ensureLocalStream();
        await this.connectSignaling(conversationId);
        await this.createPeerConnection(conversationId);

        const offer = await this.peer!.createOffer();
        await this.peer!.setLocalDescription(offer);
        this.sendSignal("offer", offer);
        this.statusMessage = "Offer sent. Waiting for answer...";
      } catch (error) {
        this.status = "error";
        this.statusMessage = error instanceof Error ? error.message : "Failed to start call";
      }
    },

    async joinCall(conversationId: number) {
      try {
        this.resetPeerState(true, true, true);
        this.status = "connecting";
        this.statusMessage = "Joining call...";
        this.callConversationId = conversationId;
        this.isDialing = false;
        this.playOutgoingRing = false;
        this.playIncomingRing = false;
        this.hasIncomingCallIntent = false;
        await this.ensureLocalStream();
        await this.connectSignaling(conversationId);
        await this.createPeerConnection(conversationId);

        if (this.pendingRemoteOffer) {
          await this.applyRemoteOffer(this.pendingRemoteOffer);
          this.pendingRemoteOffer = null;
          return;
        }

        this.sendSignal("ready", { ok: true });
      } catch (error) {
        this.status = "error";
        this.statusMessage = error instanceof Error ? error.message : "Failed to join call";
      }
    },

    async connectSignaling(conversationId: number) {
      const auth = useAuthStore();
      if (!auth.accessToken) {
        throw new Error("Not authenticated");
      }

      const signalingUrl = videoWebsocketUrl(conversationId, auth.accessToken!);

      if (this.ws && this.ws.readyState === WebSocket.OPEN && this.callConversationId === conversationId) {
        return;
      }

      this.closeSignalingSocket();

      await new Promise<void>((resolve, reject) => {
        const ws = new WebSocket(signalingUrl);
        let sessionReady = false;
        ws.onopen = () => {
          this.ws = ws;
          this.callConversationId = conversationId;
          this.signalSequence = 0;
          this.signalingSessionId = null;
        };
        ws.onerror = () => {
          // onclose often carries the useful code (4401/4403)
          window.setTimeout(() => {
            if (!this.ws) {
              reject(new Error("Video signaling connection failed"));
            }
          }, 120);
        };
        ws.onmessage = async (event) => {
          const data = JSON.parse(event.data) as {
            type: "session" | "ready" | "offer" | "answer" | "ice" | "hangup" | "error";
            sender_id?: number;
            sender_client_id?: string;
            payload?: RTCSessionDescriptionInit | RTCIceCandidateInit | { ok: boolean } | { signaling_session_id: string };
            detail?: string;
          };
          if (data.type === "session") {
            const sessionPayload = data.payload as { signaling_session_id?: string } | undefined;
            this.signalingSessionId = sessionPayload?.signaling_session_id ?? null;
            if (!sessionReady && this.signalingSessionId) {
              sessionReady = true;
              resolve();
            }
            return;
          }
          if (data.type === "error") {
            this.status = "error";
            this.statusMessage = `Signaling error: ${data.detail ?? "unknown"}`;
            return;
          }
          if (data.sender_client_id && data.sender_client_id === this.clientId) {
            return;
          }
          await this.handleSignal(data.type, data.payload);
        };
        ws.onclose = (event) => {
          if (this.ws === ws) {
            this.ws = null;
            this.signalingSessionId = null;
            this.signalSequence = 0;
          }
          if (!this.ws) {
            reject(new Error(`Video signaling websocket ${closeDetail(event.code, event.reason)}`));
            return;
          }
          if (this.inCall) {
            this.status = "ended";
            this.statusMessage = `Call ended (signaling ${closeDetail(event.code, event.reason)}).`;
          }
        };
      });
    },

    async createPeerConnection(conversationId: number) {
      if (this.peer) return;
      const peer = new RTCPeerConnection(rtcConfig);
      this.peer = peer;

      await this.initializeMediaE2eeScaffold();

      this.remoteStream = new MediaStream();

      this.localStream?.getTracks().forEach((track) => {
        peer.addTrack(track, this.localStream!);
      });

      this.activateRuntimeMediaE2eePipeline();

      peer.ontrack = (event) => {
        this.activateRuntimeMediaE2eePipeline();
        const stream = this.remoteStream ?? new MediaStream();
        this.remoteStream = stream;

        const incomingTracks = event.streams[0]?.getTracks().length
          ? event.streams[0].getTracks()
          : [event.track];

        incomingTracks.forEach((track) => {
          if (!stream.getTracks().some((t) => t.id === track.id)) {
            stream.addTrack(track);
          }
        });
      };

      peer.onicecandidate = (event) => {
        if (event.candidate) {
          this.sendSignal("ice", event.candidate.toJSON());
        }
      };

      peer.onconnectionstatechange = () => {
        if (!peer.connectionState) return;
        if (peer.connectionState === "connected") {
          this.status = "active";
          this.statusMessage = "Secure video stream active";
          this.isDialing = false;
          this.playOutgoingRing = false;
          this.playIncomingRing = false;
          this.hasIncomingCallIntent = false;
          this.startDiagnosticsLoop();
        } else if (["failed", "closed", "disconnected"].includes(peer.connectionState)) {
          this.status = "ended";
          this.statusMessage = "Call ended";
          this.isDialing = false;
          this.playOutgoingRing = false;
          this.playIncomingRing = false;
          this.hasIncomingCallIntent = false;
          this.stopDiagnosticsLoop();
        } else {
          this.statusMessage = `Connection: ${peer.connectionState}`;
        }
      };

      // keep linter happy about currently selected conversation
      this.callConversationId = conversationId;
    },

    async applyRemoteOffer(offer: RTCSessionDescriptionInit) {
      if (!this.peer) return;

      this.statusMessage = "Offer received. Creating answer...";
      await this.peer.setRemoteDescription(offer);
      const answer = await this.peer.createAnswer();
      await this.peer.setLocalDescription(answer);
      this.sendSignal("answer", answer);

      for (const ice of this.pendingIce) {
        await this.peer.addIceCandidate(ice);
      }
      this.pendingIce = [];
    },

    async handleSignal(type: "ready" | "offer" | "answer" | "ice" | "hangup", payload?: unknown) {
      if ((type === "ready" || type === "offer") && !this.inCall && !this.isDialing) {
        this.hasIncomingCallIntent = true;
        this.playIncomingRing = true;
        this.playOutgoingRing = false;
        this.statusMessage = "Incoming call...";

        // Wait for explicit Join action before processing SDP.
        if (type === "offer") {
          this.pendingRemoteOffer = payload as RTCSessionDescriptionInit;
          return;
        }
      }

      if (!this.peer && this.callConversationId) {
        await this.createPeerConnection(this.callConversationId);
      }
      if (!this.peer) return;

      if (type === "ready") {
        // If an offer was already created before the other side joined,
        // re-send it so local same-machine testing remains reliable.
        if (this.peer.signalingState === "have-local-offer" && this.peer.localDescription?.type === "offer") {
          this.sendSignal("offer", {
            type: this.peer.localDescription.type,
            sdp: this.peer.localDescription.sdp,
          });
          this.statusMessage = "Peer ready. Re-sent offer...";
          return;
        }

        if (this.peer.signalingState === "stable") {
          const offer = await this.peer.createOffer();
          await this.peer.setLocalDescription(offer);
          this.sendSignal("offer", offer);
          this.statusMessage = "Peer ready. Sent offer...";
        }
        return;
      }

      if (type === "offer") {
        await this.applyRemoteOffer(payload as RTCSessionDescriptionInit);
        return;
      }

      if (type === "answer") {
        await this.peer.setRemoteDescription(payload as RTCSessionDescriptionInit);
        this.statusMessage = "Answer received. Finalizing connection...";
        this.isDialing = false;
        this.playOutgoingRing = false;
        this.playIncomingRing = false;
        this.hasIncomingCallIntent = false;
        for (const ice of this.pendingIce) {
          await this.peer.addIceCandidate(ice);
        }
        this.pendingIce = [];
        return;
      }

      if (type === "ice") {
        const candidate = payload as RTCIceCandidateInit;
        if (this.peer.remoteDescription) {
          await this.peer.addIceCandidate(candidate);
        } else {
          this.pendingIce.push(candidate);
        }
        return;
      }

      if (type === "hangup") {
        await this.endCall(false);
      }
    },

    sendSignal(type: "ready" | "offer" | "answer" | "ice" | "hangup", payload: unknown) {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
      if (!this.signalingSessionId) return;
      this.signalSequence += 1;
      this.ws.send(
        JSON.stringify({
          type,
          payload,
          client_id: this.clientId,
          sequence: this.signalSequence,
          signaling_session_id: this.signalingSessionId,
        }),
      );
    },

    async ensureLocalStream() {
      if (this.localStream) return;
      this.localStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          frameRate: { ideal: 24, max: 30 },
        },
      });
      this.micEnabled = true;
      this.cameraEnabled = true;
    },

    toggleMic() {
      if (!this.localStream) return;
      this.micEnabled = !this.micEnabled;
      this.localStream.getAudioTracks().forEach((track) => {
        track.enabled = this.micEnabled;
      });
    },

    toggleCamera() {
      if (!this.localStream) return;
      this.cameraEnabled = !this.cameraEnabled;
      this.localStream.getVideoTracks().forEach((track) => {
        track.enabled = this.cameraEnabled;
      });
    },

    async endCall(notify = true) {
      const conversationId = this.callConversationId;
      if (notify) {
        this.sendSignal("hangup", { ended: true });
      }

      this.resetPeerState(false);
      this.status = "ended";
      this.statusMessage = "Call ended";
      if (conversationId !== null) {
        this.callConversationId = conversationId;
        await this.listenForIncoming(conversationId);
      } else {
        this.callConversationId = null;
        this.closeSignalingSocket();
      }
    },

    resetStatusIfIdle() {
      if (!this.localStream && !this.peer && !this.ws) {
        this.status = "idle";
        this.statusMessage = "Ready";
      }
    },
  },
});
