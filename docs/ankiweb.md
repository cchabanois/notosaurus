# AnkiWeb add-on page

The description of the add-on on AnkiWeb (https://ankiweb.net/shared/addons → the add-on →
edit), kept here so it is reviewed like the rest and updated with each release. AnkiWeb doesn't
render Markdown: paste the HTML below. Images must be hosted elsewhere: the GIF is served from
this repository.

**Title**: `Notosaurus — snap a lesson, get Anki cards (AI)`

**Support page**: `https://github.com/cchabanois/notosaurus/issues`

**Tags** (80 characters at most): `ai photo pdf flashcards vocabulary language school kids gemini gpt claude cloze`

**Supported Anki versions** (one branch): min `25.02` (the oldest the CI tests), max the latest tested,
without a `-` (a `-` would block newer Ankis from downloading it).

**Description**: copy only the lines *between* ```` ```html ```` and ```` ``` ````.

---

```html
<p><b>Snap a lesson with your phone, get Anki flashcards in seconds.</b> Notosaurus reads a
notebook or textbook page with AI (handwriting included) and makes the cards: you review them,
then send them to Anki in one tap.</p>

<p><a href="https://www.youtube.com/shorts/Q7bUTMEj6Kk"><img
src="https://raw.githubusercontent.com/cchabanois/notosaurus/main/docs/src/assets/demo.gif"
alt="Notosaurus demo" width="280"></a><br>
▶ <a href="https://www.youtube.com/shorts/Q7bUTMEj6Kk">Watch the 75-second demo</a> ·
📖 <a href="https://cchabanois.github.io/notosaurus/">Documentation</a></p>

<ul>
<li>📸 <b>From a photo or a PDF</b>: vocabulary, questions, fill in the blanks, multiple choice,
true or false, formulas.</li>
<li>🌱 <b>Diagrams</b>: labels hidden automatically, one card per label.</li>
<li>📐 <b>Exact figures</b> for geometry, formulas in MathJax.</li>
<li>🖼️ <b>Pictures on the cards</b> (“front: the picture of the word”), and spelling
dictations: hear the word, type it.</li>
<li>💡 <b>Helps on the back</b> where they help: why the answer is right, a genuine way to
remember it. And 💬 ask for an explanation of any card while reviewing.</li>
<li>✏️ <b>Fix the cards in plain words</b>: “add the plural on the back”, “you forgot the
colours”.</li>
<li>🔊 <b>Natural audio</b> in the deck, plays everywhere, even offline.</li>
<li>👨‍👩‍👧 <b>Made for families</b>: one Anki profile per child, each with their own lessons.</li>
<li>📥 <b>Straight into Anki</b>, updated without duplicates; review on AnkiDroid or
AnkiMobile.</li>
</ul>

<p><b>Getting started</b></p>
<ol>
<li>Install the add-on and restart Anki. On first start, Notosaurus asks before downloading its
components (about 300 MB, once).</li>
<li>The setup assistant opens in your browser (later: <i>Tools → Notosaurus → Getting
started</i>): choose an AI service and paste its key. Recommended: Gemini, about 1 US¢ per
lesson; Claude and GPT read notebooks well too, for a few cents. The recommended models come
from our tests on real notebook pages.</li>
<li>Scan the QR code with the phone, on the same Wi-Fi, and take a photo of a lesson.</li>
</ol>
<p><a href="https://cchabanois.github.io/notosaurus/getting-started/">Full guide</a> ·
<a href="https://cchabanois.github.io/notosaurus/fr/">Documentation en français</a></p>

<p><b>Good to know</b></p>
<ul>
<li>Notosaurus runs a small web server on your computer, reachable on your local network by the
devices that scanned its QR code. Never expose it to the Internet.</li>
<li>The photos are sent to the AI service you choose, and to no one else. The card backs go to
Microsoft's text-to-speech for the audio. No statistics, no tracking.
<a href="https://cchabanois.github.io/notosaurus/privacy/">Privacy</a></li>
<li>A free AI key works for trying (an older model, low limits), but its service may use what
you send to improve its products: for your children's notebooks, turn on its billing.</li>
<li>Free and open source (AGPL-3.0):
<a href="https://github.com/cchabanois/notosaurus">github.com/cchabanois/notosaurus</a>.</li>
<li>Like it? ☕ <a href="https://ko-fi.com/notosaurus">Support Notosaurus on Ko-fi</a>.</li>
</ul>

<p><b>En français</b> : prends une leçon en photo, Notosaurus en fait des cartes Anki.
<a href="https://cchabanois.github.io/notosaurus/fr/getting-started/">Guide de démarrage</a>.</p>
```

---

## Before each release

- Check that the description still matches what Notosaurus does (new card types, settings…).
- If something new deserves it, add a short **What's new in X.Y.Z** paragraph at the top, linking
  to the GitHub release.
