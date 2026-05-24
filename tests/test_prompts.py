import json

import pytest

from prompts import load_prompts, slugify


def test_load_prompts_dict(tmp_path):
    p = tmp_path / "p.json"
    p.write_text(
        json.dumps(
            {
                "prompt1": "cat doing backflip",
                "prompt2": "dog surfing",
                "prompt3": "robot painting",
            }
        )
    )
    out = load_prompts(str(p))
    assert out == ["cat doing backflip", "dog surfing", "robot painting"]


def test_load_prompts_list(tmp_path):
    p = tmp_path / "p.json"
    p.write_text(json.dumps(["a", "b", "c"]))
    assert load_prompts(str(p)) == ["a", "b", "c"]


def test_load_prompts_strips_blanks(tmp_path):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"a": "  ", "b": "real", "c": ""}))
    assert load_prompts(str(p)) == ["real"]


def test_load_prompts_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_prompts(str(tmp_path / "nope.json"))


def test_load_prompts_empty(tmp_path):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({}))
    with pytest.raises(ValueError):
        load_prompts(str(p))


def test_load_prompts_bad_type(tmp_path):
    p = tmp_path / "p.json"
    p.write_text(json.dumps("not a list"))
    with pytest.raises(ValueError):
        load_prompts(str(p))


def test_slugify_basic():
    assert slugify("Cat doing a BACKFLIP!") == "cat-doing-a-backflip"


def test_slugify_trims_dashes():
    assert slugify("  --hello world--  ") == "hello-world"


def test_slugify_max_len():
    s = slugify("a" * 200)
    assert len(s) <= 60


def test_slugify_empty_falls_back():
    assert slugify("!!!") == "image"
