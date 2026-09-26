/**
 * The sheet's own half of the bridge.
 *
 * It lives inside the spreadsheet, so there is no Google Cloud project,
 * no OAuth screen and no key. The agent posts rows to one URL and this
 * writes them.
 *
 * Paste this into Extensions -> Apps Script, then Deploy -> New
 * deployment -> Web app, running as yourself, with access set to
 * "Anyone with the link". Copy the URL it gives back.
 */

/**
 * Which spreadsheet this writes to.
 *
 * It is the long code in the sheet's own address, between /d/ and
 * /edit. Naming it here means the script works whether it was made
 * from inside the sheet or on its own, and a script that only works
 * one of those ways is a script that breaks when someone copies it.
 */
var SHEET_ID = 'put-the-id-here';

/** The tabs this writes to. They are made on the first run. */
var ROWS_TAB = 'rows';
var QUESTIONS_TAB = 'questions';

/**
 * A word only the agent knows, so a stranger with the URL writes
 * nothing. Change it here and in the agent's keychain entry.
 */
var SHARED_WORD = 'porta-do-armazem-4417';

/** Take a batch of rows from the agent. */
function doPost(request) {
  try {
    var asked = JSON.parse(request.postData.contents);
    if (asked.word !== SHARED_WORD) {
      return reply({ok: false, why: 'wrong word'});
    }
    var written = replaceTab(
      asked.tab, asked.columns, asked.rows, asked.money || []
    );
    return reply({ok: true, written: written, tab: asked.tab});
  } catch (failure) {
    return reply({ok: false, why: String(failure)});
  }
}

/** Say the sheet is alive, so a setup can be checked in a browser. */
function doGet() {
  return reply({ok: true, tabs: [ROWS_TAB, QUESTIONS_TAB]});
}

/**
 * Write one tab from scratch.
 *
 * The agent sends the whole table every run, so the sheet is replaced
 * rather than appended to. Appending would double every row on a
 * second run, and a sheet nobody can trust is worse than no sheet.
 */
function replaceTab(name, columns, rows, money) {
  var book = SpreadsheetApp.openById(SHEET_ID);
  var tab = book.getSheetByName(name) || book.insertSheet(name);
  tab.clear();
  var table = [columns];
  for (var i = 0; i < rows.length; i++) {
    var line = [];
    for (var c = 0; c < columns.length; c++) {
      line.push(rows[i][columns[c]] === undefined ? '' : rows[i][columns[c]]);
    }
    table.push(line);
  }
  tab.getRange(1, 1, table.length, columns.length).setValues(table);
  tab.getRange(1, 1, 1, columns.length).setFontWeight('bold');
  tab.setFrozenRows(1);
  showCents(tab, columns, money, table.length);
  return rows.length;
}

/**
 * Show money to the cent.
 *
 * A sheet reads 3480.00 as a number and prints 3480, which on a column
 * of invoice totals looks like a rounding nobody asked for. The amount
 * stays a number, so it can still be added up; only the printing
 * changes.
 */
function showCents(tab, columns, money, height) {
  if (!money.length || height < 2) {
    return;
  }
  for (var i = 0; i < money.length; i++) {
    var at = columns.indexOf(money[i]);
    if (at >= 0) {
      tab.getRange(2, at + 1, height - 1, 1).setNumberFormat('0.00');
    }
  }
}

/** One answer, as JSON. */
function reply(body) {
  return ContentService
    .createTextOutput(JSON.stringify(body))
    .setMimeType(ContentService.MimeType.JSON);
}
