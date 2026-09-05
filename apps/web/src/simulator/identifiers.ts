// v1.0 | 05-Sep-2026 | Generate browser identifiers with an insecure-context fallback.

export interface IdentifierCrypto {
  randomUUID?: () => string;
  getRandomValues(array: Uint8Array): Uint8Array;
}

function formatUuid(bytes: Uint8Array): string {
  const hexadecimalBytes = Array.from(bytes, (byte) =>
    byte.toString(16).padStart(2, "0"),
  );
  return [
    hexadecimalBytes.slice(0, 4).join(""),
    hexadecimalBytes.slice(4, 6).join(""),
    hexadecimalBytes.slice(6, 8).join(""),
    hexadecimalBytes.slice(8, 10).join(""),
    hexadecimalBytes.slice(10, 16).join(""),
  ].join("-");
}

export function createIdentifier(
  prefix: string,
  cryptoApi: IdentifierCrypto = globalThis.crypto,
): string {
  if (typeof cryptoApi.randomUUID === "function") {
    return `${prefix}-${cryptoApi.randomUUID()}`;
  }

  const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  return `${prefix}-${formatUuid(bytes)}`;
}
