import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import App from './App.vue'

// Mock the stores
vi.mock('./stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: false,
    user: null,
    accessToken: null,
    login: vi.fn(),
    logout: vi.fn(),
    loadMe: vi.fn(),
    loadNotificationPreferences: vi.fn(() => Promise.resolve({
      dm_sound: "chime",
      dm_document_sound: "pulse",
      video_ring_sound: "alert",
      chat_leave_sound: "soft",
    })),
    changePassword: vi.fn(),
    saveNotificationPreferences: vi.fn(),
  })
}))

vi.mock('./stores/chat', () => ({
  useChatStore: () => ({
    conversations: [],
    activeConversationId: null,
    activeMessages: [],
    messagesByConversation: {},
    loadConversations: vi.fn(),
    createConversation: vi.fn(),
    deleteConversation: vi.fn(),
    nukeConversation: vi.fn(),
    loadMessages: vi.fn(),
    refreshMessages: vi.fn(),
    disconnectSocket: vi.fn(),
  })
}))

vi.mock('./stores/security', () => ({
  useSecurityStore: () => ({
    locked: false,
    inactivitySeconds: 300,
    lastActivityAt: Date.now(),
    unlock: vi.fn(),
    lockNow: vi.fn(),
    touch: vi.fn(),
    setPasscode: vi.fn(),
    setInactivityTimeout: vi.fn(),
    resetLocalSecurity: vi.fn(),
    getConversationKey: vi.fn(),
    setConversationKey: vi.fn(),
  })
}))

vi.mock('./stores/video', () => ({
  useVideoStore: () => ({
    inCall: false,
    hasIncomingCallIntent: false,
    status: "idle",
    statusMessage: "Ready",
    localStream: null,
    remoteStream: null,
    micEnabled: true,
    cameraEnabled: true,
    playOutgoingRing: false,
    playIncomingRing: false,
    diagnosticsEnabled: false,
    diagnostics: {},
    diagnosticsError: null,
    mediaE2eeSupported: true,
    mediaE2eeEnabled: false,
    mediaE2eeMode: null,
    mediaE2eeKeyFingerprint: null,
    mediaE2eeKeyRotatedAt: null,
    mediaE2eeRuntimeTransformClass: null,
    mediaE2eeRuntimeAttachmentCount: 0,
    callConversationId: null,
    startCall: vi.fn(),
    joinCall: vi.fn(),
    endCall: vi.fn(),
    toggleMic: vi.fn(),
    toggleCamera: vi.fn(),
    startStreamTest: vi.fn(),
    startLoopbackTest: vi.fn(),
    runSignalingTest: vi.fn(),
    endSignalingTest: vi.fn(),
    resetStatusIfIdle: vi.fn(),
    setDiagnosticsEnabled: vi.fn(),
    listenForIncoming: vi.fn(),
  })
}))

vi.mock('./lib/api', () => ({
  apiRequest: vi.fn(() => Promise.resolve({}))
}))

vi.mock('./lib/crypto', () => ({
  decryptFile: vi.fn(),
  encryptFile: vi.fn(),
  encryptText: vi.fn(),
  exportPublicKey: vi.fn(),
  generateConversationKey: vi.fn(() => 'mock-key'),
  generateIdentityKeypair: vi.fn(),
}))

vi.mock('./components/AdminTestLabPanel.vue', () => ({
  default: { template: '<div>Mock Admin Panel</div>' }
}))

// Track all oscillator creations globally across AudioContext mocks
let oscillatorCalls: number
let resumeCalls: number
let constructorCalls: number

function installAudioMock(initialState = 'running') {
  oscillatorCalls = 0
  resumeCalls = 0
  constructorCalls = 0

  global.AudioContext = vi.fn().mockImplementation(function (this: any) {
    constructorCalls++
    this.currentTime = 0
    this.state = initialState
    this.destination = {}
    this.resume = vi.fn(() => { resumeCalls++ })
    this.createOscillator = vi.fn(() => {
      oscillatorCalls++
      return {
        type: 'sine',
        frequency: { setValueAtTime: vi.fn() },
        connect: vi.fn(),
        start: vi.fn(),
        stop: vi.fn(),
      }
    })
    this.createGain = vi.fn(() => ({
      gain: {
        setValueAtTime: vi.fn(),
        exponentialRampToValueAtTime: vi.fn(),
      },
      connect: vi.fn(),
    }))
  }) as any
}

describe('App Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders login form when not authenticated', () => {
    const wrapper = mount(App)

    expect(wrapper.find('h2').text()).toBe('Sign in')
    expect(wrapper.find('input[placeholder="Username"]').exists()).toBe(true)
    expect(wrapper.find('input[placeholder="Password"]').exists()).toBe(true)
    const loginBtn = wrapper.findAll('button').find((b) => b.text() === 'Login')
    expect(loginBtn).toBeTruthy()
  })

  it('exposes notification sound options', () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any

    expect(vm.notificationSoundOptions).toEqual([
      { value: "chime", label: "Digital Chime" },
      { value: "pulse", label: "Mobile Trill" },
      { value: "alert", label: "Classic Phone Ring" },
      { value: "soft", label: "Soft Bell" },
    ])

    expect(vm.videoRingSoundOptions).toEqual([
      { value: "alert", label: "Classic Phone Ring" },
      { value: "pulse", label: "Modern Smartphone Ring" },
      { value: "chime", label: "Desk Bell" },
      { value: "soft", label: "Gentle Ring" },
    ])
  })
})

describe('Notification Sound Playback', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    installAudioMock()
  })

  it('triggerNotification does not play when notificationsReady is false', () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any

    vm.notificationsReady = false
    vm.triggerNotification(2, 'dm', 1, true)
    expect(oscillatorCalls).toBe(0)
  })

  it('triggerNotification plays receiver dm_sound preference for incoming DM', () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any

    vm.notificationsReady = true
    vm.triggerNotification(2, 'dm', 1, true)
    // chime pattern has 2 oscillator notes
    expect(oscillatorCalls).toBe(2)
  })

  it('triggerNotification plays receiver dm_document_sound preference for incoming document', () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any

    vm.notificationsReady = true
    vm.triggerNotification(2, 'document', 1, true)
    // pulse pattern has 3 oscillator notes
    expect(oscillatorCalls).toBe(3)
  })

  it('playNamedSound produces oscillators for each named sound', () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any

    vm.playNamedSound('chime')
    expect(oscillatorCalls).toBe(2)

    vm.playNamedSound('pulse')
    expect(oscillatorCalls).toBe(5) // +3

    vm.playNamedSound('alert')
    expect(oscillatorCalls).toBe(9) // +4

    vm.playNamedSound('soft')
    expect(oscillatorCalls).toBe(11) // +2
  })
})
