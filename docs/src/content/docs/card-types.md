---
title: "Card types"
description: "Question and answer, fill in the blanks, multiple choice, true or false, diagrams, formulas, figures and pictures: what each card type does in Notosaurus and in Anki."
---

The instructions decide which kind of cards the AI makes (see [Instructions](../instructions/)).
Each kind becomes its own **note type** in Anki, whose name starts with “Notosaurus”.

## Question and answer

The classic card: a **front** (the question, a word in your language) and a **back** (the
answer, the word in the language being learnt), with an optional **info** shown under the
answer. It's what the vocabulary, sentences and questions instructions make.

Options, at the bottom of the lesson: the **reverse card** (back → front), **type the answer**
(Anki compares letter by letter) and **dictation** (hear the back, write it). See
[Reviewing the cards](../review/#card-options).

## Fill in the blanks

The **Fill in the blanks** instructions make sentences with gaps:

> The Sun heats the water of seas and lakes: this is `{{c1::evaporation}}`.

What is between `{{c1::` and `}}` is hidden. **Each number makes one card** in Anki; the same
number used twice hides two gaps together. In the review, the gaps are shown numbered: you can
change their text, add some or remove some by editing the braces.

![Cards with gaps](../../assets/screenshots/en/cloze.png)

## Multiple choice and true or false

**Multiple choice** cards have a question, the **right answer** and **wrong answers** (three
plausible ones): change them in the review, or add one with **+ wrong answer**.
**True / false** makes statements, half of them false with one precise mistake.

![A multiple-choice card](../../assets/screenshots/en/quiz.png)

In Anki, the question shows the options (A, B, C…, always in the same order) and the answer
marks the right one. It's plain HTML: it looks the same on every Anki app.

## Diagrams

With the **Diagram to complete** instructions, the AI finds each label of a diagram and hides
it behind a number. Each card asks “What is (2)?” and shows the answer on the diagram.

![A diagram with its labels hidden](../../assets/screenshots/en/diagram.png)

In the review:

- drag a **red mask** to move it, and its **round corner** to resize it, so that it hides the
  whole label;
- the **dashed frame** is the part of the photo that Anki shows: drag its blue corners to crop
  it.

Gemini and GPT place the masks most precisely. With Claude, check that the masks hide the
whole label on handwriting.

## Formulas

Formulas are written in **MathJax**, which Anki displays: `\( \frac{a+b}{2} \)`,
`\( x^2 \)`. The review shows them drawn under the text. Simple calculations stay as plain
text.

## Figures

For geometry and simple labelled figures (a right triangle with its hypotenuse, a circle with
its radius, a rectangle with its measures), the AI **draws an exact figure** on the card,
instead of an image model that would draw text and measures badly. The figure never shows the
answer.

![Geometry cards with their figures](../../assets/screenshots/en/figures.png)

The **🖼️** button of a card opens its figure: change its description and draw it again, or
move it to the back when it belongs to the answer. The **Geometry (with figures)** instructions
make such cards, and so do **Automatic** and the formula instructions when it helps.

## Pictures

The **Words in pictures** instructions put a picture of each word on the front, drawn by an
image model: from less than a cent to a few cents per picture. Pictures are drawn by the AI
service of the cards when it can draw (Gemini, OpenAI, OpenRouter), otherwise by another one
chosen in **Settings → Pictures on cards** (Claude and local models can't draw). That section
also chooses the image model, or **No pictures**.

![Cards with pictures](../../assets/screenshots/en/pictures.png)

The **🖼️** button of a card opens its **Picture** panel:

- **What to draw (in English)**: change the description, then **🎨 Draw again** (about 3 to 7
  US cents a drawing);
- **📷 My photo**: put your own photo instead, for free;
- **✕ No picture**: remove it;
- **On the back (with the answer)**: when the picture gives the answer away.
