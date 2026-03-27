<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  createSyntheticEvents,
  markEventStatus,
  type ConsoleLifecycleState,
  type SyntheticEvent,
  type SyntheticLogLine,
} from "../lib/eventFormatter";
import {
  buildSyntheticMessageFlow,
  generateFauxTestUsers,
  generateRunId,
  type FauxTestUserAccount,
} from "../lib/fauxData";
import {
  defaultResultSeed,
  evaluateResultFromEvidence,
  type EvidenceSnapshot,
  type ResultSummarySeed,
} from "../lib/resultModel";
import { scenarioCatalog, type ScenarioDefinition } from "../lib/scenarioCatalog";
import { apiRequest } from "../lib/api";

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

const props = defineProps<{
  bootstrap: TestLabBootstrapResponse;
  accessToken?: string;
}>();

defineEmits<{
  close: [];
}>();

interface StoredRunArtifact {
  run_id: string;
  scenario: string;
  scenario_label: string;
  category: string;
  environment: string;
  intensity: string;
  state: ConsoleLifecycleState;
  result: string;
  duration_ms: number;
  warnings: number;
  participants: string[];
  events: SyntheticEvent[];
  logs: SyntheticLogLine[];
  evidence: string[];
  diagnostics: Record<string, unknown>;
  metadata_observability: {
    correlation_id: string;
    session_id: string;
    room_id: string;
    transport_path: string;
    auth_state: string;
  };
}

interface ArtifactSummary {
  id: number;
  run_id: string;
  scenario: string;
  result: string;
  state: ConsoleLifecycleState;
  duration_ms: number;
  warnings: number;
  created_at: string;
  created_by: string;
}

const activeView = ref<"test-lab" | "connection-console" | "admin-review" | "diagnostics">("test-lab");
const selectedScenarioId = ref("dm-basic");
const selectedEnvironment = ref("local sandbox");
const selectedIntensity = ref<"quick" | "standard" | "exhaustive">("standard");
const showAnimationDetails = ref(true);
const verboseBashLog = ref(true);
const injectWarningConditions = ref(false);
const includeUnknownBranch = ref(false);
const autoScrollLogs = ref(true);
const includeFauxRelayNodes = ref(false);
const injectFailureBranch = ref(false);

const currentRunId = ref<string | null>(null);
const currentRunParticipants = ref<string[]>([]);
const currentRunEvents = ref<SyntheticEvent[]>([]);
const currentRunLogs = ref<SyntheticLogLine[]>([]);
const currentResult = ref<ResultSummarySeed | null>(null);
const runState = ref<ConsoleLifecycleState>("idle");
const runWarnings = ref(0);
const runStartedAt = ref<number | null>(null);
const runDurationMs = ref(0);
const runTimerHandle = ref<number | null>(null);
const runStepHandle = ref<number | null>(null);
const currentRunUsers = ref<FauxTestUserAccount[]>([]);
const runHistory = ref<StoredRunArtifact[]>([]);
const persistedRunSummaries = ref<ArtifactSummary[]>([]);
const selectedPersistedRun = ref<StoredRunArtifact | null>(null);
const artifactBusy = ref(false);
const artifactError = ref("");

const isSecurityAdmin = computed(() => props.bootstrap.roles.includes("security_admin"));
const isTestUser = computed(() => props.bootstrap.roles.includes("test_user"));
const diagnosticsEnabled = computed(
  () => props.bootstrap.feature_flags.verbose_diagnostics_enabled && (isSecurityAdmin.value || isTestUser.value),
);
const canReviewArtifacts = computed(() => Boolean(props.accessToken && (isSecurityAdmin.value || isTestUser.value)));

const scenarioOptions = computed(() =>
  scenarioCatalog.filter(
    (scenario) => !scenario.featureFlag || props.bootstrap.feature_flags[scenario.featureFlag] === true,
  ),
);

const selectedScenario = computed<ScenarioDefinition>(() => {
  return (
    scenarioOptions.value.find((scenario) => scenario.id === selectedScenarioId.value) ??
    scenarioOptions.value[0]
  );
});

const selectedScenarioStatus = computed(() => {
  const scenario = selectedScenario.value;
  if (!scenario) return "Select a scenario to preview synthetic execution status.";
  return scenario.description;
});

const diagnosticsSnapshot = computed(() => {
  const category = selectedScenario.value?.category ?? "dm";
  const base = {
    session_state: runState.value,
    participants: currentRunParticipants.value,
    warnings: runWarnings.value,
    result: currentResult.value?.result ?? "UNKNOWN / UNVERIFIED",
  };

  return {
    dm: {
      ...base,
      envelope_created: ["dm", "full"].includes(category),
      ciphertext_before_send_confirmed: ["dm", "full"].includes(category),
      key_change_warning_state: runWarnings.value > 0,
      lock_wipe_state: "ready",
    },
    video: {
      ...base,
      signaling_connected: ["video", "full", "group"].includes(category),
      candidate_pair_type: includeFauxRelayNodes.value ? "relay" : "direct",
      turn_usage: includeFauxRelayNodes.value,
      strict_mode_supported: !includeUnknownBranch.value,
      transport_vs_app_layer: currentResult.value?.result === "PASS — TRANSPORT ONLY" ? "transport_only" : "app_layer_verified_or_unknown",
    },
    document: {
      ...base,
      file_key_generated: ["document", "full"].includes(category),
      encrypted_blob_produced: ["document", "full"].includes(category),
      wrapped_key_sent: ["document", "full"].includes(category),
      no_plain_upload_path_detected: true,
    },
    group: {
      ...base,
      participant_set: currentRunParticipants.value,
      membership_change_detected: category === "group",
      rekey_completion_confirmed: category === "group" && runWarnings.value === 0,
      post_removal_access_denial_check: category === "group" && runWarnings.value === 0,
    },
  };
});

const latestOutcomeComparison = computed(() => {
  if (runHistory.value.length < 2) return null;
  const [latest, previous] = runHistory.value;
  return {
    latest: `${latest.run_id} (${latest.result})`,
    previous: `${previous.run_id} (${previous.result})`,
    changed: latest.result !== previous.result,
  };
});

function appendLog(line: SyntheticLogLine) {
  currentRunLogs.value.push(line);
}

function nowIso() {
  return new Date().toISOString();
}

function currentEvidenceSnapshot(scenario: ScenarioDefinition, hadFailure: boolean): EvidenceSnapshot {
  const hasWarnings = runWarnings.value > 0;
  return {
    scenario: scenario.category,
    environment: selectedEnvironment.value,
    warnings: runWarnings.value,
    hadFailure,
    dmClientEncryptConfirmed: ["dm", "full"].includes(scenario.category) ? !hasWarnings && !hadFailure : true,
    dmCiphertextOnlyRoutingConfirmed: ["dm", "full"].includes(scenario.category) ? !hasWarnings && !hadFailure : true,
    dmRecipientDecryptConfirmed: ["dm", "full"].includes(scenario.category) ? !hasWarnings && !hadFailure : true,
    videoTransportProtected: ["video", "full", "group"].includes(scenario.category),
    videoAppLayerE2eeConfirmed:
      scenario.category === "video" ? selectedIntensity.value !== "quick" && !hasWarnings && !hadFailure : !hasWarnings && !hadFailure,
    documentClientBlobEncryptionConfirmed: ["document", "full"].includes(scenario.category) ? !hasWarnings && !hadFailure : true,
    documentWrappedKeyTransferConfirmed: ["document", "full"].includes(scenario.category) ? !hasWarnings && !hadFailure : true,
    documentRecipientDecryptConfirmed: ["document", "full"].includes(scenario.category) ? !hasWarnings && !hadFailure : true,
    groupMembershipRekeyConfirmed: scenario.category === "group" ? !hasWarnings && !hadFailure : true,
    groupPostRemovalAccessDeniedConfirmed: scenario.category === "group" ? !hasWarnings && !hadFailure : true,
    sufficientEvidence: !hasWarnings && !hadFailure && !includeUnknownBranch.value,
  };
}

function buildStoredArtifact(scenario: ScenarioDefinition): StoredRunArtifact {
  return {
    run_id: currentRunId.value ?? "sim_run_pending",
    scenario: scenario.id,
    scenario_label: scenario.label,
    category: scenario.category,
    environment: selectedEnvironment.value,
    intensity: selectedIntensity.value,
    state: runState.value,
    result: currentResult.value?.result ?? "UNKNOWN / UNVERIFIED",
    duration_ms: runDurationMs.value,
    warnings: runWarnings.value,
    participants: [...currentRunParticipants.value],
    events: [...currentRunEvents.value],
    logs: [...currentRunLogs.value],
    evidence: [...(currentResult.value?.evidence ?? [])],
    diagnostics: diagnosticsSnapshot.value,
    metadata_observability: {
      correlation_id: `${currentRunId.value ?? "sim_run"}-corr`,
      session_id: `${currentRunId.value ?? "sim_run"}-sess`,
      room_id: `${scenario.id}-room`,
      transport_path: includeFauxRelayNodes.value ? "relay" : "direct",
      auth_state: "validated",
    },
  };
}

async function loadPersistedArtifacts() {
  if (!canReviewArtifacts.value || !props.accessToken) return;
  artifactBusy.value = true;
  artifactError.value = "";
  try {
    const payload = await apiRequest<{ runs: ArtifactSummary[] }>("/test-lab/runs/", { token: props.accessToken });
    persistedRunSummaries.value = payload.runs;
  } catch (error) {
    artifactError.value = error instanceof Error ? error.message : "Failed to load run artifacts.";
  } finally {
    artifactBusy.value = false;
  }
}

async function openPersistedArtifact(runId: string) {
  if (!props.accessToken || !runId) return;
  artifactBusy.value = true;
  artifactError.value = "";
  try {
    const payload = await apiRequest<{ run: StoredRunArtifact }>(`/test-lab/runs/?run_id=${encodeURIComponent(runId)}`, {
      token: props.accessToken,
    });
    selectedPersistedRun.value = payload.run;
    activeView.value = "admin-review";
  } catch (error) {
    artifactError.value = error instanceof Error ? error.message : "Failed to open run artifact.";
  } finally {
    artifactBusy.value = false;
  }
}

function replayFromHistory(runId: string) {
  const match = runHistory.value.find((item) => item.run_id === runId);
  if (!match) return;
  const scenario = scenarioOptions.value.find((item) => item.id === match.scenario);
  if (scenario) {
    selectedScenarioId.value = scenario.id;
  }
  selectedEnvironment.value = match.environment;
  selectedIntensity.value = (match.intensity as "quick" | "standard" | "exhaustive") ?? "standard";
  runSimulation();
}

function runSimulation() {
  const scenario = selectedScenario.value;
  if (!scenario) return;

  if (runTimerHandle.value) {
    window.clearInterval(runTimerHandle.value);
    runTimerHandle.value = null;
  }
  if (runStepHandle.value) {
    window.clearInterval(runStepHandle.value);
    runStepHandle.value = null;
  }

  currentRunId.value = generateRunId();
  currentRunUsers.value = generateFauxTestUsers(scenario.requiredParticipants);
  currentRunParticipants.value = currentRunUsers.value.map((user) => `${user.username}@${user.assignedNode}`);
  currentRunEvents.value = createSyntheticEvents(scenario.orderedSteps);
  currentRunLogs.value = [];
  currentResult.value = defaultResultSeed(scenario.category);
  runState.value = "running";
  runWarnings.value = 0;
  runStartedAt.value = Date.now();
  runDurationMs.value = 0;
  activeView.value = "connection-console";

  currentRunUsers.value.forEach((user) => {
    appendLog({
      timestamp: nowIso(),
      level: "INFO",
      text: `CREATE_USER ${user.username} on ${user.assignedNode} credential=generated_secure_hex(redacted)`,
    });
  });

  if (includeUnknownBranch.value) {
    appendLog({ timestamp: nowIso(), level: "WARN", text: "UNKNOWN_BRANCH flagged; final classification may be unverified." });
  }

  runTimerHandle.value = window.setInterval(() => {
    if (!runStartedAt.value) return;
    runDurationMs.value = Date.now() - runStartedAt.value;
  }, 250);

  let step = 0;
  runStepHandle.value = window.setInterval(() => {
    if (step > 0) {
      currentRunEvents.value = markEventStatus(currentRunEvents.value, step - 1, "completed");
      appendLog({
        timestamp: nowIso(),
        level: "INFO",
        text: `${currentRunEvents.value[step - 1].label} completed`,
      });
    }

    if (step < currentRunEvents.value.length) {
      currentRunEvents.value = markEventStatus(currentRunEvents.value, step, "active");
      appendLog({
        timestamp: nowIso(),
        level: "INFO",
        text: `${currentRunEvents.value[step].label} active | ${buildSyntheticMessageFlow(scenario.category, currentRunUsers.value, step)}`,
      });

      const shouldWarn =
        (injectWarningConditions.value || selectedIntensity.value !== "quick") && step === Math.floor(currentRunEvents.value.length / 2);
      if (shouldWarn) {
        runWarnings.value += 1;
        currentRunEvents.value = markEventStatus(currentRunEvents.value, step, "warning");
        appendLog({
          timestamp: nowIso(),
          level: "WARN",
          text: `${currentRunEvents.value[step].label} warning: transient relay latency detected`,
        });
      }

      if (injectFailureBranch.value && step === Math.floor(currentRunEvents.value.length / 2) + 1) {
        currentRunEvents.value = markEventStatus(currentRunEvents.value, step, "failed");
        runState.value = "failed";
        currentResult.value = evaluateResultFromEvidence(currentEvidenceSnapshot(scenario, true));
        appendLog({ timestamp: nowIso(), level: "ERROR", text: "Injected failure branch triggered; aborting run." });
        finalizeRun(scenario);
        return;
      }

      step += 1;
      return;
    }

    runState.value = includeUnknownBranch.value || runWarnings.value > 0 ? "unknown" : "completed";
    currentResult.value = evaluateResultFromEvidence(currentEvidenceSnapshot(scenario, false));
    appendLog({
      timestamp: nowIso(),
      level: runState.value === "completed" ? "INFO" : "WARN",
      text: runState.value === "completed" ? "Run completed successfully" : "Run completed with unverified branch; review warnings",
    });
    finalizeRun(scenario);
  }, 900);
}

async function persistRunArtifact(artifact: StoredRunArtifact) {
  if (!props.accessToken || !canReviewArtifacts.value) return;
  try {
    await apiRequest<{ detail: string }>("/test-lab/runs/", {
      method: "POST",
      token: props.accessToken,
      body: { run: artifact },
    });
    await loadPersistedArtifacts();
  } catch (error) {
    artifactError.value = error instanceof Error ? error.message : "Failed to persist run artifact.";
  }
}

function finalizeRun(scenario: ScenarioDefinition) {
  currentRunUsers.value.forEach((user) => {
    appendLog({ timestamp: nowIso(), level: "INFO", text: `DESTROY_USER ${user.username} from ${user.assignedNode}` });
  });

  const artifact = buildStoredArtifact(scenario);
  runHistory.value = [artifact, ...runHistory.value].slice(0, 20);
  void persistRunArtifact(artifact);

  if (runTimerHandle.value) {
    window.clearInterval(runTimerHandle.value);
    runTimerHandle.value = null;
  }
  if (runStepHandle.value) {
    window.clearInterval(runStepHandle.value);
    runStepHandle.value = null;
  }
}

function applyHistoryRun(run: StoredRunArtifact) {
  selectedPersistedRun.value = run;
  activeView.value = "admin-review";
}

function exportArtifactJson() {
  const source = selectedPersistedRun.value ?? runHistory.value[0];
  if (!source) return;
  const safePayload = {
    ...source,
    logs: source.logs,
    events: source.events,
    diagnostics: source.diagnostics,
  };
  const blob = new Blob([JSON.stringify(safePayload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${source.run_id}-artifact.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

watch(
  () => currentRunLogs.value.length,
  () => {
    if (!autoScrollLogs.value || !verboseBashLog.value) return;
    window.requestAnimationFrame(() => {
      const panel = document.querySelector(".bash-log-scroll") as HTMLElement | null;
      if (panel) {
        panel.scrollTop = panel.scrollHeight;
      }
    });
  },
);

onMounted(async () => {
  await loadPersistedArtifacts();
});

onBeforeUnmount(() => {
  if (runTimerHandle.value) window.clearInterval(runTimerHandle.value);
  if (runStepHandle.value) window.clearInterval(runStepHandle.value);
});
</script>

<template>
  <section class="card">
    <div class="test-lab-top">
      <div>
        <h2>Admin Secure Test Lab</h2>
        <p class="muted">Entry point for the isolated synthetic testing interface.</p>
      </div>
      <button class="ghost" @click="$emit('close')">Back to Messenger</button>
    </div>

    <div class="test-lab-tabs">
      <button :class="{ active: activeView === 'test-lab' }" @click="activeView = 'test-lab'">Test Lab</button>
      <button :class="{ active: activeView === 'connection-console' }" @click="activeView = 'connection-console'">
        Connection Console
      </button>
      <button :class="{ active: activeView === 'admin-review' }" @click="activeView = 'admin-review'">Admin Review</button>
      <button
        :class="{ active: activeView === 'diagnostics' }"
        :disabled="!diagnosticsEnabled"
        @click="activeView = 'diagnostics'"
      >
        Diagnostics
      </button>
    </div>

    <div class="test-lab-shell">
      <template v-if="activeView === 'test-lab'">
        <h3>Test Lab</h3>
        <p class="muted">Synthetic scenario controls for secure communications test runs.</p>

        <div class="test-lab-controls">
          <label>
            Test Scenario
            <select v-model="selectedScenarioId">
              <option v-for="scenario in scenarioOptions" :key="scenario.id" :value="scenario.id">
                {{ scenario.label }}
              </option>
            </select>
          </label>
          <p class="scenario-status muted">{{ selectedScenarioStatus }}</p>

          <label>
            Synthetic Environment
            <select v-model="selectedEnvironment">
              <option
                v-for="environment in selectedScenario?.environmentPresets ?? []"
                :key="environment"
                :value="environment"
              >
                {{ environment }}
              </option>
            </select>
          </label>

          <label>
            Test Intensity
            <select v-model="selectedIntensity">
              <option v-for="intensity in selectedScenario?.intensityPresets ?? []" :key="intensity" :value="intensity">
                {{ intensity }}
              </option>
            </select>
          </label>

          <label>
            Show animation details
            <input v-model="showAnimationDetails" type="checkbox" />
          </label>

          <label>
            Verbose bash log
            <input v-model="verboseBashLog" type="checkbox" />
          </label>

          <label>
            Inject warning conditions
            <input v-model="injectWarningConditions" type="checkbox" />
          </label>

          <label>
            Include faux relay nodes
            <input v-model="includeFauxRelayNodes" type="checkbox" />
          </label>

          <label>
            Include unknown/unverified branch
            <input v-model="includeUnknownBranch" type="checkbox" />
          </label>

          <label>
            Inject failure branch
            <input v-model="injectFailureBranch" type="checkbox" />
          </label>

          <label>
            Auto-scroll logs
            <input v-model="autoScrollLogs" type="checkbox" />
          </label>
        </div>

        <button class="run-sim-btn" @click="runSimulation">Run Simulated Test</button>

        <article class="test-lab-panel" style="margin-top: 0.8rem;">
          <h4>Replay / Re-run (Stage 8)</h4>
          <ul>
            <li v-for="run in runHistory" :key="run.run_id">
              <code>{{ run.run_id }}</code> — {{ run.scenario_label }} — {{ run.result }}
              <div class="inline-actions">
                <button class="ghost" @click="replayFromHistory(run.run_id)">Re-run</button>
                <button class="ghost" @click="applyHistoryRun(run)">Inspect</button>
              </div>
            </li>
          </ul>
          <p v-if="runHistory.length === 0" class="muted">No local run history yet.</p>
          <article v-if="latestOutcomeComparison" class="test-lab-panel" style="margin-top: 0.6rem;">
            <h5>Latest outcome comparison</h5>
            <p><strong>Latest:</strong> {{ latestOutcomeComparison.latest }}</p>
            <p><strong>Previous:</strong> {{ latestOutcomeComparison.previous }}</p>
            <p>
              Outcome changed:
              <strong>{{ latestOutcomeComparison.changed ? "yes" : "no" }}</strong>
            </p>
          </article>
        </article>
      </template>
      <template v-else-if="activeView === 'connection-console'">
        <h3>Connection Console</h3>
        <p class="muted">
          {{ selectedScenario?.label }} | {{ currentRunParticipants.join(" -> ") }} | {{ currentRunId || "sim_run_pending" }} |
          {{ runState }}
        </p>

        <article class="test-lab-panel run-summary">
          <h4>Run Summary</h4>
          <p>
            State: <strong :class="`state-${runState}`">{{ runState.toUpperCase() }}</strong>
          </p>
          <p>Duration: <strong>{{ (runDurationMs / 1000).toFixed(1) }}s</strong></p>
          <p>Warnings: <strong>{{ runWarnings }}</strong></p>
        </article>

        <div v-if="showAnimationDetails" class="console-strip">
          <span v-for="event in currentRunEvents" :key="event.id" class="console-step" :class="event.status">
            {{ event.label }}
          </span>
        </div>

        <div class="console-body-grid">
          <article class="test-lab-panel">
            <h4>Ordered Event Feed</h4>
            <ul>
              <li v-for="event in currentRunEvents" :key="event.id">
                <code>{{ event.timestamp }}</code> — {{ event.label }} ({{ event.status }})
              </li>
            </ul>
          </article>

          <article class="test-lab-panel" :class="{ 'bash-log-scroll': verboseBashLog }" aria-live="polite">
            <h4>Bash-style Log</h4>
            <ul v-if="verboseBashLog">
              <li v-for="line in currentRunLogs" :key="`${line.timestamp}-${line.text}`">
                <code>{{ line.timestamp }}</code> [{{ line.level }}] {{ line.text }}
              </li>
            </ul>
            <p v-else class="muted">Verbose bash log disabled. Enable toggle in Test Lab to view line-by-line output.</p>
          </article>
        </div>

        <article class="test-lab-panel">
          <h4>Result Summary Seed</h4>
          <p>
            <strong>{{ currentResult?.result ?? "UNKNOWN / UNVERIFIED" }}</strong>
          </p>
          <p class="muted">{{ currentResult?.explanation ?? "No result seeded." }}</p>
          <ul v-if="currentResult?.evidence?.length" class="result-evidence-list">
            <li v-for="line in currentResult.evidence" :key="line">{{ line }}</li>
          </ul>
          <p class="muted">Environment: {{ selectedEnvironment }} | Intensity: {{ selectedIntensity }}</p>
        </article>
      </template>
      <template v-else-if="activeView === 'admin-review'">
        <h3>Admin Review Workspace (Stage 6)</h3>
        <p class="muted">Review synthetic run artifacts and observability fields without plaintext content.</p>

        <article class="test-lab-panel">
          <h4>Persisted Artifacts</h4>
          <button class="ghost" :disabled="artifactBusy" @click="loadPersistedArtifacts">Refresh</button>
          <p v-if="artifactError" class="error">{{ artifactError }}</p>
          <ul>
            <li v-for="run in persistedRunSummaries" :key="run.id">
              <code>{{ run.run_id }}</code> — {{ run.scenario }} — {{ run.result }}
              <div class="inline-actions">
                <button class="ghost" :disabled="artifactBusy" @click="openPersistedArtifact(run.run_id)">Open</button>
              </div>
            </li>
          </ul>
        </article>

        <article v-if="selectedPersistedRun" class="test-lab-panel" style="margin-top: 0.7rem;">
          <h4>Artifact Detail: {{ selectedPersistedRun.run_id }}</h4>
          <p><strong>Result:</strong> {{ selectedPersistedRun.result }}</p>
          <p><strong>Duration:</strong> {{ (selectedPersistedRun.duration_ms / 1000).toFixed(2) }}s</p>
          <p><strong>Warnings:</strong> {{ selectedPersistedRun.warnings }}</p>
          <p><strong>Participants:</strong> {{ selectedPersistedRun.participants.join(", ") }}</p>

          <h5>Observability metadata</h5>
          <ul>
            <li>Correlation id: <code>{{ selectedPersistedRun.metadata_observability.correlation_id }}</code></li>
            <li>Session id: <code>{{ selectedPersistedRun.metadata_observability.session_id }}</code></li>
            <li>Room id: <code>{{ selectedPersistedRun.metadata_observability.room_id }}</code></li>
            <li>Transport path: <code>{{ selectedPersistedRun.metadata_observability.transport_path }}</code></li>
            <li>Auth state: <code>{{ selectedPersistedRun.metadata_observability.auth_state }}</code></li>
          </ul>
          <button class="ghost" @click="exportArtifactJson">Export Test Artifact</button>
        </article>
      </template>
      <template v-else>
        <h3>Diagnostics (Stage 7)</h3>
        <p v-if="!diagnosticsEnabled" class="muted">
          Diagnostics require test-user or security-admin role with verbose diagnostics enabled.
        </p>
        <div v-else class="console-body-grid">
          <article class="test-lab-panel">
            <h4>DM Test Actions</h4>
            <ul>
              <li v-for="(value, key) in diagnosticsSnapshot.dm" :key="`dm-${key}`"><code>{{ key }}</code>: {{ value }}</li>
            </ul>
          </article>
          <article class="test-lab-panel">
            <h4>Video Test Actions</h4>
            <ul>
              <li v-for="(value, key) in diagnosticsSnapshot.video" :key="`video-${key}`"><code>{{ key }}</code>: {{ value }}</li>
            </ul>
          </article>
          <article class="test-lab-panel">
            <h4>Document Test Actions</h4>
            <ul>
              <li v-for="(value, key) in diagnosticsSnapshot.document" :key="`doc-${key}`"><code>{{ key }}</code>: {{ value }}</li>
            </ul>
          </article>
          <article v-if="bootstrap.feature_flags.group_testing_enabled" class="test-lab-panel">
            <h4>Group Behavior Test Actions</h4>
            <ul>
              <li v-for="(value, key) in diagnosticsSnapshot.group" :key="`group-${key}`"><code>{{ key }}</code>: {{ value }}</li>
            </ul>
          </article>
        </div>
        <button v-if="diagnosticsEnabled" class="ghost" style="margin-top: 0.6rem;" @click="exportArtifactJson">Export Test Artifact</button>
      </template>
    </div>

    <div class="test-lab-grid">
      <article class="test-lab-panel">
        <h4>Role & Access</h4>
        <p>Roles: {{ bootstrap.roles.join(", ") }}</p>
        <p>Security admin: <strong>{{ bootstrap.is_security_admin ? "yes" : "no" }}</strong></p>
        <p>Test lab access: <strong>{{ bootstrap.can_access_test_lab ? "allowed" : "blocked" }}</strong></p>
      </article>

      <article class="test-lab-panel">
        <h4>Environment Gate</h4>
        <p>Current: <code>{{ bootstrap.environment.current }}</code></p>
        <p>Allowed: <code>{{ bootstrap.environment.allowed.join(", ") }}</code></p>
        <p>Environment valid: <strong>{{ bootstrap.environment.is_allowed ? "yes" : "no" }}</strong></p>
      </article>

      <article class="test-lab-panel">
        <h4>Feature Flags</h4>
        <ul>
          <li v-for="(enabled, key) in bootstrap.feature_flags" :key="key">
            <code>{{ key }}</code>: <strong>{{ enabled ? "enabled" : "disabled" }}</strong>
          </li>
        </ul>
      </article>

      <article class="test-lab-panel">
        <h4>Account Governance</h4>
        <ul>
          <li>
            Active admin accounts:
            <strong>{{ bootstrap.governance_status.active_admin_accounts }} / {{ bootstrap.governance_status.max_active_admins }}</strong>
          </li>
          <li>
            Active test users:
            <strong>{{ bootstrap.governance_status.active_test_users }} / {{ bootstrap.governance_status.max_active_test_users }}</strong>
          </li>
          <li>
            Group testing participant slot:
            <strong>
              {{ bootstrap.governance_status.group_testing_slot_enabled ? `${bootstrap.governance_status.group_testing_slot_usage} / 1 temporary` : "disabled" }}
            </strong>
          </li>
          <li>Admin limit compliant: <strong>{{ bootstrap.governance_status.admin_limit_compliant ? "yes" : "no" }}</strong></li>
          <li>Test-user limit compliant: <strong>{{ bootstrap.governance_status.test_user_limit_compliant ? "yes" : "no" }}</strong></li>
        </ul>
        <p class="muted" style="margin-top: 0.6rem;">
          Test users are provisioned automatically per scenario: peer-to-peer tests (video/DM/documents)
          create 2 hashed <code>test-user-*</code> accounts with random secure hex passwords; group tests create
          3 or more based on participant requirements, then teardown after run completion.
        </p>
        <p v-if="bootstrap.feature_flags.group_testing_enabled" class="muted" style="margin-top: 0.4rem;">
          Group testing feature flag is enabled: optional temporary third participant slot available for approved rekey/access-loss scenarios.
        </p>
      </article>
    </div>

    <p class="visually-hidden" aria-live="polite">
      Current test lab state {{ runState }}. Selected scenario {{ selectedScenario?.label }}.
    </p>
  </section>
</template>