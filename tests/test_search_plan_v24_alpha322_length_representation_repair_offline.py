"""Exercise every requested L01-L14 check against the new runtime."""

import pytest
from scripts import search_plan_v24_alpha322_length_representation_fixtures_v1 as fixtures


@pytest.mark.parametrize("key", list(fixtures.SPEC))
def test_length_representation_contract(key, tmp_path):
    result = fixtures.execute(key, tmp_path / key)
    assert result["passed"], result
