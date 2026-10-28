// The libraries' licences page (licences.html): the page's own (static/vendor, see its README),
// then the Android app's when it is that app (web/licences-android.json, written at its build)
const PAGE_LIBRARIES = [
  { name: "Alpine.js", version: "3.14.9", licence: "MIT", file: "vendor/alpinejs/LICENSE" },
  { name: "KaTeX", version: "0.19.0", licence: "MIT", file: "vendor/katex/LICENSE" },
  { name: "PDF.js", version: "6.4.299", licence: "Apache-2.0", file: "vendor/pdfjs/LICENSE" },
];

// The figures' (core figures_typst.py): Typst and its packages, shipped with Notosaurus
const FIGURE_LIBRARIES = [
  { name: "Typst", version: "0.15.0", licence: "Apache-2.0", url: "https://github.com/typst/typst" },
  { name: "alchemist", version: "0.2.0", licence: "MIT", url: "https://typst.app/universe/package/alchemist" },
  { name: "cetz", version: "0.3.4", licence: "LGPL-3.0-or-later", url: "https://typst.app/universe/package/cetz" },
  { name: "cetz", version: "0.5.2", licence: "LGPL-3.0-or-later", url: "https://typst.app/universe/package/cetz" },
  { name: "cetz-venn", version: "0.2.0", licence: "Apache-2.0", url: "https://typst.app/universe/package/cetz-venn" },
  { name: "ctz-euclide", version: "0.3.0", licence: "MIT", url: "https://typst.app/universe/package/ctz-euclide" },
  { name: "elembic", version: "1.1.1", licence: "MIT OR Apache-2.0", url: "https://typst.app/universe/package/elembic" },
  { name: "fletcher", version: "0.5.8", licence: "MIT", url: "https://typst.app/universe/package/fletcher" },
  { name: "komet", version: "0.1.0", licence: "MIT", url: "https://typst.app/universe/package/komet" },
  { name: "komet", version: "0.2.0", licence: "MIT", url: "https://typst.app/universe/package/komet" },
  { name: "lilaq", version: "0.6.0", licence: "MIT", url: "https://typst.app/universe/package/lilaq" },
  { name: "oxifmt", version: "0.2.1", licence: "MIT-0", url: "https://typst.app/universe/package/oxifmt" },
  { name: "oxifmt", version: "1.0.0", licence: "MIT OR Apache-2.0", url: "https://typst.app/universe/package/oxifmt" },
  { name: "suiji", version: "0.5.1", licence: "MIT", url: "https://typst.app/universe/package/suiji" },
  { name: "tiptoe", version: "0.4.0", licence: "MIT", url: "https://typst.app/universe/package/tiptoe" },
  { name: "zap", version: "0.6.0", licence: "MIT", url: "https://typst.app/universe/package/zap" },
  { name: "zero", version: "0.6.1", licence: "MIT", url: "https://typst.app/universe/package/zero" },
];

function libraryItem(name, detail, licences) {
  const li = document.createElement("li");
  const title = document.createElement("strong");
  title.textContent = name;
  li.append(title, ` ${detail} · `);
  licences.forEach(({ label, href }, i) => {
    if (i) li.append(", ");
    const a = document.createElement("a");
    a.textContent = label;
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener";
    li.append(a);
  });
  return li;
}

async function showLicences() {
  await i18nReady;
  for (const el of document.querySelectorAll("[data-t]")) el.textContent = t(el.dataset.t);
  document.documentElement.classList.add("i18n-ready");
  const page = document.getElementById("page-libraries");
  for (const lib of PAGE_LIBRARIES) page.append(libraryItem(lib.name, lib.version, [{ label: lib.licence, href: lib.file }]));
  const figures = document.getElementById("figure-libraries");
  for (const lib of FIGURE_LIBRARIES) figures.append(libraryItem(lib.name, lib.version, [{ label: lib.licence, href: lib.url }]));
  let android = [];
  try {
    const res = await fetch("licences-android.json");
    if (res.ok) android = await res.json();
  } catch {}  // the computer's page: none
  if (!android.length) return;
  const list = document.getElementById("android-libraries");
  for (const a of android) {
    const licences = [...(a.spdxLicenses ?? []).map((l) => ({ label: l.identifier, href: l.url })),
                      ...(a.unknownLicenses ?? []).map((l) => ({ label: l.name, href: l.url }))];
    list.append(libraryItem(a.name || a.artifactId, `(${a.groupId}:${a.artifactId} ${a.version})`, licences));
  }
  document.getElementById("android").hidden = false;
}

document.addEventListener("DOMContentLoaded", showLicences);
