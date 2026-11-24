# Changelog

All notable changes to Notosaurus. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/).

Each pull request's entries (the `## Changelog` of its description) are put under **Unreleased** once it is merged, by the *Changelog* workflow: see [Pull requests](CONTRIBUTING.md#pull-requests), and [Releasing](CONTRIBUTING.md#releasing) for how a version is published.

## [Unreleased]

### Added

- 🔊 A lesson's voice can be chosen once it is made (« Voix », under the deck): a lesson made without one gets it.
- 📄 **The page a card comes from**: the open card shows "📄 p. 3"; a touch shows the lesson's page in full (‹ › to the others), in a lesson read only too.
- 🗂 An open card shows its Anki deck at its top, small, as Anki does: « Jules › 5e › Anglais › … › Exercices ».
- 🔊 Every card can be read aloud on its question, its answer, or both: a sentence with gaps with its blank, then whole; the card's ⋯ turns each side on or off.
- 🖼️ A sentence with gaps can have a picture, on its question or its answer.
- ✓ « Garder » keeps an AI correction, beside « Annuler » and « Refaire avec soin », for a card and for the whole lesson.
- ＋ in a card open adds one just after it; after the last card, the lesson's end, to add a card or send the lesson to Anki.
- Maps: places, lines (a wall, a road, a railway, a front) and areas the atlas lacks, given by their coordinates, and symbols on places (ports, industries, silos, dams) with their legend.
- Figures: icons of a lab's glassware (beaker, volumetric flask, burette, pipette) and of living things (animals, plants, fungi, organs), of a cell's parts (chromosome, bacterium, chloroplast, neuron…) and of history's weapons and ships.
- Figures: pictograms on a timeline's events and in a scheme's boxes (a factory, a port, a battle, wheat, a microscope, a laptop…), from the free Maki, Temaki and Phosphor icons and a few of our own for history; a word with no icon simply draws none.
- Figures: a planet's or the Sun's internal structure drawn as a cut quarter, its layers, depths and names placed by the app.
- ✏️ Correcting a card with a figure, the AI now sees the drawing: "the bar is at the wrong height", "the triangle should be outside the square" and the figure is drawn again, right.
- ⚛️ The periodic table drawn with its elements' symbols and atomic numbers, families coloured with a legend, an element a card asks for written « ? ».
- Maps: every country's overseas lands and far archipelagos, the small territories (Gibraltar, Monaco…), the world's regions (East Asia, Latin America, the Maghreb…), and the camps of the Shoah; a country's far lands drawn in insets.
- 🔭 The afocal astronomical telescope drawn with its ray path computed: the beam converging in the focal plane, then leaving the eyepiece parallel at α'.
- Figures: climate charts (diagrammes ombrothermiques), the precipitation as bars and the temperature as a curve, their scales tied.
- 🧩 A figure that shows two things of different kinds (a circuit and the curve of its voltage, a titration's set-up and its curve) is drawn in panels, each by its own family.
- Google's document scanner (📷) and the photo crop can each be turned off from the relay (`lesson.scan`, `lesson.crop`) without an app update: the 📷 then takes one photo with the phone's camera; the photo editor then blacks out only, a crop already made being kept.
- Figures: a bar chart's mean or expectation marked and an interval of its values shaded; on a number line, an interval's centre and its distance to each bound.
- Figures: rectangles under or over a curve (the rectangle method), the real line wound round the trigonometric circle.
- 📊 Histograms drawn by their classes (adjacent rectangles, unequal classes by their areas) and scatter plots with their fitted line.
- Figures: the Earth with a point by its latitude and longitude, a point's coordinates written in a frame of space, tilings of the plane by squares, triangles or hexagons.
- Geometry figures: a protractor laid on an angle, a triangle built with ruler and compass with its arcs, a lottery wheel with its colours and pointer, a cuboid made of unit cubes.
- 📄 **The app scans the lesson's pages** (Android): 📷 opens Google's document scanner: several pages in one go, each found, straightened and cropped to its edges, shadows lightened, as many as the lesson has room for. No camera permission; on a phone without Google Play services, or until the scanner is downloaded, the phone's camera as before.
- 🧭 Maps centred on a pole: the Arctic with its countries and its sea routes (the Northern Sea Route, the North-West Passage), and Antarctica, as seen from above the pole.
- 🗺️ History maps for every year from 1815 to 1991, the Second World War's included: Europe under Germany in 1942, Japan's empire, Germany's occupation zones, Africa before and after its partition, Algeria French until 1962.
- 🗺️ Maps of history drawn with the borders of the time: the Congress of Vienna's Europe, the German Empire, 1914's alliances and colonial empires, the interwar years, the Anschluss, Germany's occupation zones, the Cold War's blocs.
- Charts: population pyramids, two series of bars back to back by age class, graduated alike on both sides; a pyramid described only by its shape drawn as that shape, without numbers.
- Maps draw routes (voyages, sea and trade routes, by sea around the land or over land) and flows (migrations, trade, tourists) as arrows between named places, with a legend: no longer drawn by hand. A flow between regions tints and names them; arrows are wide as their importance.
- Maps colour countries or regions by group (alliances, empires, blocs, a union's members), with a legend: no longer drawn by hand.
- Field lines of a magnet or of point charges are now computed, running from north to south and from + to −, with an arrow showing the field's direction on each line.
- 🌗 Shadows and eclipses (a source, a lit body, its shadow cone, the shadow cast on a screen or on the Earth, the Moon in the Earth's shadow, a body's own shadow) drawn with rays tangent to the bodies, the shadow behind the body and every body named.
- Chemistry figures: a molecule's partial charges, a bond angle, its dipole moment and a bond's polarisation, placed by computation on the molecule (each charge beside its atom, the angle inside, the dipole moment from the charges, beside the molecule).
- 🔦 Refraction, reflection and a lens's image drawn with their rays computed: the refracted angle by Snell-Descartes, the image and its three rays.
- 🛹 Skate ramps, roller coasters and marble tracks drawn exactly: the track's shape computed, the body at its point, each label clear of the track.
- 🧂 Crystals on a cubic lattice (an ionic crystal's alternating ions, a metal's simple, body-centred or face-centred cell) drawn regular in perspective, each ball in its place and in front of those behind it, with their legend and the cell's edge.
- 📤 On the phone without a computer: a lesson's cards, several lessons' or a test's, shared as a file through Android's share menu (a message, a mail, a drive), to open with Anki or AnkiDroid.
- 📤 Share the cards of several lessons, or of a test, with another family in one file to open with Anki or AnkiDroid: from 📚 My lessons (lessons ticked), a test's sheet, or the open lesson. Without the child's name nor its review history.
- Figures: logarithmic scales (distances in the Universe, sizes from the atom to the galaxy, sound frequencies) drawn with each object at its place and powers of ten as graduations; named zones on a scale (infrasons, audible sounds, ultrasons), each its colour.
- 📤 On Android, share photos, a PDF or a text from any app to Notosaurus: they become the pages of a lesson, ready to make its cards (a web page's address alone is not taken: share a screenshot or the page as a PDF).
- ✋ "Cancel" while the AI corrects the lesson or a card: it stops, the cards stay as they were.
- Pictures seen in full can be zoomed with two fingers and moved with one; a tap zooms in where it touches.
- 📦 Box plots drawn by the statistics chart: boxes on one shared axis at a readable size, their graduation computed.
- 🧩 Scratch scripts drawn block by block as Scratch draws them (blockst), their words never cut.
- 📊 Tables of values (two-way tables with totals, proportionality tables with their arrows, conversion and frequency tables): each column as wide as its content, totals computed.
- 〰️ Curves through measures (a reaction's progress, a growth, a cooling) drawn smooth, through every measure and never beyond them.
- 🛰️ Forces and velocities drawn on a body (an orbit and its Frenet frame, a block on the ground or a slope, a pendulum), each arrow in the right direction and every name readable.
- 🧊 Figures: a coordinate frame of space, its points, lines, planes and vectors placed from their coordinates, what a plane or a solid hides dashed.
- 🧬 Aligned sequences (alleles, mutations, proteins compared): each letter in its column, the differences framed automatically.
- 🌳 Phylogenetic trees drawn from the species and the innovations they share, each innovation on its branch.
- 📈 Line charts compare several groups on one axis, with a legend (two populations, two people, two conditions).
- Additive and subtractive colour synthesis drawn exactly: each overlap's colour computed; the colour a card asks for left as a question mark.
- Charts mark an event or a period on a curve, and draw a second measure with its own unit on a right axis.
- Solids cut by a plane (a cuboid, a prism, a pyramid, a cylinder, a cone, a ball): the section drawn where it is, its hidden sides dashed.
- Maps for history lessons: their places (Constantinople, Aix-la-Chapelle, Cordoue, Troie, Verdun…) and cities' former names (Leningrad, Saïgon, Pékin), in every language of the page.
- Curves of measures (a heart rate over time): drawn from the lesson's measures, their axes starting where the measures are.
- Statistics charts (bars, pie, half pie): drawn from the lesson's counts, their angles computed.
- Cylinders, cones, spheres and half-balls drawn in proportion to their lengths, their hidden parts dashed; several solids side by side at one scale to compare them.
- Coordinates of points in a frame (5e): a gridded frame, a tick at each unit.
- Geography maps show regions, rivers, mountains and seas too.
- Solids in perspective (a cube, a cuboid, a prism, a pyramid): drawn exactly, their hidden edges dashed where they should be, their vertices and lengths named.
- Reading the time, and saying it in a language ("It's a quarter to nine", "Es ist halb elf"): a card asks "What time is it?" with a real clock, its hands exactly at the time.
- Geography cards show a real map: the country, its neighbours, its cities.

### Changed

- The lesson's own drawings are looked for on the card's page and the pages next to it, not on every page of the lesson: cheaper, and found more reliably.
- ✨ **Correct this card** sends the AI only the lesson's page the card comes from, not every page: much cheaper on long lessons (cards made from now on; older cards as before).
- Corrections cost a little less: the AI is no longer sent where each card's picture comes from.
- 🗂 A card's sub-deck is chosen in a list: none, one of the lesson's (with its number of cards), or a new one.
- ⏳ A button that waits for the AI pulses until the answer comes: 🔊 while its voice is made, 💬 while the explanation is thought (shown where it will come), the search for a picture, « Mettre au propre ».
- 📄 A PDF of several pages shows its pages before adding them, all ticked when they fit: tap the ones you don't want.
- 🔊 A sentence with gaps is read whole on its question, as a dictation: you hear the missing words and write them.
- 🗂 New Anki note types (v3) for text, multiple choice and gaps; the computer moves your notes there, their review history kept.
- 🔊 A card's sound sits beside its answer, which it reads.
- While dictating, « Corriger », « Écrire » or « Générer » can be tapped directly: the dictation stops and what was said is sent, no need to tap ■ first.
- The figure's check says what it does: « 🔍 Vérifier la figure » under the figure, not a lone 🔍 that read as a zoom.
- 📚 « Mes leçons » leaves the lessons the room: the sheet rises to the top, the tests to prepare fold in one line, the search and sharing share one line.
- 🏷️ A diagram's card shows only what Anki will show of the photo; touched, it opens full screen to move its masks and frame.
- ✨ In a card open, « Corriger » sits beside its field, on a light bar at the bottom of the screen.
- 🖼️ A card open has its actions at its top right; in the list, only 🔊 is shown, a picture is above the question or after the answer, as in Anki, and a diagram shows only what Anki will show of the photo.
- 📋 The cards' list is compact (front, back, a small picture): a card touched opens full screen; « ▶ Relire carte par carte » goes through them from the first.
- 📝 A card is edited full screen (a window on a computer): ✕ closes it, ‹ › or a swipe go to the previous or next card, and « ✨ Corriger avec l'IA » is always at the bottom.
- ✏️ Cards show as they will in Anki, formulas and figures drawn. Touch a text to edit it (its LaTeX shown there only), one card at a time; ✓ Done closes it.
- ✨ "Correct this card" on a phone no longer opens the keyboard: dictate with 🎙️, or touch the field to type.
- 🔒 Figures are compiled without access to the server's secrets.
- 📐 A figure drawn again after a correction starts from the one it replaces: what you ask changes, the rest stays as it was.
- Maps of the world or a continent drawn about twice as fast, their coastlines simplified to their scale.
- 🎙️ While dictating, the microphone button shows a stop (■): tap it to stop and write the text.
- ⚡ Corrections (of a lesson or a card) follow the Quick / Careful choice: quick, about a third faster for a lesson, as right in our measures; « 🎯 Refaire avec soin » asks again carefully.
- ✨ « Corriger cette carte » is now a button on every card, no longer hidden in its ⋯ menu.
- On a phone, the bar at the bottom of the cards is lower and hides less of them: « Partager » and « Réviser » are icon buttons, the main button's text stays on one line.
- Figures whose text would be too small to read on a phone are drawn again more compactly, in every kind of figure, not only diagrams.
- 🖼️ The photo viewer's crop button shows the usual crop icon (two crossing right angles) instead of scissors, as does the editor's « Recadrer » mode; a page cropped or blacked out is now marked by a small dot on its button instead of a filled background, and told to screen readers.
- ✂️ Cropping a photo has its own button in the full-screen photo, next to 🖍️ for blacking out a name: each opens the editor ("Prepare the photo") ready for its job.
- Maps: when a river, relief or sea is not in the atlas, the error names the closest ones it has, so the AI can correct the name instead of dropping it.
- 🗺️ The past borders come from OpenHistoricalMap: finer, dated to the day, every colony with its ruler.
- 🗂️ Classifications drawn as groups inside groups are narrower and easier to read on a card: groups side by side wrap onto several rows, each group's name is centred above a thin line, and its own members sit under its sub-groups.
- « Toutes les pages »: no more ✕ on each page. « Sélectionner » (or a long press on a page) chooses pages, then « Retirer » removes them together; a tap still shows a page in full.
- A lesson holds 30 pages (10 before): a PDF of a chapter or a long course at one click, its pages read 10 at a time, the page saying which ones it reads.
- 🎙️ Dictation shows your words as you speak: the phone's own speech recognition writes them, at once and with no credits used; your voice no longer goes through the Notosaurus service.
- 🎙️ The dictation button shows the microphone Android apps use, filled on a pulsing circle while it listens.
- 📸 Photos: a lesson with more pages than fit beside the add buttons shows a "+N" in the last place; it opens all the pages in a sheet. A page's thumbnail now shows only its number and ✕, plus a 🖍️ mark when part of it is hidden. A tap on a page opens it full screen, where it is turned (↻), partly hidden (🖍️) or removed (🗑️).
- 📜 The figures' credits on the licences page come from the Notosaurus service: a drawing tool added is credited without updating the app.
- The AI (Gemini) may now process the lessons' photos outside the European Union, on Google's servers; the privacy policy says so.
- Figures drawn with Typst 0.15.1 (bug fixes; no figure changes).
- Algorithm flowcharts are drawn with their usual shapes: rounded start and end, a diamond for each test.
- Figures drawn in Typst use the same plain font as the other figures, and timelines' text is larger.
- The automatic instruction makes cards that read a lesson's charts and curves (its tables of counts or of measures), the chart or the curve redrawn on the front.
- The Android app is about a third smaller.

### Fixed

- 🐛 Cards to be read aloud in a lesson without a voice: said, instead of a correction saying the audio is on.
- 🐛 The app: a Chinese lesson gets a voice (Mandarin, or Cantonese for Hong Kong); it had none, nothing read aloud.
- A card corrected while its picture was being drawn keeps its correction: the drawing of what it said before is set aside
- Android: something shared to Notosaurus is no longer added a second time when the app is reopened from the recent apps, or after a change of theme, language or text size.
- Android: sharing more files than a lesson's pages now says how many were not added, and a file too large or damaged is said as such, not as a type Notosaurus doesn't take.
- "📐 Dessiner la figure" on a figure a correction changed, while it hasn't been drawn again (its automatic drawing failed or is still to come), now starts from the old drawing and changes only what the correction asks (computer and Android).
- A figure corrected while the lesson's other pictures are being drawn is now drawn again from its corrected description and keeps it, instead of going back to the old one.
- Changes made to a lesson while its pictures are being drawn are now saved at once, instead of waiting for the drawing to end (they were lost if the app was closed meanwhile).
- A lesson missing one of its pages (its photo deleted) no longer sends the AI the wrong page when correcting a card or the lesson, or when looking for the lesson's own drawings: each page is used by its own number, and a card from the missing page is handled as one whose page is unknown.
- Adding pages to a lesson missing one of its photos no longer overwrites an existing page or reuses a number its cards still point to.
- On Android, choosing your own photo for a card refuses a file that isn't a JPEG, PNG, WebP or GIF image, as on the computer.
- Finding a picture for a very long card (over 4000 characters) no longer fails.
- A formula's web commands (links, styles) no longer reach Anki: a colour kept as \color.
- A picture drawn with the lesson's others and meant for the answer side no longer moves to the question when the lesson is next saved.
- 🗂️ **Each lesson its own deck on Android too**: a deck that already exists in AnkiDroid or belongs to another lesson gets " (2)", as on the computer.
- 🏷️ **A lesson shared as a package from the Android app keeps its tests' tags**, as when it is sent to AnkiDroid.
- 👧 **Children's names and decks in any script**: a child whose name or class is in Cyrillic, Greek or Japanese no longer hides every other non-Latin deck from the AI. "ß" and "ss" are the same level on the phone and on the page.
- 🔊 On Android, a lesson in the pupil's own language is no longer taken for a foreign one when the AI writes its language in capitals or with spaces.
- 📦 On the computer, a shared package with a blank name is named after its test, as on Android.
- Sending to Anki or drawing pictures, cancelled meanwhile: no error said any more, the cards as they were.
- "🔍 Check the picture" works on long cards; it no longer fails for cards longer than about 1000 characters.
- Asking the AI to change a figure into a photo no longer leaves the card half-changed when no photo is chosen: the card keeps its figure until a picture actually replaces it. A card already left that way can be checked again.
- Gemini unreachable: said as such ("Can't reach the Gemini API"), and the relay tries its other routes and fallback models instead of stopping on a generic error.
- Something shared to the app while Notosaurus is busy (a lesson being made or corrected, a card open) is no longer lost or added in the wrong place: it is added once the current task is done or the card closed.
- Starting a new lesson from elsewhere (an Anki profile switched, the open lesson deleted) no longer leaves the previous lesson's card open over it.
- The offer to draw pictures with the AI no longer follows you to another lesson.
- A correction cancelled just as it was being saved now shows the corrected cards it saved, instead of the old ones.
- The sub-deck tag's tooltip uses each language's punctuation.
- 🖼️ A figure on the question side of a sentence with gaps no longer risks showing a hidden word: it is drawn knowing only the question, its gaps hidden.
- 📐 Two wires of a circuit ending a hair apart are joined, instead of each moving onto the other and leaving the circuit open.
- 📐 A figure that stays too small after being drawn again is kept as a finished drawing (a map's outlines lightened), instead of being lost.
- 📊 A box plot whose values are all equal is drawn, instead of refused.
- 📐 An interval on a number line is drawn where the line puts its values, even when its first value isn't given again, and an infinite end stops at the line's end.
- 🌑 The shadow of a flat body (a bar seen edge on) ends where its rays meet, instead of crossing.
- 📏 A figure whose positions are written with a unit ("10px") is measured, instead of failing.
- On the phone, correcting a card of a lesson of more than 10 pages no longer fails ("too large"): its own page is sent, or, for a card made before, no page.
- 📐 A figure drawn again keeps its layout everywhere: after a correction, or with its description changed on its picture's page, only what is asked changes (computer and Android).
- 🐛 A PDF or photos added right as the page opens: counted against the lesson's 30 pages, not 10.
- 📐 On the phone, a figure drawn again keeps its layout: only what is asked changes
- A figure's Typst can no longer fetch a package from the internet nor read a file, however it is written: only the packages shipped with Notosaurus are found. A label or a comment may still say any word ("import / export", "the json format").
- Checking or correcting a very tall figure no longer takes a large amount of memory, nor holds up the server's other requests; a card's correction goes on without the figure when the figure can't be drawn.
- A card's formula can no longer add links or styles to Notosaurus's page. Commands such as `\href` or `\style` are shown in red, as unknown.
- Notosaurus's page now runs only its own scripts, on the computer and in the phone app.
- Another website open on the computer can no longer make Notosaurus act: make a lesson, import lessons, unpair the phones or test the AI.
- A picture's source page is shown as a link only when it is an `https:` address.
- Exporting or sending a lesson to Anki takes only that lesson's own pictures.
- A lesson of many pages, read in several calls, has its pictures drawn once, after the last call: the next pages' cards are no longer dropped from the saved lesson, and the first pages' pictures are no longer drawn (and paid for) twice.
- A picture drawn while the lesson is changed elsewhere (the next pages added, a card edited) keeps those changes.
- A figure whose name ends in digits only keeps its Typst source.
- A picture just drawn is no longer removed by a prune asked at the same moment (computer and Android).
- In the app, lessons moved from the computer can be edited and deleted: they were read only, for an Anki profile the phone doesn't have.
- 🎤 On Android, the phone's speech recognition stopping on an error no longer wipes what it had already written: the text stays in the field, the error is said.
- 📷 On Android, tapping 📷 again while the pages just scanned were still being added no longer makes them "unreadable"; the camera's photos are no longer kept on the phone when the document scanner is turned off.
- 📤 On Android, a second share arriving while the first one was being added no longer mixes their files.
- On Android, an `.apkg` that fails to be made no longer leaves the lesson's cards in the app's cache.
- A lesson read only (another Anki profile's) shows its cards' questions and answers again: they were empty.
- The packages for drawing figures no longer pile up on the computer: the ones of older versions (about 30 MB each) are removed.
- Building a package (one lesson, or several to share) or sending to Anki no longer stops the computer's page from answering meanwhile.
- 🖼️ After exporting, sharing or sending a lesson, ↩ Undo no longer brings back a card with a broken picture.
- 🖼️ Undoing the first card's correction no longer loses its old picture.
- 🖼️ Opening a lesson again (a reload, another tab) while its pictures are being drawn no longer deletes a picture just drawn.
- On a phone, a diagram's card in the list shows its question and answer under the photo, no longer squeezed beside it.
- A card corrected with the AI keeps its picture's source: a free picture's licence and page stay in its Anki note, and a figure redrawn after a correction is redrawn from its own drawing.
- A figure of a circuit, a clock, magnetic field lines, a phylogenetic tree or a Scratch script can show a pictogram, as every other figure can: it no longer fails to draw.
- A lesson of more than 10 pages: its cards get the lesson's own drawings again (before, none did past 10 pages).
- The 📷 opens the camera when Google Play services are too slow to start the document scanner (offline, its module still downloading), instead of doing nothing.
- 🐛 Swiping to the next card, its deck at its top shows during the swipe, not once it has arrived.
- 🖼️ Asking a correction for another picture no longer brings back the same drawing cut out of the lesson's photos.
- 🎨 "No free picture fits: have the AI draw it?" shows again after the pictures are looked for.
- 🐛 A card's sound that can't be heard says why: an ended subscription offers « Subscribe », instead of « unknown voice or speech unavailable ».
- On a slow computer, a card just added no longer takes the cursor away from the field you had already clicked in.
- 🐛 « Vérifier la figure » no longer shows on a card whose figure was replaced by a photo (it said « Cette carte n'existe plus »).
- 🐛 A lesson's correction counts the cards whose figure, wrong answers or helps it changed, no longer « aucun changement ».
- 🐛 The lesson's correction: « ✓ Garder » shows its text (it was an empty white button).
- 🖼️ On a picture's page, what it shows is seen whole, over several lines, no longer cut to one.
- 🗂 A card's note (+ info) is no longer squeezed by its sub-deck, and a card without a sub-deck says "+ sub-deck" instead of looking like one.
- 👆 A card open turns to the next with a swipe from anywhere on it, its correction's field or a diagram's photo too.
- 🖼️ A card's photo is shown large in the card open, no longer a small square.
- A button of the page could stay shown when it no longer applied (📤 with Anki out of reach): what the page shows now always follows its last state.
- A card's text touched on a busy phone could open its field without the cursor in it (no keyboard): the field is focused once shown.
- 🖼️ Undoing a card's correction that redrew its figure no longer leaves a broken picture.
- 🧮 What the AI says it changed on a card, and its explanations, show their formulas drawn, not their code.
- 🖼️ A figure being drawn again keeps its size on the phone too.
- 🎙️ Dictation on the phone (Android 13 and later) no longer loses what you say after a pause, and no longer beeps at each pause.
- 🖼️ A figure being drawn again keeps its size meanwhile: its old one no longer shrinks into a small square.
- 🖼️ A figure corrected stays shown (faded) while the new one is drawn, no longer an empty frame.
- Figures: a heavy map with symbols no longer fails for want of memory.
- ⏳ A correction's waiting time is said as measured (10 to 25 seconds usually), no longer "about a minute".
- Figures: a school word no longer draws an unrelated icon (a cell, a lens, a cone, a switch): its own, or none.
- Figures: icons drawn with their white halo, readable on a map's colours.
- Maps: the United Kingdom's nations (Scotland, Wales…) as regions, the world's parts by their usual names (West Africa, the Antilles), the British dominions in the empire, and more places of history (Ephesus, Dunhuang).
- Maps: small islands (La Réunion, Guadeloupe, Bermuda…) drawn with their real outline in a map's insets.
- Diagrams: an arrow that goes to no box is no longer drawn into the void; the figure is drawn again.
- 📊 A chart drawn in the colours its description, or a correction, asks for ("the bars in green"), no longer grey.
- A photo cropped just after it was added comes back cropped when the app opens again. Before, a slow save of the uncropped photo could land after the cropped one.
- Dictation started as the app opens, before the prompts have loaded: the dictated text stays in the free prompt, as typed text does. Before, it replaced the text of the first prompt, which stayed selected with its deck and voice.
- A formula written the LaTeX way on a figure (t_{1/2}, \text{…}) shown as meant, never refused nor written with its code.
- Molecules in Cram's representation drawn with their wedges (in front, behind), narrow at their atom.
- Maps: regions found by their names in every language (« Lombardie », « Puglia »); a name the atlas refuses says what to write instead.
- Maps: names no longer written on each other where places are close (a route's straits, overseas islands, cities on a world map); a strait or a canal a route passes is marked; a name moved off its place has a line to it.
- Labelled schemes: the labels' lines no longer cross the words of the arrows or run along the arrows, and a label's point no longer lands on an arrow's word.
- Figures: maps of real places (a country's rural areas, an event's sites) drawn on the atlas instead of invented shapes; a town's plan (Berlin's sectors) no longer drawn as a country map.
- 🏷️ A scheme's labels are set where their lines cross the drawing least: in a row over or under steps side by side, in one column, or on each side for a name whose parts lie on both sides (a flower's petals). They are no longer always in two columns with long lines across the drawing.
- 🏹 In a figure drawn as SVG, the words on arrows (what enters or leaves, a step) are set by the app beside their arrow, where nothing else is drawn, instead of across the drawing.
- 🏷️ The label of a region the drawing closes against its frame (a cell's nucleus, left of an envelope drawn from top to bottom) stays on that region instead of jumping to the nearest part.
- ⚡ A circuit's voltages (uC, U across a resistor, a generator's E) drawn as their arrows beside the components.
- 📈 A calibration curve's values readable on its axis; an infrared spectrum's wavenumbers from 4000 to 500; a fitted line's small slope no longer written 0.
- Graphs: a point's name no longer written on the lines that go through it.
- 🌐 Brazilian Portuguese: sharing cards and saving or transferring lessons are no longer worded in European Portuguese. Italian: cards are called « carte » everywhere.
- Bar charts with many bars (a probability law) no longer drawn tiny, their values no longer written on one another.
- Figures: points' and lines' names no longer fall on the axes or their numbers, a curve running along an axis no longer crosses its numbers, a relation is written under the figure, and a vector's name keeps its arrow.
- 📚 « Réviser » on a lesson with nothing to review today no longer comes straight back to Notosaurus: AnkiDroid opens on your decks, and Notosaurus says there is nothing to review today.
- Geometry figures: a length written before the lines crossing it no longer lies on them, an angle's name is always written with its hat, and a word naming a segment (diameter, radius) stays beside it.
- The photo editor's modes no longer run off the edge of a narrow phone.
- An angle's name is written with its hat (BAC with ^), never "(BAC)".
- Two things shared to the app in a row (Android): the second is no longer lost when it comes while the page is taking the first.
- Geometry figures: lengths, angle values and line names no longer fall on a side, a point or a line; a segment cut by a point (a diameter through its centre) has its length on a dimension line over its whole length.
- 📈 A line chart of small values (concentrations in thousandths) gets a graduation you can read values from, instead of a single band.
- 🔵 Names written under a Venn diagram no longer overlap.
- 🎯 A throw drawn as a chronophotography uses the launch angle the lesson gives.
- ⛰️ A slope's angle uses the lesson's name for it (θ, β…) instead of always α.
- 🌍 An orbit's radius starts at the centre of the central body, not at its surface.
- Symmetry figures: the image of a triangle by a central symmetry no longer has its construction lines on top of one another, and the axes of an equilateral triangle go through its centre.
- 🖍️ A name blacked out on a photo no longer shows again for an instant after **Terminé**: the photo is shown hidden at once.
- 🗺️ A map naming several places the atlas lacks lists them all at once, so the AI can correct them in one go. « Groenland » given among Denmark's regions is drawn as the country it is in the atlas.
- Maps: straits and canals ("canal de Suez", "détroit d'Ormuz", "pas de Calais", "détroit de Béring"…) are found among the waters in every language, and a strait or canal too small to see on a world map is marked by a ring with its name beside it.
- 🏛️ Schemes: each arrow drawn straight from box to box (one soft curve round a box in its way), its words on it on a white ground, never over other words; arrows arriving at a box spread along its side; larger arrowheads, readable on a phone.
- 📊 A chart writes the values its lesson gives (a pie's percentages with "%"), and only hides the one the card asks for.
- ✋ A card's « Annuler » drops its correction at once, whatever it is at (the AI writing it, or a dictation): the field closes and the card stays as it was.
- ⏱️ The waiting card says how long a lesson really takes, by its number of pages (« Environ 15 secondes »), no longer « moins de 10 secondes ».
- Diagrams of institutions and organisations (who elects, appoints or controls whom) are laid out automatically: boxes in layers, as few crossing arrows as possible, arrow words never on one another or on a box, readable on a phone.
- A diagram too small to read on a card is drawn again more compactly; an arrow from a box to itself is no longer drawn.
- 📅 **Timelines**: periods drawn under the line, each in its own colour, a period within another (a battle in its war) on a lane of its own instead of hidden; each period's name on its bar with its years; the years on the line on round numbers (600, 800…); an event's year always written.
- 🔁 A lesson whose AI got stuck repeating a card (or its tags) keeps each card once, with a few tags.
- Map names are no longer cut by the edge of the map.
- 🏷️ A scheme's label whose point fell just beside its part (an antibody's light chain) is joined to the part itself, not to the void.
- 🎤 While dictating, the microphone button shows clearly that it is listening.
- 🎙️ Dictating on the phone (Android 13 and later): no more sound at each pause.
- 🏷️ A labelled scheme drawn freely (a cell, a flower, an organ): its names set beside it, a line to each part, never across its outlines.
- 🧬 Two DNA strands are drawn face to face, each base joined to its pair (and their hydrogen bonds when asked), the complementary strand computed.
- 🗂️ A classification whose groups sit side by side in another (mammals and birds among the tetrapods) is drawn as boxes in boxes, its names never cut nor on one another.
- 🦠 A cell dividing, its chromosomes, a population of bacteria: drawn as such, no longer boxes of text.
- ⚗️ In a hydrogen bond, the oxygen's (or nitrogen's) non-bonding pairs face the hydrogen; a molecule drawn with an atom too many bonds, or a hydrogen bond between two atoms without its H, is drawn again.
- 🪟 On Windows, a figure Typst refused is told to the AI with its accents and symbols intact, so that it corrects it.
- Figures: a timeline, set diagram, chart, number line, chronophotography, sphere, crystal, circuit branch or lens given an input that used to crash it is now drawn as meant or refused with a message that lets the AI correct it, instead of failing with an obscure error.
- Numbers on a figure's axes and on a mechanics figure's marked angles are written with the language's decimal comma, without rounding noise.
- A line chart of large values (a population in millions) is drawn instead of failing.
- Sequences written in lowercase letters (atg gca) are aligned letter by letter, and amino acids written in capitals (MET-PRO-GLU) one per codon.
- A line tangent to a curve is found where it touches it, instead of being refused as not meeting it.
- ⚗️ A Lewis structure's non-bonding pairs drawn where its bonds leave room, never on a bond, whichever way the molecule is turned.
- Graphs: a period's or an amplitude's name (a double arrow) set clear of the curve, never written across the sinusoid.
- 🏷️ A card's sub-deck field no longer cuts its placeholder on newer phones' browsers.
- Figures: on a number line, names or numbers too close together no longer written on each other; large numbers written with their thousands apart (20 000).
- Bar charts drawn as horizontal bars when the description asks for them; a long name on two lines instead of making the whole chart wide and its text tiny; counts in the millions graduated.
- 🔌 **Circuit figures**: a branch's components are spaced and wired by the drawing itself, so they are never drawn on one another, a branch is never left open, and each current's arrow sits on its own branch, its name apart from the components'.
- In the app's settings, « Vérifier » on a subscription that has ended no longer says « Clé vérifiée : à jour » next to « Votre abonnement est terminé ».
- 🔌 **Figures: a house installation** drawn the way a textbook draws it: the socket with its phase, neutral and earth terminals, the earth wire green-and-yellow going to the earth symbol and never to the neutral, the general breaker on both the phase and the neutral.
- Chronophotographies (a ball thrown, a fall, a uniform or accelerated motion, a circular one) drawn with their positions computed: on their trajectory, the velocity vectors along it, the change of velocity where it is.
- A graph described by conditions only (the intermediate value theorem's f(a) < 0 < f(b), a function decreasing past a value k, a maximum M, two zeros): its curve drawn through points that satisfy them, varied as a textbook draws a function unless the description says it is monotone, crossing the axis only as often as the description says, the point c where f(c) = 0 or k computed exactly at the crossing, and the signs never reversed.
- A function given by its two ends drawn as a curve, no longer as a straight segment.
- A graph naming a single value on an axis (a maximum M), two values at the same height, or no value on an axis no longer fails to draw.
- Tables drawn with their formulas, chemical formulas (H₂O, Cu²⁺) and arrows instead of the code that wrote them, and with the sentence under them.
- Physics figures keep their scene: the body in its liquid, both bodies with their two forces, the marked angle and the displacement, the scale; a solid on an inclined plane rests on it.
- 📜 A map's credit links to the atlas and its data's pages, no longer to Typst's package site.
- Cards: the explanation and the memory tip no longer grow by themselves when scrolling on a phone; they are as tall as their text.
- 🔢 A graph's axis no longer writes a plain number on top of a value named next to it (u₂ against 2).
- 📏 Lines in geometry figures no longer run far past their figure, so the figure keeps a readable size on the card.
- 📈 A graph's frame larger than 9 cm is drawn smaller as a whole (an orthonormal frame stays orthonormal), so the card no longer shrinks its text.
- A curve given by its points or its table of variations passes through every point, level at its minimum and maximum.
- 🔄 A rotation's direction drawn as an arc with its arrow, the right way, instead of a figure sometimes drawn without it.
- 📈 A graph's asymptote or limit line is drawn across the whole frame, broken where it would cross the axis's numbers (no more "3" read as "−3"), and always named ("y = 3").
- 📈 The names of a graph's curves and lines (𝒞f, y = x) are set along each one, clear of the other lines and of each other.
- ↗️ A translation's image no longer drawn on its figure nor its arrow along a side, when the lesson gives no vector.
- A tangent to a circle is no longer drawn so long that the figure shrinks to nothing.
- 🔺 A pyramid's height written beside it, never on an edge; its foot's and vertices' names clear of one another.
- Diagrams: two arrows each way between two boxes (the states of matter) drawn as a diagram again, never as a drawing with labels on one another.
- Circuits: the wire no longer cut around a current's arrow, the circuit no longer drawn open.
- 📏 Points on a number line placed at their value, never beside the line or on the wrong graduation; its numbers written once.
- A decimal number quoted in a figure's formula no longer drawn with a space after its comma ("1, 5").
- Graphs: the point where two curves meet is computed and clearly marked, with its coordinates when the card asks for them.
- Fractions shown on a disc, a bar or a rectangle: exactly the parts asked for are coloured, whole.
- Venn diagrams: a part's name (A ∩ B) no longer lies on the circles; elements sit in their parts, a union or a complement is named beside the diagram, and an event alone is drawn with its own circle only.
- Geometry figures: vectors are drawn with their arrow and their name, never as plain segments.
- 〰️ A curve given by its measures is no longer replaced by a function of the AI's own that misses some of them.
- Geometry figures: lengths are written beside their segments, never on them; Thales' configuration keeps the lengths given, its points placed from them.
- Figures: names on a graph's axis that would touch are set on two rows; a frame's axes numbered at whole units only; roots of unity drawn on the unit circle, named as the lesson names them.
- Chemistry: several molecules in one figure are drawn side by side, each with its name, no longer one on another; a hydrogen bond is drawn dotted.
- 📈 Two curves of the same measure are no longer drawn on two different axes, which made a small change look as large as a big one.
- Figures: a Greek letter in a figure's formula (λ, π, α) is no longer replaced by a number the AI named after it.
- A circle or points in a coordinate frame drawn with their graduated axes, instead of a rough drawing.
- A trigonometric circle with a single angle is drawn.
- A probability law's bar chart is graduated by tenths or hundredths, its values readable.
- Figures: numbers written as the lesson's language writes them (a decimal comma in French, German…, a point in English), never LaTeX's `{,}`.
- The trigonometric circle: its points at their angles, its cosine and sine projected, no stray names.
- Number lines: an interval's brackets are turned the right way ([2 ; +∞[, ]2 ; 7[).
- Sets inside one another (ℕ ⊂ ℤ ⊂ ℝ, a classification's groups): each element drawn in its own ring.
- Lewis structures show their atoms' non-bonding pairs.
- A chart's long category names no longer overlap, and a curve shows only the values the lesson gives.
- Diagrams: an arrow's label no longer lies on the boxes it joins or on another label (energy chains, cycles).
- A ball's radius no longer written against its centre's name or across its equator.
- Chemical formulas and reaction equations are written as chemistry (\(\ce{2H2 + O2 -> 2H2O}\)) and shown as such in the cards' preview, as in Anki.
- A figure the AI drew empty (a map of plates, volcanoes or earthquakes) is drawn again instead of going on the card blank.
- Figures drawn as SVG keep their colours, fonts and labels when they style them with classes, the font shorthand or a halo, or put a label in a link or along a curve.
- A figure whose colours are written as rgb(…) or hsl(…) no longer comes out black.
- A figure whose colours are mixed (a pH scale's band from red to blue) no longer comes out black.
- In geometry figures, a transformed figure's points are named with a prime (A', B', C'), and the lengths a figure is given are written on it.
- A cone's height is written beside it, no longer across its side.
- A solid's lengths are written beside its edges, no longer across them.
- Diagrams' lines are no longer drawn with a bar across them.
- Diagrams whose boxes hold long texts are no longer drawn tiny, and links between boxes are no longer drawn with a bar across them.
- Every sheet is announced as a dialog by screen readers (TalkBack), and every sheet slides in from the bottom.
- A card no longer shows "\n" where the AI meant a line break.
- On a dictation card's back, the sentence to write is no longer glued to its instruction.
- Labelled drawings (an organ, a cell): their labels no longer cut off at the edge.
- Diagrams of boxes and arrows: several things carried between two boxes in one labelled arrow, long chains on two rows, arrows always drawn as arrows.
- A diagram label corrected by the AI keeps its place on the diagram when its question is only reworded.
- Maps: countries and seas found by their usual names in every language of the page ("Chine", "Stati Uniti", "Méditerranée", "Atlantik").
- Graphs of data (a population over the years, a temperature over time): drawn at a readable size, their axes at the frame's start.
- Graphs: the axes' names no longer cut off at the edge; a curve with a plateau drawn in one piece; a period's double arrow.
- Electric circuits: the current's direction drawn when asked, the right way in every branch; a short circuit named.
- Diagrams of boxes and arrows: plain and dashed lines told apart (contact, action at a distance); the labels of arrows going both ways no longer on top of each other.
- A figure on a card's front no longer writes the answer the card asks (a count, a measure), even when its description says so.
- Number lines drawn cleaner: the line ends at its last graduation, decimals written with their comma, nothing written that the card didn't ask for.

## [1.1.1] - 2026-11-04

### Changed

- The Android app's privacy policy says how to have your data deleted, step by step, and what is deleted or kept.
- The Android app's privacy policy says what this version does: the lesson's drawings cut out of its photos, a child's class sent with their lessons (never their first name), backups, the background notification, the QR code read by Google Play services.

### Fixed

- On a narrow phone, a lesson's one page is shown beside the add buttons again, not under them.

## [1.1.0] - 2026-11-03

### Added

**The Android app**

- 📱 Notosaurus on Android: a lesson photographed, its cards made and sent straight to AnkiDroid, no computer needed. The AI is the Notosaurus service's (no key to get), with a subscription through Google Play, by the month or the year, restored by itself on a new phone. Or, for free, the app shows the computer's page (the Anki add-on): scan its QR code.
- 🎁 A free trial without a card, once per phone: it starts with the first lesson.
- The cards in AnkiDroid are the computer's: the same note types, so a lesson sent from the phone or from the computer is the same notes, never added twice. Natural voices (Google Chirp 3 HD), pictures and figures, dictations, typed answers, reversed cards, multiple choice, texts with gaps and diagrams with their labels hidden.
- 🎤 Instructions and corrections by voice, written down as you meant them (hesitations out, "ten, no, twelve" → twelve), then read over.
- 📚 A lesson reviewed in AnkiDroid right after it is sent; **Open AnkiDroid** in the top bar.
- The app follows the phone's dark mode; Android's back button closes the open sheet first.

**Making a lesson**

- ⚡ Quick or 🎯 Careful: quick by default, 2 to 4 times faster and cheaper; careful for a rich lesson (a diagram, maths). After a quick lesson, **Make again, carefully**.
- The cards show as the AI writes them, the waiting card says what the AI is at, and **Cancel** stops it.
- ➕ A page added to a lesson days later: the AI reads only the new pages; the cards made already, and their notes in Anki, stay as they are.
- 🖍️ On a photo not sent yet, black out with a finger what the AI shouldn't see (a name, a school).
- ✨ **Tidy up** rewrites the instructions clear and short, nothing added; ↩ Undo brings them back.
- The lesson in progress is never lost by leaving the page: its photos and prompt are found again.
- On a computer, photos and PDFs dragged from a folder onto the page.

**Notosaurus's prompts**

- New: **Dictation**, **Gap dictation**, **By heart** (a poem, a recitation, line by line), **Recognise from an example**, **Dates and landmarks** (learned both ways), **Table to learn**, **Definitions and properties** (a theorem's name → its full statement, and its converse when the lesson gives it), **Language: conjugation**, **Methods (steps)**. **Automatic** recognises each of these kinds of page.
- Any prompt can ask for the reverse card, the backs read aloud, slow or normal speed, no pictures, no helps.

**Cards**

- ✨ **Correct this card** (a card's ⋯): say what's wrong ("the answer is 1789", "shorter"), typed or dictated, and the AI rewrites that card alone; ↩ Undo. A card just added, still empty: **Write with the AI**.
- ⚠️ A lesson that looks wrong (a pupil's notes, a copy mistake: a wrong date, name or number) is said on its card, with the correction to take or not; never sent to Anki.

**Pictures and figures**

- One **✨ Image** button, the cheapest first: a drawing from the lesson's own page cut out of the photo (35 right out of 36 on 11 lessons); else a free picture (Wikimedia Commons, Openverse; Pixabay in the app), with no credit to give and filtered for pupils, the best ones first; drawn by the AI only once you say yes.
- Figures drawn in Typst with the package made for each kind: geometry (marks and angles computed), graphs computed from their function, sets, diagrams, circuits, chemistry, timelines. 🔍 under a figure has the AI check it and redraw it when it's wrong.
- Each picture says where it comes from (its source, licence and page), and each figure what drew it, crediting the open-source projects behind it.

**Into Anki**

- ✎ **Notosaurus** under every answer in Anki: the card opened in Notosaurus to correct it, in the app on Android or in the page on the computer.
- 🔊 **Add to Anki** is quicker (the sounds made in the background beforehand) and says how far it is. A lesson not changed since its send says **✓ Up to date in Anki**.
- After a send, the cards in Anki that no longer match the lesson are listed, deleted only on **Delete from Anki**.

**Tests to prepare**

- 📌 A lesson, whole or some of its cards, added to a test (a name, a date): its cards tagged in Anki, and its sheet says how to review them all (custom study, a filtered deck). On the computer, **Revise now in Anki** makes the filtered deck; on Android, **Open in AnkiDroid**. The lessons not in Anki yet are sent from the test's sheet.

**Children and settings**

- 🧒 **Children**: a card each, with a first name, a class typed freely (another country's, Prépa, university…), its decks and instructions for the AI. The AI is told the class and the instructions, never the first name. The next lesson is for the child chosen.
- 💾 **Back up or move my lessons**: every lesson in one file (photos, cards, pictures, sounds), with the children, the tests and your prompts, no key or password; imported on another computer or in the Android app. A lesson's cards already in Anki are found again, never added twice.
- **About**: Notosaurus is free software (AGPL-3.0), with the privacy policy and the libraries' licences.

**For developers**

- `notosaurus-core` (in `core/`): the AI and card logic as a package of its own. The Notosaurus relay's API, `core/relay-api-v1.json`, is frozen for each released app (`core/relay-api-releases/`), and a test refuses a change that would break one.
- The Android app in `android/`, built and tested with the same page; device tests with real AnkiDroid (on Mondays, several of its versions side by side).
- Notosaurus's prompts and the AI's fixed rules in files of their own: `static/prompts/<lang>/`, `core/notosaurus_core/rules/`, `core/notosaurus_core/typst_rules/`.
- `NOTOSAURUS_PICTURE_SERVICE` and `NOTOSAURUS_PICTURE_MODEL` (`.env`) give the pictures' service and model by default (Docker).

### Changed

- The Anki note types and their cards are named in English, the same whatever the app's language: "Notosaurus front/back (audio) v2", "Front → Back"… (they were French everywhere). On the computer, a 1.0.0 lesson's notes move to them at the next send, their review history kept.
- A card's note in Anki is found by the card itself, never by its front: a corrected front, two cards with the same front, or dictations without a sentence each keep their own note, and a package imported again after a correction updates the card instead of duplicating it. A lesson made again keeps the notes of the cards that stay the same. Lessons sent with 1.0.0 come into Anki anew, once, the next time they are sent.
- The button under the prompt says what it does: "See the instructions" for Notosaurus's own, "Save the changes" for one of yours once its text is changed (saved into it at once), "Edit instructions" otherwise.
- Once a lesson's cards are made, step 2 (the prompt) folds to one line, its prompt and speed, so the cards come first; **✏️ Change** opens it. Its buttons stay in view, and a prompt changed since the cards were made says it isn't applied until they are made again. Step 3's "Prompt used for this lesson" is gone: the folded line says it.
- A picture can be on any card in Anki, no longer on a card of its own: a dictation, a reversed or typed card keeps its picture. **Anki asks for a full sync once.** The picture cards sent by 1.0.0 are sent again as new notes; the old ones are offered for deletion (their review history isn't kept).
- A photo is kept as taken, no longer turned upright by guess (sometimes upside down): **↻** turns it.
- Pictures where they truly help (a work of art, a person, a place, an animal), never on every card; a picture that would give the answer away goes on the back. **Settings → Instructions for the AI → 🖼️ Pictures on the cards** turns them off.
- Every card says its deck above its question, small (the subject and the lesson). A front that allows another right answer says what tells it apart.
- Only short answers are typed (a word or two); a definition or a sentence is said in one's own words.
- **Did you know?** and the helps on the back are settings (on by default), no longer switches under the prompt. The **Add the reverse card** switch is gone: how the cards are asked comes from the prompt, and can be changed in the correction ("one way only").
- The voices are slowed only for a language being learned and for dictations.
- The review's cards are a third shorter: their buttons on the front's line, Report and Delete behind **⋯**.
- The page speaks of children, not of Anki profiles.
- The big button at the bottom is always the next action: photograph the lesson, generate the cards, or generate from the prompt alone once it says what to learn.
- Notosaurus's prompts reviewed: none imposes French or English any more, and each lesson gets a deck of its own.
- The AI only makes learning material suited to pupils; anything else is refused with a clear message. Lessons on hard topics (history, biology, health) still work.
- The pages load nothing from elsewhere (no CDN, no Google Fonts): they work offline, and no third party sees their visits.
- Gemini not answering is given up on after 45 s for the next model, instead of waiting forever.

### Fixed

- In the Android app, a lesson whose cards were sent to AnkiDroid with an older Notosaurus note type updates those notes, their review history kept, instead of adding each card again and offering the old ones for deletion. AnkiDroid can't change a note's type, so they keep theirs.
- A lesson made again keeps the notes and review history of its cards in Anki when the AI writes a card's question otherwise but its answer is the same and the lesson's only one, a dictation's word for instance: they became new cards, the old ones offered for deletion.
- An Anki package (.apkg) made by 1.1.0 imports beside 1.0.0's note types, where Anki 2.1.4x refused its notes ("the note type changed").
- A card the AI corrects no longer takes another card's history in Anki because they share an answer ("True", "False", a multiple choice's option): it is matched by its answer alone only when that answer belongs to one card of the lesson.
- In the Android app, a lesson's pictures reach AnkiDroid even where an older Notosaurus made the note types (synced from the computer's 1.0.0), and the cards just sent are never offered for deletion as leftovers. The note types now carry a version ("Notosaurus QCM v2"); on the computer, the notes of an older one move to it with their review history.
- A lesson made again, or corrected by the AI, keeps the review history of its cards in Anki when the AI only changes a capital, a final full stop or a quote mark ("la mère" / "La mère."): such a card was taken for a new one. An accent or a digit changed still makes another card.
- In the Android app, a lesson's pictures and sounds are made too when the app is left (home, the screen off), and its send to AnkiDroid goes on: turning the screen off during "In Anki: sounds…" left the cards without sound.
- A topic of one word written in one of Notosaurus's prompts ("Automatic" and "The capitals") makes the cards without a photo again: the button below stayed on "Take a photo of the lesson" until three words were written. The hint under the prompt says what to write for the button to make the cards.
- A lesson made with a prompt of several lines ("⭐ Automatic"…) no longer says "Changed since the cards were made" at once, and opened again it shows its prompt, no longer "✏️ Free".
- With pages taken, the "Next page", "Gallery" and "PDF" buttons come first, always in the same place, two pages high: no longer a column taller than the pages, alone under them. A lesson of one page shows it large beside them.
- Once a lesson has its 10 pages, the add buttons are greyed out and say so ("10 pages at most"), instead of refusing the next photo.
- In a lesson already made, a photo put in place of another (removed, then chosen from the gallery) turns itself when turned: the lesson's old photo came back, turned, in its place.
- A card corrected after a send updates its own note in Anki (its review history kept) instead of adding a second one; a lesson whose deck changed moves its cards there. A part named like the deck's last level no longer makes a second deck inside it.
- A formula shows as meant when the AI wrote it with a single backslash or with brackets for an interval; formulas in the info and "Did you know?" are drawn, no longer shown as LaTeX.
- Accents written as HTML entities ("trach&eacute;e"), tags or Markdown the AI wrote in a card: made plain text.
- 🔊 reads a back in Russian, Greek, Chinese, Japanese, Arabic…; a phonetic transcription is no longer read aloud; a dictation's sound no longer makes words up; listening again no longer plays two voices at once.
- A dictation in the pupil's own language gets its voice with **Automatic**.
- Without a photo, an unchanged prompt no longer makes cards on a made-up subject: the page says to write what to learn.
- A picture an image service refused or didn't give leaves that card without one, no longer failing the lesson's other pictures. A picture drawn by Gemini is counted at the image's price (it counted a twentieth of it).
- Claude makes lessons again with the helps or the fun facts on.
- A lesson keeps to its 10 pages, from the gallery and the camera too.
- Instructions typed while the page was starting are no longer replaced; a long back is seen whole in the review; scrolling the lessons no longer moves the page behind.
- Notosaurus's prompts as each language writes them (Brazilian Portuguese throughout).

### Security

- Notosaurus answers only when opened by an IP address, `localhost` or `NOTOSAURUS_PUBLIC_URL`: a website open on the computer can no longer reach it (DNS rebinding) to read the lessons or change the settings. A `Host` with a line break or an impossible port is refused.
- A new settings password needs 8 characters; after 5 wrong ones the device must wait, longer at each try. Those typed on the computer itself never lock it out.
- A card's id is checked (it names its picture's file); a photo over 4 MB, or claiming an enormous size in a few kilobytes, is refused.
- Nothing of a lesson in the logs any more, on the computer and on the relay.
- The Docker image runs Notosaurus as its own user, not root. A `notosaurus-data` volume made by an older image is handed over once with `docker run --rm -u 0 -v notosaurus-data:/data notosaurus chown -R notosaurus: /data`.

## [1.0.0] - 2026-10-04

The first version.

### Added

**From a lesson to cards**

- Photos of a lesson (handwriting included, pages taken sideways straightened), a PDF (its text read exactly) or the instructions alone: a vision AI drafts the cards. Gemini, Claude, GPT, OpenRouter or a local model.
- Instructions for each kind of lesson, ⭐ "Automatic" choosing the cards from the page; your own saved instructions, or written for one lesson; standing instructions per child ("in year 8").
- Card types: questions and answers, fill in the blanks, multiple choice, true or false, vocabulary and sentences of a language, formulas, geometry with exact figures, diagrams with their labels hidden, pictures drawn by an image model, typed answers and dictations.
- Helps on the back where they help (why the answer is right, a genuine way to remember it), optional "Did you know?" facts, and 💬 an explanation of any card while reviewing.
- Review: edit, add or delete cards, fix them in plain words with the AI, generate again, undo.
- Natural audio of the backs, in the deck: it plays everywhere, even offline.

**Into Anki**

- An Anki add-on: Notosaurus starts with Anki, installs its components after asking (about 300 MB, once), and a setup assistant guides the first steps (the AI and its key, then the phone).
- Sent straight to Anki and synced, updated without duplicates; or an `.apkg` file. Each lesson has its own deck, under the subjects already there.

**For families**

- One Anki profile per child, each with their own lessons, shared or not; the lessons grouped by subject, with a search.
- Only the phones that scanned the QR code use Notosaurus; the settings open on the computer only.
- What each lesson cost, call by call.

**Settings, languages, help**

- Recommended models for each service, from our tests on real notebook pages, with what a lesson or a picture costs; a test for the AI and for the pictures. A free Gemini key works, with an older model.
- The app, its instructions and the add-on in English, French, Spanish, German, Italian and Portuguese (Brazil); the documentation in English and French (https://cchabanois.github.io/notosaurus/).

[Unreleased]: https://github.com/cchabanois/notosaurus/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/cchabanois/notosaurus/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/cchabanois/notosaurus/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/cchabanois/notosaurus/releases/tag/v1.0.0
