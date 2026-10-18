from src.api.errors import domain_error_handler
from src.domain.errors import (
    CodeSpaceExhausted,
    ConcurrentUpdate,
    DomainError,
    GameNotFound,
    NotAuthenticated,
)


async def test_mapped_domain_error_uses_its_status():
    response = await domain_error_handler(None, GameNotFound("ABCD"))
    assert response.status_code == 404


async def test_unmapped_domain_error_falls_back_to_400():
    response = await domain_error_handler(None, DomainError("boom"))
    assert response.status_code == 400


async def test_new_errors_have_meaningful_statuses():
    assert (await domain_error_handler(None, NotAuthenticated())).status_code == 401
    assert (await domain_error_handler(None, ConcurrentUpdate("ABCD"))).status_code == 409
    assert (await domain_error_handler(None, CodeSpaceExhausted())).status_code == 503
