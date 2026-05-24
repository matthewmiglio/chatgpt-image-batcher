"""CLI parsing tests — verifies the public CLI contract from the README."""

import json

import pytest

import image_gen


def test_parser_auth():
    args = image_gen.build_parser().parse_args(["auth"])
    assert args.command == "auth"


def test_parser_generate_with_flags(tmp_path):
    pj = tmp_path / "p.json"
    pj.write_text("{}")
    args = image_gen.build_parser().parse_args(
        ["generate", "--prompts", str(pj), "--output", str(tmp_path)]
    )
    assert args.command == "generate"
    assert args.prompts == str(pj)
    assert args.output == str(tmp_path)


def test_parser_generate_positional_path(tmp_path):
    """Supports `generate "C:/prompts.json"` shorthand from the spec."""
    pj = tmp_path / "p.json"
    pj.write_text("{}")
    args = image_gen.build_parser().parse_args(["generate", str(pj)])
    assert args.command == "generate"
    assert args.prompts_positional == str(pj)


def test_parser_generate_missing_prompts_errors(tmp_path):
    with pytest.raises(SystemExit):
        image_gen.main(["generate"])


def test_parser_no_command_errors():
    with pytest.raises(SystemExit):
        image_gen.build_parser().parse_args([])
