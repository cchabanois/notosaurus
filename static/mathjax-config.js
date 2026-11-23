// MathJax set up as Anki and AnkiDroid set it up (Anki's ts/mathjax/index.ts: the same
// full bundle, the same extensions in and out): the preview draws a formula exactly as the
// card will show it, an unknown command in red as there. Read before vendor/mathjax loads.
// One difference: the `html` extension is out (\href, \style, \class, \cssId, \data). A card's
// text comes from the AI, an imported or a shared lesson: in this page, which holds the
// keys and the lessons, those commands would add links and styles of its choosing. The
// preview writes them in red, as unknown.
window.MathJax = {
  tex: {
    packages: { "[+]": ["noerrors", "mathtools", "mhchem"], "[-]": ["textmacros", "html"] },
  },
  loader: { load: ["[tex]/noerrors", "[tex]/mathtools", "[tex]/mhchem"] },  // in the bundle: nothing fetched
  chtml: { fontURL: "vendor/mathjax/output/chtml/fonts/woff-v2" },
  options: { enableMenu: false },  // the right-click menu would fetch more of MathJax
  startup: { typeset: false },  // nothing in the page: the previews ask for their formulas
};
