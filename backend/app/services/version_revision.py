from math import gcd

_REVISION_ALPHABET = "abcdefghijklmnopqrstuvwxyz"
_REVISION_LENGTH = 4
_REVISION_CAPACITY = len(_REVISION_ALPHABET) ** _REVISION_LENGTH
_AFFINE_MULTIPLIER = 5
_AFFINE_OFFSET = 731

if gcd(_AFFINE_MULTIPLIER, _REVISION_CAPACITY) != 1:
    raise RuntimeError("修订标识映射乘数必须与标识容量互质")

_AFFINE_MULTIPLIER_INVERSE = pow(
    _AFFINE_MULTIPLIER,
    -1,
    _REVISION_CAPACITY,
)


def version_number_to_revision(version_number: int) -> str:
    """将数字版本稳定映射为固定四位纯小写字母修订标识。"""
    if not 1 <= version_number <= _REVISION_CAPACITY:
        raise ValueError(
            f"版本号必须在 1 到 {_REVISION_CAPACITY} 之间",
        )

    value = (
        (version_number - 1) * _AFFINE_MULTIPLIER + _AFFINE_OFFSET
    ) % _REVISION_CAPACITY
    characters = [""] * _REVISION_LENGTH
    for index in range(_REVISION_LENGTH - 1, -1, -1):
        value, remainder = divmod(value, len(_REVISION_ALPHABET))
        characters[index] = _REVISION_ALPHABET[remainder]
    return "".join(characters)


def revision_to_version_number(revision: str) -> int:
    """将固定四位纯小写字母修订标识还原为数字版本。"""
    if len(revision) != _REVISION_LENGTH or any(
        character not in _REVISION_ALPHABET for character in revision
    ):
        raise ValueError("修订标识必须是四位纯小写英文字母")

    value = 0
    for character in revision:
        value = value * len(_REVISION_ALPHABET) + _REVISION_ALPHABET.index(character)

    version_index = (
        (value - _AFFINE_OFFSET) * _AFFINE_MULTIPLIER_INVERSE
    ) % _REVISION_CAPACITY
    return version_index + 1
