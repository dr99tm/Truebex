# Demo Request → Google Sheets

The demo request form posts submissions to a Google Apps Script Web App,
which appends each one as a row in a Google Sheet. This replaces the old
FastAPI server (`server/main.py`, now removed).

## One-time setup

1. **Create a Google Sheet** (e.g. "Truebex Demo Requests").
2. In that sheet: **Extensions → Apps Script**.
3. Delete the default `Code.gs` content and paste [`Code.gs`](./Code.gs). Save.
4. **Deploy → New deployment**:
   - Select type: **Web app**
   - **Execute as:** Me
   - **Who has access:** Anyone
   - Click **Deploy**, authorize when prompted, and **copy the Web app URL**
     (looks like `https://script.google.com/macros/s/.../exec`).
5. Put that URL in the site's env file:
   ```
   # .env.local
   NEXT_PUBLIC_SHEETS_URL=https://script.google.com/macros/s/.../exec
   ```
6. Rebuild and deploy the site (`build-to-directory.ps1` or
   `deploy-to-server.bat`). The URL is baked into the static bundle at
   build time, so a rebuild is required after changing it.

## Notes

- The form sends data with `mode: "no-cors"` and URL-encoded fields. The
  browser can't read the response (it's opaque), so the UI treats "no
  network error" as success. This is the standard, reliable way to post to
  an Apps Script Web App from a static site without CORS preflight issues.
- After editing `Code.gs`, you must **re-deploy** (Manage deployments →
  edit the existing deployment → Deploy) for changes to take effect. The
  Web app URL stays the same if you edit the existing deployment.
- Columns written: `timestamp, name, email, company, project_description`.
- Old submissions from the previous server were backed up to
  `demo_requests_backup.csv` at the repo root; you can import that into the
  sheet via **File → Import** if you want the history.
