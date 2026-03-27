export type ProtectionResult =
  | "PASS — E2EE VERIFIED"
  | "PASS — TRANSPORT ONLY"
  | "FAIL"
  | "UNKNOWN / UNVERIFIED";

export type ScenarioCategory = "dm" | "video" | "document" | "full" | "group";

export interface EvidenceSnapshot {
  scenario: ScenarioCategory;
  environment: string;
  warnings: number;
  hadFailure: boolean;
  dmClientEncryptConfirmed: boolean;
  dmCiphertextOnlyRoutingConfirmed: boolean;
  dmRecipientDecryptConfirmed: boolean;
  videoTransportProtected: boolean;
  videoAppLayerE2eeConfirmed: boolean;
  documentClientBlobEncryptionConfirmed: boolean;
  documentWrappedKeyTransferConfirmed: boolean;
  documentRecipientDecryptConfirmed: boolean;
  groupMembershipRekeyConfirmed: boolean;
  groupPostRemovalAccessDeniedConfirmed: boolean;
  sufficientEvidence: boolean;
}

export interface ResultSummarySeed {
  result: ProtectionResult;
  explanation: string;
  evidence: string[];
}

export function defaultResultSeed(category: string): ResultSummarySeed {
  if (category === "video") {
    return {
      result: "PASS — TRANSPORT ONLY",
      explanation: "Initial synthetic seed. Stage 5 will compute evidence-based classification.",
      evidence: ["Transport path placeholder created."],
    };
  }
  return {
    result: "UNKNOWN / UNVERIFIED",
    explanation: "Synthetic run scaffold generated. Evidence mapping arrives in Stage 5.",
    evidence: ["Evidence map not yet evaluated."],
  };
}

export function evaluateResultFromEvidence(snapshot: EvidenceSnapshot): ResultSummarySeed {
  const evidence: string[] = [];
  const envUnknown = snapshot.environment.toLowerCase().includes("unknown/unverified");

  if (snapshot.hadFailure) {
    return {
      result: "FAIL",
      explanation: "Synthetic execution encountered a failure branch before protection requirements were satisfied.",
      evidence: ["Failure branch signaled in ordered event stream."],
    };
  }

  if (!snapshot.sufficientEvidence || envUnknown) {
    evidence.push("Insufficient evidence chain for protection-level attestation.");
    if (envUnknown) {
      evidence.push("Environment selected unknown/unverified branch; trust boundary intentionally unresolved.");
    }
    if (snapshot.warnings > 0) {
      evidence.push(`Warning count (${snapshot.warnings}) requires manual verification.`);
    }
    return {
      result: "UNKNOWN / UNVERIFIED",
      explanation:
        "Run completed but cannot assert protection class because required evidence checkpoints are incomplete or explicitly unverified.",
      evidence,
    };
  }

  if (["dm", "full"].includes(snapshot.scenario)) {
    evidence.push(`DM client-side encryption: ${snapshot.dmClientEncryptConfirmed ? "confirmed" : "missing"}`);
    evidence.push(
      `DM ciphertext-only routing expectation: ${snapshot.dmCiphertextOnlyRoutingConfirmed ? "confirmed" : "missing"}`,
    );
    evidence.push(`DM recipient decrypt path: ${snapshot.dmRecipientDecryptConfirmed ? "confirmed" : "missing"}`);
  }

  if (["document", "full"].includes(snapshot.scenario)) {
    evidence.push(
      `Document client-side blob encryption: ${snapshot.documentClientBlobEncryptionConfirmed ? "confirmed" : "missing"}`,
    );
    evidence.push(
      `Document wrapped-key transfer: ${snapshot.documentWrappedKeyTransferConfirmed ? "confirmed" : "missing"}`,
    );
    evidence.push(
      `Document recipient decrypt confirmation: ${snapshot.documentRecipientDecryptConfirmed ? "confirmed" : "missing"}`,
    );
  }

  if (["group", "full"].includes(snapshot.scenario)) {
    evidence.push(
      `Group membership-change rekey behavior: ${snapshot.groupMembershipRekeyConfirmed ? "confirmed" : "missing"}`,
    );
    evidence.push(
      `Post-removal access denial check: ${snapshot.groupPostRemovalAccessDeniedConfirmed ? "confirmed" : "missing"}`,
    );
  }

  const e2eeChecksPass =
    snapshot.dmClientEncryptConfirmed &&
    snapshot.dmCiphertextOnlyRoutingConfirmed &&
    snapshot.dmRecipientDecryptConfirmed &&
    snapshot.documentClientBlobEncryptionConfirmed &&
    snapshot.documentWrappedKeyTransferConfirmed &&
    snapshot.documentRecipientDecryptConfirmed &&
    (snapshot.scenario !== "group" || (snapshot.groupMembershipRekeyConfirmed && snapshot.groupPostRemovalAccessDeniedConfirmed));

  if (snapshot.scenario === "video" && !snapshot.videoAppLayerE2eeConfirmed && snapshot.videoTransportProtected) {
    evidence.push("Video transport protection confirmed (DTLS/SRTP equivalent synthetic path). App-layer media E2EE not confirmed.");
    return {
      result: "PASS — TRANSPORT ONLY",
      explanation:
        "Video scenario validated transport protection but did not produce sufficient app-layer media encryption evidence.",
      evidence,
    };
  }

  if (snapshot.videoTransportProtected) {
    evidence.push("Video transport protection confirmed.");
  }
  if (snapshot.videoAppLayerE2eeConfirmed) {
    evidence.push("Video app-layer E2EE check confirmed.");
  }

  if (snapshot.scenario === "video") {
    if (snapshot.videoTransportProtected && snapshot.videoAppLayerE2eeConfirmed) {
      return {
        result: "PASS — E2EE VERIFIED",
        explanation: "Video scenario validated both transport and app-layer media encryption evidence.",
        evidence,
      };
    }
    return {
      result: "UNKNOWN / UNVERIFIED",
      explanation: "Video scenario did not meet evidence threshold for transport/E2EE classification.",
      evidence,
    };
  }

  if (e2eeChecksPass) {
    return {
      result: "PASS — E2EE VERIFIED",
      explanation:
        "Required synthetic evidence checkpoints for client-side encryption, protected routing semantics, and recipient decrypt confirmation were satisfied.",
      evidence,
    };
  }

  return {
    result: "UNKNOWN / UNVERIFIED",
    explanation: "Run completed but one or more domain evidence checkpoints are missing.",
    evidence,
  };
}
