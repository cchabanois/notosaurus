# pdf.js

[pdf.js](https://github.com/mozilla/pdf.js) 6.4.299 (Apache-2.0, see LICENSE), from the npm
package `pdfjs-dist@6.4.299`: its **legacy** build (`legacy/build/pdf.min.mjs`,
`legacy/build/pdf.worker.min.mjs`), its integrity checked against the registry's. The modern
build needs a recent browser (`Promise.try`, Chrome 128; `Uint8Array.prototype.toHex`, Chrome
140): with an older Android WebView (124 on the emulator) a PDF stayed on "Reading…" forever. Shipped with the page rather than loaded from a CDN: a blocked
CDN (an ad blocker, a privacy setting) made PDFs "unreadable", and it works offline.

To update: take both files of a newer `pdfjs-dist`'s `legacy/build/` the same way, and change the version here
and in `static/app-photos.js` (PDFJS).
