"""Smoke test: validates the test tooling is wired correctly."""


def test_tooling_runs():
    assert True


def test_src_package_importable():
    import src  # noqa: F401
