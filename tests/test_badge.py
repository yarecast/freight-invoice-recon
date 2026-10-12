from recon.report import _badge


def test_no_findings_badge_has_text_and_check_icon():
    out = _badge("SIN_HALLAZGOS")
    assert "NADA QUE REVISAR" in out
    assert "<svg" in out
    assert "http://" not in out and "https://" not in out


def test_other_badges_have_no_icon():
    assert "<svg" not in _badge("HIGH")