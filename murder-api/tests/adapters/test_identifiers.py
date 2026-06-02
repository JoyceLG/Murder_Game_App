from src.adapters.identifiers import CODE_ALPHABET, CODE_LENGTH, RandomCodeGenerator, UuidGenerator


def test_uuid_generator_produces_unique_ids():
    gen = UuidGenerator()
    ids = {gen.new_id() for _ in range(100)}
    assert len(ids) == 100


def test_code_generator_uses_unambiguous_alphabet_and_length():
    gen = RandomCodeGenerator()
    allowed = set(CODE_ALPHABET)
    for _ in range(100):
        code = gen.new_code()
        assert len(code) == CODE_LENGTH
        assert set(code) <= allowed
