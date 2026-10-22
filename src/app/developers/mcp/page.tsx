import { Fragment } from "react";
import { DevPage, Notes } from "@/components/developers/DevDocs";
import { groupMetadata } from "@/components/developers/GroupDocPage";
import { DEVELOPER_DOCS as D } from "@/lib/constants";
import {
  argumentRows,
  nestedFields,
  rulesOf,
  toolsDocument,
  typeOf,
  withToolCount,
  type ArgumentRow,
  type Schema,
} from "@/lib/developer-docs";

// PF12d: the tool count in the page's words is the number of tools the server lists ({tools} in the copy).
export const metadata = groupMetadata("mcp", withToolCount(D.pages.mcp.description));

// An argument with no type (set_tunable's value: the portable subset of agent-interface §6.5 has no type
// list) shows the page's own words for what it takes, never an empty cell.
function argumentType(tool: string, name: string, schema: Schema, untyped: Record<string, string>, fallback: string) {
  const typed = schema.type !== undefined || schema.enum || schema.const !== undefined || schema.anyOf || schema.$ref;
  return typed ? typeOf(schema) : (untyped[`${tool}.${name}`] ?? fallback);
}

// PF12d: an object argument (create_layout's program) or an array of objects (create_object's parts) lists its
// fields in one compact row under its own: name, type, required, rules, description.
function NestedFields({ tool, of, items, fields }: { tool: string; of: string; items: boolean; fields: ArgumentRow[] }) {
  const page = D.pages.mcp;
  return (
    <tr data-fields-of={of}>
      <td colSpan={5} className="pb-3 pl-8 pt-0">
        <p className="my-1 text-xs text-text-muted">{items ? page.itemsLabel : page.fieldsLabel}</p>
        <ul className="my-1 space-y-1 pl-5">
          {fields.map((f) => {
            const rules = rulesOf(f.schema);
            return (
              <li key={f.name} data-field={f.name} data-required={f.required ? "" : undefined}>
                <code>{f.name}</code>{" "}
                <code>{argumentType(tool, `${of}.${f.name}`, f.schema, page.untypedTypes, page.untypedFallback)}</code>
                {f.required ? ` · ${page.itemRequired}` : null}
                {rules ? ` · ${rules}` : null}
                {f.schema.description ? ` — ${f.schema.description}` : null}
              </li>
            );
          })}
        </ul>
      </td>
    </tr>
  );
}

function CodeBlock({ code }: { code: string }) {
  return (
    <pre>
      <code>{code}</code>
    </pre>
  );
}

// PF12b: generated at build time from src/content/tools.json (the app's own file,
// copied by scripts/sync-mcp.ps1); the words around it are DEVELOPER_DOCS.pages.mcp.
// PF12c: only the tools on the mcp surface (toolsDocument), as the server lists them.
export default function McpDocs() {
  const page = D.pages.mcp;
  const tools = toolsDocument();
  const counted = (text: string) => withToolCount(text, tools.tools);
  const requiresText: Record<string, string> = page.requiresText;
  const untypedTypes: Record<string, string> = page.untypedTypes;
  return (
    <DevPage slug="mcp" h1={page.h1} intro={page.intro} description={counted(page.description)} status={page.status}>
      <h2 id="connect">{page.connectTitle}</h2>
      <ol className="my-4 list-decimal space-y-2 pl-6">
        {page.connectSteps.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ol>

      <h2 id="install">{page.installTitle}</h2>
      {page.installNotes.map((n) => (
        <div key={n.client} data-install={n.client}>
          <h3>{n.client}</h3>
          <p>{counted(n.text)}</p>
          <CodeBlock code={n.code} />
        </div>
      ))}
      {D.mcpPublished ? (
        <div data-install="npm">
          <h3>{page.npmTitle}</h3>
          <p>{page.npmText}</p>
          {page.npmNotes.map((n) => (
            <div key={n.client}>
              <p className="text-sm">{n.client}</p>
              <CodeBlock code={n.code} />
            </div>
          ))}
        </div>
      ) : (
        <p>
          <span className="font-semibold text-warn">{D.rollingOut}:</span> {page.publishing}
        </p>
      )}
      <h3>{page.pinTitle}</h3>
      <p>{page.pinText}</p>

      <h2 id="tools">{page.toolsTitle}</h2>
      <p>{page.classesText}</p>
      <p className="text-sm">
        tools.json <code>{tools.version}</code>
      </p>
      {tools.tools.map((t) => {
        const klass = t._meta["com.truebex/permission"];
        const requires = t._meta["com.truebex/requires"];
        return (
          <section key={t.name} id={t.name} data-tool={t.name} className="mt-10 border-t border-border pt-6">
            <h3 className="!mt-0 flex flex-wrap items-baseline gap-2">
              <code className="text-accent">{t.name}</code>
              <span>{t.title}</span>
            </h3>
            <p>{t.description}</p>
            <p className="text-sm">
              {page.klass}: <code data-class={klass}>{klass}</code>
              {/* the project log takes log-safe edits only (project-log §6.2): a read marked logSafe never travels */}
              {t._meta["com.truebex/logSafe"] && klass === "edit" ? <span> · {page.logSafe}</span> : null}
            </p>
            {requires ? (
              <p className="text-sm" data-requires>
                <span className="font-semibold text-warn">{D.onRoadmap}:</span> {requiresText[requires] ?? page.requiresFallback}
              </p>
            ) : null}
            <div className="overflow-x-auto">
              <table className="min-w-[44rem]">
                <thead>
                  <tr>
                    <th>{page.argument}</th>
                    <th>{D.reference.type}</th>
                    <th>{D.reference.required}</th>
                    <th>{page.rules}</th>
                    <th>{D.reference.description}</th>
                  </tr>
                </thead>
                <tbody>
                  {argumentRows(t.inputSchema).map((a) => {
                    const fields = nestedFields(a.schema);
                    return (
                      <Fragment key={a.name}>
                        <tr data-argument={a.name} className={fields.length ? "[&>td]:border-b-0" : undefined}>
                          <td>
                            <code>{a.name}</code>
                          </td>
                          <td>
                            <code>{argumentType(t.name, a.name, a.schema, untypedTypes, page.untypedFallback)}</code>
                          </td>
                          <td>{a.required ? D.reference.yes : ""}</td>
                          <td>{rulesOf(a.schema)}</td>
                          <td>{a.schema.description ?? ""}</td>
                        </tr>
                        {fields.length ? (
                          <NestedFields tool={t.name} of={a.name} items={a.schema.type === "array"} fields={fields} />
                        ) : null}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}

      <h2 id="resources">{page.resourcesTitle}</h2>
      <p>{page.resourcesText}</p>
      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>{page.resource}</th>
              <th>{page.holds}</th>
            </tr>
          </thead>
          <tbody>
            {page.resources.map((r) => (
              <tr key={r.uri} data-resource={r.uri}>
                <td>
                  <code className="break-all">{r.uri}</code>
                </td>
                <td>{r.text}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 id="errors">{page.errorsTitle}</h2>
      <p>{page.errorsText}</p>
      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>{page.errorCode}</th>
              <th>{page.errorMeaning}</th>
            </tr>
          </thead>
          <tbody>
            {page.errors.map((e) => (
              <tr key={e.code} data-error={e.code}>
                <td>
                  <code>{e.code}</code>
                </td>
                <td>{e.meaning}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Notes title={page.safetyTitle} notes={page.safety} />
    </DevPage>
  );
}
