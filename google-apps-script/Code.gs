/**
 * Truebex demo request -> Google Sheets
 *
 * Setup:
 * 1. Create a Google Sheet. Note its ID from the URL:
 *    https://docs.google.com/spreadsheets/d/<THIS_IS_THE_ID>/edit
 * 2. Open Extensions > Apps Script in that sheet (the script is then
 *    bound to it and getActiveSpreadsheet() works — no ID needed).
 *    Alternatively, set SHEET_ID below to use a standalone script.
 * 3. Paste this file, Save.
 * 4. Deploy > New deployment > type "Web app":
 *      - Execute as: Me
 *      - Who has access: Anyone
 *    Copy the Web app URL into the site's NEXT_PUBLIC_SHEETS_URL.
 * 5. Re-deploy (or "Manage deployments" > edit) after any code change.
 */

// Leave blank to use the sheet this script is bound to.
var SHEET_ID = "";
var SHEET_NAME = "Demo Requests";
var HEADERS = ["timestamp", "name", "email", "company", "project_description"];

function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000); // serialize concurrent submissions

  try {
    var sheet = getSheet_();

    var params = (e && e.parameter) || {};
    sheet.appendRow([
      new Date(),
      params.name || "",
      params.email || "",
      params.company || "",
      params.project_description || "",
    ]);

    return json_({ result: "success" });
  } catch (err) {
    return json_({ result: "error", message: String(err) });
  } finally {
    lock.releaseLock();
  }
}

// Simple health check when visiting the URL in a browser.
function doGet() {
  return json_({ result: "ok" });
}

function getSheet_() {
  var ss = SHEET_ID
    ? SpreadsheetApp.openById(SHEET_ID)
    : SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(HEADERS);
  } else if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
  }
  return sheet;
}

function json_(obj) {
  return ContentService.createTextOutput(
    JSON.stringify(obj)
  ).setMimeType(ContentService.MimeType.JSON);
}
