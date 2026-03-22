const encoder = new TextEncoder();
const decoder = new TextDecoder();

function toBase64(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes));
}

function fromBase64(input: string): Uint8Array {
  return Uint8Array.from(atob(input), (c) => c.charCodeAt(0));
}

export async function generateIdentityKeypair(): Promise<CryptoKeyPair> {
  try {
    // Modern high-security curve for key agreement (when supported by browser).
    return await window.crypto.subtle.generateKey(
      {
        name: "X25519",
      } as AlgorithmIdentifier,
      true,
      ["deriveKey", "deriveBits"],
    );
  } catch {
    // Compatibility fallback.
    return window.crypto.subtle.generateKey(
      {
        name: "ECDH",
        namedCurve: "P-256",
      },
      true,
      ["deriveKey", "deriveBits"],
    );
  }
}

export async function exportPublicKey(key: CryptoKey): Promise<string> {
  const raw = await window.crypto.subtle.exportKey("raw", key);
  return toBase64(new Uint8Array(raw));
}

async function importAesKey(raw: Uint8Array): Promise<CryptoKey> {
  return window.crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
}

export async function generateConversationKey(): Promise<string> {
  const raw = window.crypto.getRandomValues(new Uint8Array(32));
  return toBase64(raw);
}

export async function encryptText(plaintext: string, base64Key: string): Promise<{ ciphertext: string; nonce: string }> {
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const key = await importAesKey(fromBase64(base64Key));
  const encrypted = await window.crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv,
    },
    key,
    encoder.encode(plaintext),
  );

  return {
    ciphertext: toBase64(new Uint8Array(encrypted)),
    nonce: toBase64(iv),
  };
}

export async function decryptText(ciphertext: string, nonce: string, base64Key: string): Promise<string> {
  const key = await importAesKey(fromBase64(base64Key));
  const plain = await window.crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: fromBase64(nonce),
    },
    key,
    fromBase64(ciphertext),
  );
  return decoder.decode(plain);
}

export async function encryptFile(file: File): Promise<{ encrypted: Blob; key: string; nonce: string; sha256: string }> {
  const key = await generateConversationKey();
  const nonceBytes = window.crypto.getRandomValues(new Uint8Array(12));
  const aes = await importAesKey(fromBase64(key));
  const raw = await file.arrayBuffer();
  const digest = await window.crypto.subtle.digest("SHA-256", raw);
  const encrypted = await window.crypto.subtle.encrypt({ name: "AES-GCM", iv: nonceBytes }, aes, raw);

  return {
    encrypted: new Blob([encrypted], { type: "application/octet-stream" }),
    key,
    nonce: toBase64(nonceBytes),
    sha256: toBase64(new Uint8Array(digest)),
  };
}

export async function decryptFile(
  encryptedBlob: Blob,
  base64Key: string,
  nonce: string,
  mimeType = "application/octet-stream",
): Promise<Blob> {
  const aes = await importAesKey(fromBase64(base64Key));
  const raw = await encryptedBlob.arrayBuffer();
  const decrypted = await window.crypto.subtle.decrypt(
    { name: "AES-GCM", iv: fromBase64(nonce) },
    aes,
    raw,
  );
  return new Blob([decrypted], { type: mimeType });
}
