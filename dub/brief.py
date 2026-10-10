"""One pass over the whole transcript: topic, speaker style, and term rules for translators."""
from . import config, gem

SCHEMA = {"type": "object", "properties": {
    "summary": {"type": "string"}, "speaker_style": {"type": "string"},
    "terms": {"type": "array", "items": {"type": "object", "properties": {
        "source": {"type": "string"}, "rule": {"type": "string"}}, "required": ["source", "rule"]}}},
    "required": ["summary", "speaker_style", "terms"]}


def make_brief(units: list[dict], info: dict, src: str) -> dict:
    text = "\n".join(f"[{u['id']}] {u['text']}" for u in units)
    return gem.json_call(
        f"Video title: {info.get('title')}\nChannel: {info.get('channel')}\nTags: {info.get('tags') or []}\n"
        f"Transcript ({config.LANGS[src]}):\n{text}\n\n"
        "Prepare a dubbing brief in English. summary: 3 sentences on topic and audience. speaker_style: tone, "
        "energy and formality in one sentence. terms: product names, acronyms, jargon and proper nouns, each "
        "with a rule (keep as-is / translate as X / spell out). Use the channel name, title and tags as ground "
        "truth for brand spelling.", SCHEMA)
