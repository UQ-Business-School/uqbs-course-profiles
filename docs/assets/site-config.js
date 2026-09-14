/* Site edition config — the ONE file the dual-build swaps per edition.
 * Loaded before app.js on every page. See scraper/build_editions.py.
 *
 *   edition : "uqbs" -> UQBS view, AoL/GA layers ON
 *             "all"  -> All-UQ public view, AoL/GA layers OFF
 *   dataBase: ""     -> profile JSONs + big manifests served same-origin
 *             "https://host/base/" -> fetched cross-origin from that base, so a
 *               light edition (UQBS on teach.business) needn't carry the bulk data.
 *   uqbsUrl/allUrl : where the landing page's two buttons point. The build sets
 *               these to the live edition URLs; the dev defaults below are
 *               relative so the splash works when serving docs/ locally.
 *
 * This source copy is the self-contained UQBS default used for local dev and
 * tests. The build overwrites it in each published tree.
 */
window.SITE = {
  edition: "uqbs",
  dataBase: "",
  repoUrl: "https://github.com/UQ-Business-School/uqbs-course-profiles",
  uqbsUrl: "business.html",
  allUrl: "browse-all.html",
  reportEmail: "learningdesign@business.uq.edu.au",
};
