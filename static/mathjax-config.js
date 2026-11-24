// MathJax set up as Anki and AnkiDroid set it up (Anki's ts/mathjax/index.ts: the same
// full bundle, the same extensions in and out): the preview draws a formula exactly as the
// card will show it, an unknown command in red as there. Read before vendor/mathjax loads.
// One difference: the `html` extension is out (\href, \style, \class, \cssId, \data), and
// \require can't load it again. A card's text comes from the AI, an imported or a shared
// lesson: in this page, which holds the keys and the lessons, those commands would add links
// and styles of its choosing. The preview writes them in red, as unknown.
// Other commands write CSS of their own, which MathJax copies into the page as written
// (\bbox's, \fcolorbox's frame, \mmlToken's attributes, \unicode's font): of it, a formula
// keeps a border and a padding (a box's colour is MathJax's own), as Anki gets them
// (app/note_types/formulas.py); no link, class or id of its own.

(() => {
  // A declaration a formula's CSS keeps: a border or a padding, of plain values (no url(), no var())
  const KEPT_CSS = /^\s*(?:border(?:-width|-style|-color)?|padding)\s*:\s*[a-z0-9#. %-]+$/i;
  const PLAIN_FONT = /^[\w\s,'"-]*$/;

  function harmless({ data }) {
    data.root.walkTree((node) => {
      const attributes = node.attributes?.getAllAttributes();
      if (!attributes) return;
      for (const name of ["href", "class", "id", "fontsize"]) delete attributes[name];
      if (attributes.style !== undefined) {
        const kept = String(attributes.style).split(";").filter((d) => KEPT_CSS.test(d)).join(";");
        if (kept) attributes.style = kept;
        else delete attributes.style;
      }
      if (attributes.fontfamily !== undefined && !PLAIN_FONT.test(attributes.fontfamily)) delete attributes.fontfamily;
    });
  }

  window.MathJax = {
    tex: {
      packages: { "[+]": ["noerrors", "mathtools", "mhchem"], "[-]": ["textmacros", "html"] },
      require: { allow: { html: false } },
    },
    loader: { load: ["[tex]/noerrors", "[tex]/mathtools", "[tex]/mhchem"] },  // in the bundle: nothing fetched
    chtml: { fontURL: "vendor/mathjax/output/chtml/fonts/woff-v2" },
    options: { enableMenu: false },  // the right-click menu would fetch more of MathJax
    startup: {
      typeset: false,  // nothing in the page: the previews ask for their formulas
      ready() {
        MathJax.startup.defaultReady();
        MathJax.startup.input[0].postFilters.add(harmless);
      },
    },
  };
})();
