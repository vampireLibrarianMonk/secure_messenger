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

// Mock API requests
vi.mock('./lib/api', () => ({
  apiRequest: vi.fn(() => Promise.resolve({}))
}))

// Mock crypto functions
vi.mock('./lib/crypto', () => ({
  decryptFile: vi.fn(),
  encryptFile: vi.fn(),
  encryptText: vi.fn(),
  exportPublicKey: vi.fn(),
  generateConversationKey: vi.fn(() => 'mock-key'),
  generateIdentityKeypair: vi.fn(),
}))

// Mock AdminTestLabPanel component
vi.mock('./components/AdminTestLabPanel.vue', () => ({
  default: { template: '<div>Mock Admin Panel</div>' }
}))

describe('App Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders login form when not authenticated', () => {
    const wrapper = mount(App)
    
    expect(wrapper.find('h2').text()).toBe('Sign in')
    expect(wrapper.find('input[placeholder="Username"]').exists()).toBe(true)
    expect(wrapper.find('input[placeholder="Password"]').exists()).toBe(true)
    expect(wrapper.find('button').text()).toBe('Login')
  })

  it('includes notification sound options in settings', () => {
    const wrapper = mount(App)
    
    // Look for notification sound options in the template
    const html = wrapper.html()
    expect(html).toContain('Digital Chime')
    expect(html).toContain('Mobile Trill') 
    expect(html).toContain('Classic Phone Ring')
    expect(html).toContain('Soft Bell')
  })
})

describe('Notification Functions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    
    // Mock AudioContext
    global.AudioContext = vi.fn().mockImplementation(() => ({
      createOscillator: vi.fn(() => ({
        type: 'sine',
        frequency: { setValueAtTime: vi.fn() },
        connect: vi.fn(),
        start: vi.fn(),
        stop: vi.fn(),
      })),
      createGain: vi.fn(() => ({
        gain: { 
          setValueAtTime: vi.fn(),
          exponentialRampToValueAtTime: vi.fn(),
        },
        connect: vi.fn(),
      })),
      destination: {},
      currentTime: 0,
    }))
  })

  it('should have different sound patterns for different notification types', () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any
    
    // Test that different sound types trigger different patterns
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

  it('should only trigger notifications when ready and not in active conversation', () => {
    const wrapper = mount(App)
    const vm = wrapper.vm as any
    
    // Mock notification state
    vm.notificationsReady = false
    vm.chat.activeConversationId = 1
    
    const playNamedSoundSpy = vi.spyOn(vm, 'playNamedSound')
    
    // Should not play sound when notifications not ready
    vm.triggerNotification(1, 'dm', 1)
    expect(playNamedSoundSpy).not.toHaveBeenCalled()
    
    // Should not play sound for active conversation even when ready
    vm.notificationsReady = true
    vm.triggerNotification(1, 'dm', 1)
    expect(playNamedSoundSpy).not.toHaveBeenCalled()
    
    // Should play sound for different conversation when ready
    vm.triggerNotification(2, 'dm', 1)
    expect(playNamedSoundSpy).toHaveBeenCalledWith('chime')
  })
})
