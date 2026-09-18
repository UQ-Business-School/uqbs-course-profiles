/**
 * AoL register to course profiles feed (payload schema 1)
 *
 * An Office Script for UQBS-AoL-Register.xlsx. The Power Automate flow
 * "AoL register to course profiles" runs it every night and sends what it
 * returns to GitHub (UQ-Business-School/uqbs-course-profiles, event type
 * aol-register), where scraper/export_aol_register.py builds the feed that
 * the course profiles viewer reads.
 *
 * It only reads the register. It returns what the public feed shows and
 * nothing else: course, GA, assessment, status, First implemented and the
 * rubric file path. Learning designer names, coordinators, notes and folder
 * links never leave the workbook.
 *
 * The master copy of this script is automation/aol-register-feed.ts in the
 * repo. If you change the columns here, change PAYLOAD_COLUMNS in
 * export_aol_register.py in the same commit and bump the schema in both.
 */

interface RegisterFeed {
  schema: number;
  source: string;
  file_base: string;
  columns: string[];
  rows: string[][];
  row_count: number;
}

const TABLE_NAME = "AoLRegister";
const PAYLOAD_SCHEMA = 1;
const PAYLOAD_COLUMNS = ["course_code", "ga", "assessment", "status", "first_implemented", "rubric_file"];
// Register headings for the first five payload columns, in the same order.
const HEADINGS = ["Course code", "Graduate attribute", "Assessment", "Status", "First implemented"];
// The rubric file comes from the HYPERLINK formula in this column.
const RUBRIC_HEADING = "Rubric";
// GitHub takes an event payload of less than 64 KB. Measure the larger of the two
// shapes the flow can send (the object, or the object as a JSON string) and stop
// well short.
const MAX_BYTES = 58000;

function main(workbook: ExcelScript.Workbook): RegisterFeed {
  const table = workbook.getTable(TABLE_NAME);
  if (!table) {
    throw new Error(`There is no table called ${TABLE_NAME}. The register rows must stay inside that Excel table.`);
  }

  const headings = table.getHeaderRowRange().getValues()[0].map((h) => cellText(h));
  const columnOf = (name: string): number => {
    const i = headings.indexOf(name);
    if (i < 0) {
      throw new Error(`The ${TABLE_NAME} table has no "${name}" column. Rename it back, or change this script and the exporter together.`);
    }
    return i;
  };
  // Office Scripts only accept arrow functions as array callbacks.
  const cols = HEADINGS.map((name) => columnOf(name));
  const rubricCol = columnOf(RUBRIC_HEADING);

  const fileBaseName = workbook.getNamedItem("FileBase");
  if (!fileBaseName) {
    throw new Error("The FileBase name is missing (Formulas > Name Manager). It holds the SharePoint address of the course folders.");
  }
  const fileBase = cellText(fileBaseName.getRange().getValue());

  const rows: string[][] = [];
  if (table.getRowCount() > 0) {
    const body = table.getRangeBetweenHeaderAndTotal();
    const values = body.getValues();
    const formulas = body.getFormulas();
    const link = /HYPERLINK\(\s*FileBase\s*&\s*"([^"]+)"/i;
    for (let r = 0; r < values.length; r++) {
      const code = cellText(values[r][cols[0]]).toUpperCase();
      if (code === "") {
        continue;
      }
      const found = String(formulas[r][rubricCol]).match(link);
      rows.push([
        code,
        cellText(values[r][cols[1]]).toUpperCase(),
        cellText(values[r][cols[2]]),
        cellText(values[r][cols[3]]),
        cellText(values[r][cols[4]]),
        found ? found[1] : ""
      ]);
    }
  }

  const feed: RegisterFeed = {
    schema: PAYLOAD_SCHEMA,
    source: workbook.getName(),
    file_base: fileBase,
    columns: PAYLOAD_COLUMNS,
    rows: rows,
    row_count: rows.length
  };
  const size = utf8Bytes(JSON.stringify(JSON.stringify(feed)));
  console.log(`${rows.length} register rows, ${size} bytes`);
  if (size > MAX_BYTES) {
    throw new Error(`The feed is ${size} bytes and GitHub takes less than 64 KB in one event. The flow needs splitting into more than one event before more rows are added.`);
  }
  return feed;
}

function utf8Bytes(s: string): number {
  return encodeURIComponent(s).replace(/%[0-9A-F]{2}/g, "x").length;
}

function cellText(value: string | number | boolean): string {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim();
}
