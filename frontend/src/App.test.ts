import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import App from './App.vue'

// Mutable chat state so tests can manipulate conversations
const chatState = {
  conversations: [] as any[],
  activeConversationId: null as number | null,
  activeMessages: [] as any[],
  messagesByConversation: {} as Record<number, any[]>,
}

vi.mock('./stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: false,
    user: { id: 10, username: 'testuser', email: 'test@example.com' },
    accessToken: 'mock-token',
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
    get conversations() { return chatState.conversations },
    set conversations(v) { chatState.conversations = v },
    get activeConversationId() { return chatState.activeConversationId },
    set activeConversationId(v) { chatState.activeConversationId = v },
    get activeMessages() { return chatState.activeMessages },
    get messagesByConversation() { return chatState.messagesByConversation },
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
  exportPublicKey: vi.fn(() => 'mock-public-key'),
  generateConversationKey: vi.fn(() => 'mock-key'),
  generateIdentityKeypair: vi.fn(() => Promise.resolve({ publicKey: 'mock-pub', privateKey: 'mock-priv' })),
}))

vi.mock('./components/AdminTestLabPanel.vue', () => ({
  default: { template: '<div>Mock Admin Panel</div>' }
}))

let oscillatorCalls: number
let resumeCalls: number

function installAudioMock(initialState = 'running') {
  oscillatorCalls = 0
  resumeCalls = 0

  global.AudioContext = vi.fn().mockImplementation(function (this: any) {
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

function resetChatState() {
  chatState.conversations = []
  chatState.activeConversationId = null
  chatState.activeMessages = []
  chatState.messagesByConversation = {}
}

describe('App Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    resetChatState()
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
    resetChatState()
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
    // chime pattern = 2 oscillator notes
    expect(oscillatorCalls).toBe(2)
  })

  it('triggerNotification plays receiver dm_document_sound preference for incoming document', () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any

    vm.notificationsReady = true
    vm.triggerNotification(2, 'document', 1, true)
    // pulse pattern = 3 oscillator notes
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

describe('Non-Active Conversation Notifications', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    resetChatState()
    installAudioMock()
  })

  it('refreshConversations triggers notification for new incoming message on non-active conversation', async () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any

    chatState.activeConversationId = 1

    // First pass: seed known conversations with no messages (notifications off)
    chatState.conversations = [
      { id: 1, kind: 'dm', title: 'active', created_by: 10, created_at: '', workspace: null, channel: null, last_message_id: null, last_message_sender: null },
      { id: 2, kind: 'dm', title: 'other', created_by: 99, created_at: '', workspace: null, channel: null, last_message_id: null, last_message_sender: null },
    ]
    await vm.refreshConversations()

    // Now enable notifications and simulate a new message arriving on conv 2
    vm.notificationsReady = true
    chatState.conversations = [
      { id: 1, kind: 'dm', title: 'active', created_by: 10, created_at: '', workspace: null, channel: null, last_message_id: null, last_message_sender: null },
      { id: 2, kind: 'dm', title: 'other', created_by: 99, created_at: '', workspace: null, channel: null, last_message_id: 500, last_message_sender: 99 },
    ]

    await vm.refreshConversations()

    expect(vm.unreadByConversation[2]).toBe(1)
    // chime = 2 oscillators
    expect(oscillatorCalls).toBe(2)
  })

  it('refreshConversations does not trigger notification for own message on non-active conversation', async () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any

    chatState.activeConversationId = 1

    // Seed known conversations
    chatState.conversations = [
      { id: 1, kind: 'dm', title: 'active', created_by: 10, created_at: '', workspace: null, channel: null, last_message_id: null, last_message_sender: null },
      { id: 2, kind: 'dm', title: 'other', created_by: 10, created_at: '', workspace: null, channel: null, last_message_id: null, last_message_sender: null },
    ]
    await vm.refreshConversations()

    vm.notificationsReady = true

    // Message from self (user id 10) on conv 2
    chatState.conversations = [
      { id: 1, kind: 'dm', title: 'active', created_by: 10, created_at: '', workspace: null, channel: null, last_message_id: null, last_message_sender: null },
      { id: 2, kind: 'dm', title: 'other', created_by: 10, created_at: '', workspace: null, channel: null, last_message_id: 600, last_message_sender: 10 },
    ]

    await vm.refreshConversations()

    expect(vm.unreadByConversation[2]).toBeUndefined()
    expect(oscillatorCalls).toBe(0)
  })

  it('refreshConversations does not double-count the same last_message_id', async () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any

    chatState.activeConversationId = 1

    // Seed known conversations
    chatState.conversations = [
      { id: 1, kind: 'dm', title: 'active', created_by: 10, created_at: '', workspace: null, channel: null, last_message_id: null, last_message_sender: null },
      { id: 2, kind: 'dm', title: 'other', created_by: 99, created_at: '', workspace: null, channel: null, last_message_id: null, last_message_sender: null },
    ]
    await vm.refreshConversations()

    vm.notificationsReady = true

    chatState.conversations = [
      { id: 1, kind: 'dm', title: 'active', created_by: 10, created_at: '', workspace: null, channel: null, last_message_id: null, last_message_sender: null },
      { id: 2, kind: 'dm', title: 'other', created_by: 99, created_at: '', workspace: null, channel: null, last_message_id: 700, last_message_sender: 99 },
    ]

    await vm.refreshConversations()
    expect(vm.unreadByConversation[2]).toBe(1)

    // Call again with same last_message_id — should not increment
    oscillatorCalls = 0
    await vm.refreshConversations()
    expect(vm.unreadByConversation[2]).toBe(1)
    expect(oscillatorCalls).toBe(0)
  })

  it('refreshConversations skips active conversation', async () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any

    chatState.activeConversationId = 1

    // Seed
    chatState.conversations = [
      { id: 1, kind: 'dm', title: 'active', created_by: 10, created_at: '', workspace: null, channel: null, last_message_id: null, last_message_sender: null },
    ]
    await vm.refreshConversations()

    vm.notificationsReady = true

    // New message on the active conversation — should be handled by WebSocket watcher, not here
    chatState.conversations = [
      { id: 1, kind: 'dm', title: 'active', created_by: 10, created_at: '', workspace: null, channel: null, last_message_id: 800, last_message_sender: 99 },
    ]

    await vm.refreshConversations()

    expect(vm.unreadByConversation[1]).toBeUndefined()
    expect(oscillatorCalls).toBe(0)
  })
})

describe('AudioContext Warm-up', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    resetChatState()
    installAudioMock('suspended')
  })

  it('resumes suspended AudioContext when playing sound', () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any

    vm.playNamedSound('chime')
    expect(resumeCalls).toBeGreaterThan(0)
  })
})
