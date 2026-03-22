import { defineStore } from "pinia";
import { videoWebsocketUrl } from "../lib/api";
import { useAuthStore } from "./auth";

type CallStatus = "idle" | "testing" | "connecting" | "active" | "ended" | "error";

interface VideoState {
  ws: WebSocket | null;
  peer: RTCPeerConnection | null;
  loopbackPeer: RTCPeerConnection | null;
  localStream: MediaStream | null;
  remoteStream: MediaStream | null;
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
}

const rtcConfig: RTCConfiguration = {
  iceServers: [{ urls: ["stun:stun.l.google.com:19302"] }],
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
  }),
  getters: {
    inCall(state): boolean {
      return state.status === "connecting" || state.status === "active";
    },
  },
  actions: {
    async listenForIncoming(conversationId: number) {
      const auth = useAuthStore();
      if (!auth.accessToken) return;
      if (this.inCall) return;

      if (this.ws && this.ws.readyState === WebSocket.OPEN && this.callConversationId === conversationId) {
        return;
      }

      this.ws?.close();
      this.ws = null;
      this.callConversationId = conversationId;

      await new Promise<void>((resolve, reject) => {
        const ws = new WebSocket(videoWebsocketUrl(conversationId, auth.accessToken!));
        ws.onopen = () => {
          this.ws = ws;
          this.callConversationId = conversationId;
          if (!this.inCall) {
            this.status = "idle";
            this.statusMessage = "Ready";
          }
          resolve();
        };
        ws.onerror = () => reject(new Error("Incoming call listener failed to connect"));
        ws.onmessage = async (event) => {
          const data = JSON.parse(event.data) as {
            type: "ready" | "offer" | "answer" | "ice" | "hangup" | "error";
            sender_client_id?: string;
            payload?: RTCSessionDescriptionInit | RTCIceCandidateInit | { ok: boolean };
            detail?: string;
          };
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
        ws.onclose = () => {
          if (this.ws === ws) {
            this.ws = null;
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
      const ws = new WebSocket(videoWebsocketUrl(conversationId, auth.accessToken));

      await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(() => {
          ws.close();
          reject(new Error("Signaling test timeout (no echo received)"));
        }, 5000);
        let settled = false;

        const failOnce = (error: Error) => {
          if (settled) return;
          settled = true;
          window.clearTimeout(timeout);
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
          ws.close();
          resolve();
        };

        ws.onopen = () => {
          ws.send(JSON.stringify({
            type: "ready",
            payload: { signal_test: true, ts: Date.now() },
            client_id: testClientId,
          }));
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as { type?: string; sender_client_id?: string; detail?: string };
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
        await this.endCall(false);
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
        await this.endCall(false);
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

      if (this.ws && this.ws.readyState === WebSocket.OPEN && this.callConversationId === conversationId) {
        return;
      }

      this.ws?.close();
      this.ws = null;

      await new Promise<void>((resolve, reject) => {
        const ws = new WebSocket(videoWebsocketUrl(conversationId, auth.accessToken!));
        ws.onopen = () => {
          this.ws = ws;
          this.callConversationId = conversationId;
          resolve();
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
            type: "ready" | "offer" | "answer" | "ice" | "hangup" | "error";
            sender_id?: number;
            sender_client_id?: string;
            payload?: RTCSessionDescriptionInit | RTCIceCandidateInit | { ok: boolean };
            detail?: string;
          };
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
      this.pendingIce = [];

      this.remoteStream = new MediaStream();

      this.localStream?.getTracks().forEach((track) => {
        peer.addTrack(track, this.localStream!);
      });

      peer.ontrack = (event) => {
        const stream = this.remoteStream ?? new MediaStream();
        this.remoteStream = stream;
        event.streams[0]?.getTracks().forEach((track) => {
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
        } else if (["failed", "closed", "disconnected"].includes(peer.connectionState)) {
          this.status = "ended";
          this.statusMessage = "Call ended";
          this.isDialing = false;
          this.playOutgoingRing = false;
          this.playIncomingRing = false;
          this.hasIncomingCallIntent = false;
        } else {
          this.statusMessage = `Connection: ${peer.connectionState}`;
        }
      };

      // keep linter happy about currently selected conversation
      this.callConversationId = conversationId;
    },

    async handleSignal(type: "ready" | "offer" | "answer" | "ice" | "hangup", payload?: unknown) {
      if ((type === "ready" || type === "offer") && !this.inCall && !this.isDialing) {
        this.hasIncomingCallIntent = true;
        this.playIncomingRing = true;
        this.playOutgoingRing = false;
        this.statusMessage = "Incoming call...";

        // Wait for explicit Join action before processing SDP.
        if (type === "offer") {
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
        this.statusMessage = "Offer received. Creating answer...";
        await this.peer.setRemoteDescription(payload as RTCSessionDescriptionInit);
        const answer = await this.peer.createAnswer();
        await this.peer.setLocalDescription(answer);
        this.sendSignal("answer", answer);

        for (const ice of this.pendingIce) {
          await this.peer.addIceCandidate(ice);
        }
        this.pendingIce = [];
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
      this.ws.send(JSON.stringify({ type, payload, client_id: this.clientId }));
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
      if (notify) {
        this.sendSignal("hangup", { ended: true });
      }

      this.peer?.close();
      this.peer = null;
      this.loopbackPeer?.close();
      this.loopbackPeer = null;

      this.ws?.close();
      this.ws = null;

      this.localStream?.getTracks().forEach((track) => track.stop());
      this.remoteStream?.getTracks().forEach((track) => track.stop());
      this.localStream = null;
      this.remoteStream = null;

      this.pendingIce = [];
      this.callConversationId = null;
      this.hasIncomingCallIntent = false;
      this.playOutgoingRing = false;
      this.playIncomingRing = false;
      this.isDialing = false;
      this.status = "ended";
      this.statusMessage = "Call ended";
    },

    resetStatusIfIdle() {
      if (!this.localStream && !this.peer && !this.ws) {
        this.status = "idle";
        this.statusMessage = "Ready";
      }
    },
  },
});
