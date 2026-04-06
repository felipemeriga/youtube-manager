from persona import PERSONA, format_persona


def test_persona_has_required_keys():
    assert "channel" in PERSONA
    assert "language" in PERSONA
    assert "tone" in PERSONA
    assert "avoid" in PERSONA


def test_format_persona_returns_string():
    result = format_persona()
    assert isinstance(result, str)
    assert len(result) > 0


def test_format_persona_contains_channel_name():
    result = format_persona()
    assert "Além do Código" in result


def test_format_persona_contains_avoid_items():
    result = format_persona()
    for item in PERSONA["avoid"]:
        assert item in result
