import { DevPage, Notes } from "@/components/developers/DevDocs";
import { groupMetadata } from "@/components/developers/GroupDocPage";
import { DEVELOPER_DOCS as D } from "@/lib/constants";
import { rulesOf, toolsDocument, typeOf, type Schema } from "@/lib/developer-docs";

export const metadata = groupMetadata("mcp");

function argumentRows(schema: Schema, prefix = ""): { name: string; schema: Schema; required: boolean }[] {
  const required = new Set(schema.required ?? []);
  return Object.entries(schema.properties ?? {}).flatMap(([name, prop]) => {
    const row = { name: prefix + name, schema: prop, required: required.has(name) };
    return prop.type === "object" && prop.properties ? [row, ...argumentRows(prop, `${prefix}${name}.`)] : [row];
  });
}

export default function McpDocs() {
  const page = D.pages.mcp;
  const tools = toolsDocument();
  return (
    <DevPage slug="mcp" h1={page.h1} intro={page.intro} description={page.description} status={page.status}>
      <h2 id="install">{page.installTitle}</h2>
      {!D.mcpPublished && (
        <p>
          <span className="font-semibold text-warn">{D.rollingOut}:</span> {page.publishing}
        </p>
      )}
      {page.installNotes.map((n) => (
        <div key={n.client}>
          <h3>{n.client}</h3>
          <p>{n.text}</p>
          <pre>
            <code>{n.code}</code>
          </pre>
        </div>
      ))}

      <h2 id="tools">{page.toolsTitle}</h2>
      <p>{page.classesText}</p>
      <p className="text-sm">
        tools.json <code>{tools.version}</code>
      </p>
      {tools.tools.map((t) => {
        const klass = t._meta["com.truebex/permission"];
        return (
          <section key={t.name} id={t.name} data-tool={t.name} className="mt-10 border-t border-border pt-6">
            <h3 className="!mt-0 flex flex-wrap items-baseline gap-2">
              <code className="text-accent">{t.name}</code>
              <span>{t.title}</span>
            </h3>
            <p>{t.description}</p>
            <p className="text-sm">
              {page.klass}: <code data-class={klass}>{klass}</code>
              {t._meta["com.truebex/logSafe"] ? <span> · {page.logSafe}</span> : null}
            </p>
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>{page.argument}</th>
                    <th>{D.reference.type}</th>
                    <th>{D.reference.required}</th>
                    <th>{page.rules}</th>
                  </tr>
                </thead>
                <tbody>
                  {argumentRows(t.inputSchema).map((a) => (
                    <tr key={a.name} data-argument={a.name}>
                      <td>
                        <code>{a.name}</code>
                      </td>
                      <td>
                        <code className="break-all">{typeOf(a.schema)}</code>
                      </td>
                      <td>{a.required ? D.reference.yes : ""}</td>
                      <td className="break-all">{rulesOf(a.schema)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}

      <Notes title={page.safetyTitle} notes={page.safety} />
    </DevPage>
  );
}
