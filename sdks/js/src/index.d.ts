// Types of @truebex/sdk. The operation groups are generated (operations.d.ts)
// from openapi/v1.json; the schemas by openapi-typescript (schema.d.ts).
import type {
  AccountApi,
  FeedsApi,
  JobsApi,
  MarketApi,
  ProjectsApi,
  SharesApi,
  UploadsApi,
  WebhooksApi,
} from "./operations";

export type { components, operations, paths } from "./schema";
export type { CallOptions } from "./operations";
export { OPERATIONS } from "./operations";
export { verifyWebhook, signWebhook, WebhookVerificationError } from "./webhooks";

export declare const DEFAULT_BASE_URL: string;

export declare class TruebexError extends Error {
  readonly status: number;
  /** The envelope's code: forbidden, not_found, validation_failed, rate_limited … */
  readonly code: string;
  readonly detail: string;
  readonly data: Record<string, unknown> | null;
  readonly requestId: string | null;
  readonly retryAfterS: number | null;
}

export interface TruebexOptions {
  /** Defaults to process.env.TRUEBEX_API_KEY. */
  apiKey?: string;
  /** Defaults to https://api.truebex.com. */
  baseUrl?: string;
  /** Retries on 429, 5xx and network errors (writes only with an idempotency key). Default 2. */
  maxRetries?: number;
  fetch?: typeof fetch;
}

export declare class Truebex {
  constructor(options?: TruebexOptions);
  readonly baseUrl: string;
  readonly account: AccountApi;
  readonly projects: ProjectsApi;
  readonly jobs: JobsApi;
  readonly uploads: UploadsApi;
  readonly shares: SharesApi;
  readonly market: MarketApi;
  readonly feeds: FeedsApi;
  readonly webhooks: WebhooksApi;
}
