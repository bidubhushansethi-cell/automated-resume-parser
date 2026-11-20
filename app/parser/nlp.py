"""Lazy spaCy loader. The parser still works (with heuristics only) if the model is missing."""
import logging

log = logging.getLogger(__name__)
_nlp = None
_tried = False


def get_nlp():
    global _nlp, _tried
    if _tried:
        return _nlp
    _tried = True
    try:
        import spacy
        _nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"])
    except Exception as exc:
        log.warning("spaCy model 'en_core_web_sm' unavailable (%s). Run: "
                    "python -m spacy download en_core_web_sm", exc)
        _nlp = None
    return _nlp


def entities(text: str, label: str, limit: int = 1000) -> list:
    nlp = get_nlp()
    if nlp is None or not text.strip():
        return []
    return [e.text.strip() for e in nlp(text[:limit]).ents if e.label_ == label]
