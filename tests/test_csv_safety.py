import pytest

from recon.report import CSV_DANGEROUS, safe_cell


@pytest.mark.parametrize("value", ["=1+1", "+52 81", "-5", "@SUM(A1)"])
def test_formula_like_cells_are_neutralized(value):
    result = safe_cell(value)
    assert result[0] not in CSV_DANGEROUS
    assert value in result


def test_normal_text_is_unchanged():
    assert safe_cell("Rio Grande") == "Rio Grande"