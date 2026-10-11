import { DevPage } from "@/components/developers/DevDocs";
import { groupMetadata } from "@/components/developers/GroupDocPage";
import { DEVELOPER_DOCS as D } from "@/lib/constants";
import { apiDocument, camel, operations } from "@/lib/developer-docs";

export const metadata = groupMetadata("sdks");

const PYTHON = `import truebex

client = truebex.Client()  # reads TRUEBEX_API_KEY
project = client.projects.create(name="House", doc_version=38)
ops = client.projects.pull_ops(project["project_id"], after=0, wait_s=25)

try:
    client.projects.delete(project["project_id"])
except truebex.TruebexError as err:
    print(err.status, err.code)  # 403 session_required`;

const JS = `import { Truebex, TruebexError } from "@truebex/sdk";

const truebex = new Truebex(); // reads process.env.TRUEBEX_API_KEY
const project = await truebex.projects.create({ name: "House", doc_version: 38 });
const { ops } = await truebex.projects.pullOps(project.project_id, { after: 0, wait_s: 25 });`;

export default function SdksDocs() {
  const page = D.pages.sdks;
  const version = apiDocument().info.version;
  const ops = operations(["account", "projects", "jobs", "uploads", "shares", "market", "feeds", "webhooks"]);
  return (
    <DevPage
      slug="sdks"
      h1={page.h1}
      intro={page.intro}
      description={page.description}
      status={D.sdksPublished ? undefined : page.status}
      statusLabel={D.rollingOut}
    >
      <h2 id="install">{page.installTitle}</h2>
      <pre>
        <code>{`pip install truebex          # Python 3.11+, version ${version}\nnpm install @truebex/sdk     # Node 18+, browsers, workers`}</code>
      </pre>
      <h2 id="python">{page.pythonTitle}</h2>
      <pre>
        <code>{PYTHON}</code>
      </pre>
      <h2 id="javascript">{page.jsTitle}</h2>
      <pre>
        <code>{JS}</code>
      </pre>
      <h2 id="methods">{page.methodsTitle}</h2>
      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>{page.operation}</th>
              <th>{page.python}</th>
              <th>{page.javascript}</th>
            </tr>
          </thead>
          <tbody>
            {ops.map((op) => {
              const [group, ...rest] = op.id.split("_");
              const name = rest.join("_");
              return (
                <tr key={op.id} data-operation={op.id}>
                  <td>
                    <code>
                      {op.method} {op.path}
                    </code>
                  </td>
                  <td>
                    <code>
                      client.{group}.{name}()
                    </code>
                  </td>
                  <td>
                    <code>
                      truebex.{group}.{camel(name)}()
                    </code>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </DevPage>
  );
}
