import { DevPage, OperationReference } from "@/components/developers/DevDocs";
import { groupMetadata } from "@/components/developers/GroupDocPage";
import { DEVELOPER_DOCS as D } from "@/lib/constants";
import { apiDocument, operations } from "@/lib/developer-docs";

export const metadata = groupMetadata("webhooks");

function wait(seconds: number): string {
  if (seconds === 0) return D.pages.webhooks.immediately;
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${seconds / 60} min`;
  return `${seconds / 3600} h`;
}

function fill(text: string, values: Record<string, string | number>): string {
  return text.replace(/\{(\w+)\}/g, (_, k: string) => String(values[k] ?? ""));
}

const VERIFY_PY = `import os, truebex

event = truebex.verify_webhook(
    os.environ["TRUEBEX_WEBHOOK_SECRET"], request.headers, request.body
)
print(event["type"], event["data"])`;

const VERIFY_JS = `import { verifyWebhook } from "@truebex/sdk/webhooks";

const event = await verifyWebhook(process.env.TRUEBEX_WEBHOOK_SECRET, req.headers, rawBody);`;

const HEADERS = `POST /your/endpoint
content-type: application/json
webhook-id: msg_0199c6…
webhook-timestamp: 1791763200
webhook-signature: v1,K5oZfzN95Z9UVu1EsfQmfVNQhnkZ2pj9o9NDN/H/pI4=

{"type":"share.published","timestamp":"2026-10-11T09:00:00Z","data":{…}}`;

export default function WebhooksDocs() {
  const page = D.pages.webhooks;
  const doc = apiDocument();
  const hooks = doc["x-truebex-webhooks"];
  return (
    <DevPage slug="webhooks" h1={page.h1} intro={page.intro} description={page.description}>
      <h2 id="verify">{page.verifyTitle}</h2>
      <p>{page.verifyText}</p>
      <pre>
        <code>{HEADERS}</code>
      </pre>
      <h3>Python</h3>
      <pre>
        <code>{VERIFY_PY}</code>
      </pre>
      <h3>JavaScript</h3>
      <pre>
        <code>{VERIFY_JS}</code>
      </pre>

      <h2 id="events">{page.eventsTitle}</h2>
      <p>{fill(page.eventsText, { debounce: hooks.debounce_s })}</p>
      <table>
        <thead>
          <tr>
            <th>{page.event}</th>
            <th>{page.when}</th>
          </tr>
        </thead>
        <tbody>
          {doc["x-truebex-webhook-events"].map((e) => (
            <tr key={e.type} data-event={e.type}>
              <td>
                <code>{e.type}</code>
              </td>
              <td>{e.description}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 id="retries">{page.retriesTitle}</h2>
      <p>
        {fill(page.retriesText, { timeout: hooks.timeout_s, disable: hooks.disable_after_days, keep: hooks.keep_days })}
      </p>
      <table>
        <thead>
          <tr>
            <th>{page.attempt}</th>
            <th>{page.after}</th>
          </tr>
        </thead>
        <tbody>
          {hooks.retry_after_s.map((s, i) => (
            <tr key={i}>
              <td>{i + 1}</td>
              <td>{wait(s)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 id="local">{page.localTitle}</h2>
      <p>{page.localText}</p>

      <OperationReference ops={operations(page.groups)} />
    </DevPage>
  );
}
