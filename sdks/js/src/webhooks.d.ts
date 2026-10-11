export declare class WebhookVerificationError extends Error {}

type Headers = { get(name: string): string | null } | Record<string, string | string[] | undefined>;

/** `v1,<base64 HMAC-SHA256 of "id.timestamp.body">`. */
export declare function signWebhook(secret: string, msgId: string, timestamp: number, body: string | Uint8Array | ArrayBuffer): Promise<string>;

/** The parsed event when the signature matches and the timestamp is within `toleranceS` (300 s). */
export declare function verifyWebhook<T = unknown>(
  secret: string,
  headers: Headers,
  body: string | Uint8Array | ArrayBuffer,
  options?: { toleranceS?: number; now?: number },
): Promise<T>;
