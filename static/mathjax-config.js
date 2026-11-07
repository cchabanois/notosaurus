// MathJax set up as Anki and AnkiDroid set it up (Anki's ts/mathjax/index.ts: the same
// full bundle, the same extensions in and out): the preview draws a formula exactly as the
// card will show it, an unknown command in red as there. Read before vendor/mathjax loads.
window.MathJax = {
  tex: {
    packages: { "[+]": ["noerrors", "mathtools", "mhchem"], "[-]": ["textmacros"] },
  },
  loader: { load: ["[tex]/noerrors", "[tex]/mathtools", "[tex]/mhchem"] },  // in the bundle: nothing fetched
  chtml: { fontURL: "vendor/mathjax/output/chtml/fonts/woff-v2" },
  options: { enableMenu: false },  // the right-click menu would fetch more of MathJax
  startup: { typeset: false },  // nothing in the page: the previews ask for their formulas
};
