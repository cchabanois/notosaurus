# Third-party files, shipped with the pages

The pages load nothing from elsewhere: a blocked CDN (an ad blocker, a privacy setting) broke
them, they work offline (the Anki add-on, the Android app), and no third party sees the pupils'
visits. Each comes from its npm package, its integrity checked against the registry's, with its
licence next to it.

| Folder | What | npm package | Licence |
|---|---|---|---|
| `alpinejs/` | the pages' framework (`cdn.min.js`) | `alpinejs@3.14.9`, `dist/cdn.min.js` | MIT |
| `mathjax/` | formulas drawn on the cards' previews, as Anki draws them: the full bundle Anki and AnkiDroid ship (`tex-chtml-full.js`, the same file), its fonts (`output/chtml/fonts/woff-v2/`) | `mathjax@3.2.2`, `es5/` | Apache-2.0 |
| `pdfjs/` | PDFs read in the page (see its README) | `pdfjs-dist@6.4.299`, `build/` | Apache-2.0 |
| `material/` | the 🎤 of dictation, as Android apps draw it (`mic.svg`, `mic-fill.svg` while listening) | `@material-symbols/svg-400@0.48.3`, `outlined/` | Apache-2.0 |

To update one: take the same files from a newer version of its package the same way, check its
integrity, and change the version here (and where the pages say it, for pdf.js:
`static/app-photos.js`). `tests/test_vendor.py` checks that no page loads anything from
elsewhere.
