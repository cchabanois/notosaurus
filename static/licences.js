// The libraries' licences page (licences.html): the page's own (static/vendor, see its README),
// then the Android app's when it is that app (web/licences-android.json, written at its build)
const PAGE_LIBRARIES = [
  { name: "Alpine.js", version: "3.14.9", licence: "MIT", file: "vendor/alpinejs/LICENSE" },
  { name: "KaTeX", version: "0.19.0", licence: "MIT", file: "vendor/katex/LICENSE" },
  { name: "PDF.js", version: "6.4.299", licence: "Apache-2.0", file: "vendor/pdfjs/LICENSE" },
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
