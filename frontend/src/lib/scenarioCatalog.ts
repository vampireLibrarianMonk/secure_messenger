export type ScenarioCategory = "dm" | "video" | "document" | "full" | "group";

export interface ScenarioDefinition {
  id: string;
  label: string;
  description: string;
  category: ScenarioCategory;
  requiredParticipants: number;
  environmentPresets: string[];
  intensityPresets: Array<"quick" | "standard" | "exhaustive">;
  orderedSteps: string[];
  featureFlag?: "group_testing_enabled";
}

export const scenarioCatalog: ScenarioDefinition[] = [
  {
    id: "dm-basic",
    label: "DM basic encrypted exchange",
    description: "Validate synthetic direct-message encryption flow and recipient delivery.",
    category: "dm",
    requiredParticipants: 2,
    environmentPresets: ["local sandbox", "staging simulator", "reconnect simulation"],
    intensityPresets: ["quick", "standard", "exhaustive"],
    orderedSteps: ["session", "encrypt", "route", "fetch", "decrypt"],
  },
  {
    id: "video-e2ee",
    label: "Video E2EE verification test",
    description: "Simulate signaling, ICE, relay/direct selection, DTLS, and app E2EE checks.",
    category: "video",
    requiredParticipants: 2,
    environmentPresets: ["local sandbox", "degraded relay environment", "packet-loss simulation"],
    intensityPresets: ["quick", "standard", "exhaustive"],
    orderedSteps: ["signal", "ice", "relay/direct", "dtls", "e2ee-check"],
  },
  {
    id: "document-encrypted",
    label: "Document upload/download encrypted flow",
    description: "Exercise synthetic file-key generation and encrypted blob transfer path.",
    category: "document",
    requiredParticipants: 2,
    environmentPresets: ["local sandbox", "staging simulator", "reconnect simulation"],
    intensityPresets: ["quick", "standard", "exhaustive"],
    orderedSteps: ["file-key", "encrypt-blob", "upload", "wrap-key", "fetch", "decrypt"],
  },
  {
    id: "full-suite",
    label: "Full communication suite",
    description: "Run DM, video, and document synthetic checks as one ordered scenario.",
    category: "full",
    requiredParticipants: 2,
    environmentPresets: ["local sandbox", "staging simulator", "unknown/unverified branch"],
    intensityPresets: ["standard", "exhaustive"],
    orderedSteps: ["dm", "video", "document", "result"],
  },
  {
    id: "group-join-rekey",
    label: "Group join and rekey test",
    description: "Optional synthetic third-user scenario for membership change and rekey behavior.",
    category: "group",
    requiredParticipants: 3,
    environmentPresets: ["staging simulator", "unknown/unverified branch"],
    intensityPresets: ["standard", "exhaustive"],
    orderedSteps: ["group-init", "membership-change", "rekey", "redistribute", "access-check"],
    featureFlag: "group_testing_enabled",
  },
  {
    id: "group-remove-access-loss",
    label: "Group remove and access-loss test",
    description: "Validate removed participant cannot access newly protected group content.",
    category: "group",
    requiredParticipants: 3,
    environmentPresets: ["staging simulator", "unknown/unverified branch"],
    intensityPresets: ["standard", "exhaustive"],
    orderedSteps: ["group-init", "membership-change", "rekey", "post-removal-access-check", "result"],
    featureFlag: "group_testing_enabled",
  },
  {
    id: "group-call-membership-change",
    label: "Group call membership-change test",
    description: "Exercise join/leave signaling and security state updates in group-call simulation.",
    category: "group",
    requiredParticipants: 3,
    environmentPresets: ["staging simulator", "degraded relay environment", "unknown/unverified branch"],
    intensityPresets: ["standard", "exhaustive"],
    orderedSteps: ["group-call-init", "membership-change", "rekey", "sender-key-distribute", "access-check", "result"],
    featureFlag: "group_testing_enabled",
  },
];
