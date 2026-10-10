"use client";

// PF12: webhook endpoints of the signed-in account (the API's /webhooks
// routes, with the session; /v1/webhooks is the same for API keys).
import { api } from "@/lib/api";

export interface WebhookDelivery {
  delivery_id: string;
  endpoint_id: string;
  event_id: string;
  event_type: string | null;
  attempt: number;
  status: "pending" | "succeeded" | "failed" | "cancelled";
  next_attempt_at: string | null;
  response_code: number | null;
  response_ms: number | null;
  error: string | null;
  delivered_at: string | null;
  created_at: string;
  manual: boolean;
}

export interface WebhookEndpoint {
  endpoint_id: string;
  url: string;
  events: string[];
  active: boolean;
  description: string;
  failing_since: string | null;
  disabled_reason: "failing" | "owner" | null;
  created_at: string;
  last_delivery: WebhookDelivery | null;
  /** Only when it was just made or rotated. */
  secret?: string;
}

export interface WebhookList {
  endpoints: WebhookEndpoint[];
  events: string[];
  descriptions: Record<string, string>;
}

export const listWebhooks = () => api<WebhookList>("/webhooks");
export const createWebhook = (url: string, events: string[], description = "") =>
  api<WebhookEndpoint>("/webhooks", { method: "POST", json: { url, events, description } });
export const updateWebhook = (id: string, patch: Partial<Pick<WebhookEndpoint, "url" | "events" | "description" | "active">>) =>
  api<WebhookEndpoint>(`/webhooks/${id}`, { method: "PATCH", json: patch });
export const deleteWebhook = (id: string) => api<void>(`/webhooks/${id}`, { method: "DELETE" });
export const listDeliveries = (id: string) =>
  api<{ deliveries: WebhookDelivery[] }>(`/webhooks/${id}/deliveries?limit=20`);
export const resendDelivery = (id: string, deliveryId: string) =>
  api<WebhookDelivery>(`/webhooks/${id}/deliveries/${deliveryId}/resend`, { method: "POST" });
export const revealSecret = (id: string) => api<{ endpoint_id: string; secret: string }>(`/webhooks/${id}/secret`);
export const rotateSecret = (id: string) =>
  api<{ endpoint_id: string; secret: string }>(`/webhooks/${id}/secret/rotate`, { method: "POST" });
export const sendTest = (id: string) => api<WebhookDelivery>(`/webhooks/${id}/test`, { method: "POST" });
