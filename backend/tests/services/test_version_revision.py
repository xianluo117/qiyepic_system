import pytest

from app.services.version_revision import (
    revision_to_version_number,
    version_number_to_revision,
)


def test_revision_mapping_is_stable_and_shared_by_version_number() -> None:
    assert version_number_to_revision(1) == "abcd"
    assert version_number_to_revision(2) == "abci"
    assert version_number_to_revision(10) == "abdw"


@pytest.mark.parametrize("version_number", [1, 2, 10, 1000, 456_976])
def test_revision_mapping_round_trip(version_number: int) -> None:
    revision = version_number_to_revision(version_number)

    assert len(revision) == 4
    assert revision.isascii()
    assert revision.isalpha()
    assert revision.islower()
    assert revision_to_version_number(revision) == version_number


@pytest.mark.parametrize("version_number", [0, 456_977])
def test_revision_mapping_rejects_out_of_range_versions(version_number: int) -> None:
    with pytest.raises(ValueError, match="版本号必须在"):
        version_number_to_revision(version_number)


@pytest.mark.parametrize("revision", ["abc", "abcde", "ABCd", "ab1d", "中文ab"])
def test_revision_mapping_rejects_invalid_revision(revision: str) -> None:
    with pytest.raises(ValueError, match="四位纯小写英文字母"):
        revision_to_version_number(revision)
