"""Notosaurus's brain: reading lesson photos into cards, correcting and explaining
them, drawing pictures and figures, card audio.

Used by the Notosaurus web app and Anki add-on with the user's own keys. It never
reads the app's settings or lessons: the AI configuration (config.AIConfig) and
everything else come in as parameters, and the results come back as values.
"""

from .files import configure  # noqa: F401
