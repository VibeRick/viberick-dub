from pathlib import Path

from dub import config
from dub.languages import LANGUAGES
from tools.gen_langs_js import render


def test_web_language_table_matches_pipeline():
    assert (Path(__file__).resolve().parents[1] / "web" / "langs.js").read_text() == render()


def test_defaults_and_sources_are_targets():
    assert set(config.DEFAULT_LANGS) <= set(LANGUAGES)
    assert set(config.CHIRP_CODES) <= set(LANGUAGES)
    assert len(LANGUAGES) >= 100
