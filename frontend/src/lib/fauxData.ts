const fauxNodes = ["faux_node_alpha", "faux_node_bravo", "faux_node_charlie", "faux_relay_01"];

export interface FauxTestUserAccount {
  username: string;
  passwordHex: string;
  assignedNode: string;
}

function secureRandomHex(length = 32): string {
  const bytesNeeded = Math.ceil(length / 2);
  const bytes = new Uint8Array(bytesNeeded);
  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("").slice(0, length);
}

export function generateRunId(): string {
  return `sim_run_${Math.floor(1000 + Math.random() * 9000)}`;
}

export function pickParticipants(count: number): string[] {
  return fauxNodes.slice(0, Math.max(2, Math.min(count, 3)));
}

export function generateFauxTestUsers(count: number): FauxTestUserAccount[] {
  const boundedCount = Math.max(2, Math.min(count, fauxNodes.length));
  return Array.from({ length: boundedCount }, (_, index) => {
    const hash = secureRandomHex(8);
    return {
      username: `test-user-${hash}`,
      passwordHex: secureRandomHex(32),
      assignedNode: fauxNodes[index] ?? `faux_node_${index + 1}`,
    };
  });
}

export function buildSyntheticMessageFlow(
  category: "dm" | "video" | "document" | "full" | "group",
  users: FauxTestUserAccount[],
  step: number,
): string {
  if (users.length < 2) {
    return "insufficient synthetic users for message routing";
  }

  const sender = users[step % users.length];
  const recipients = users.filter((user) => user.username !== sender.username);
  const recipientText = recipients.map((r) => r.username).join(", ");

  if (category === "video") {
    return `${sender.username} -> ${recipientText} [video frame + signaling envelope #${step + 1}]`;
  }
  if (category === "document") {
    return `${sender.username} -> ${recipientText} [encrypted document key-wrap #${step + 1}]`;
  }
  if (category === "group") {
    return `${sender.username} -> ${recipientText} [group broadcast packet #${step + 1}]`;
  }
  if (category === "full") {
    return `${sender.username} -> ${recipientText} [suite event #${step + 1}: dm/video/document chain]`;
  }
  return `${sender.username} -> ${recipientText} [dm ciphertext #${step + 1}]`;
}
