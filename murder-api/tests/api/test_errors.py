from src.api.errors import domain_error_handler
from src.domain.errors import DomainError, GameNotFound


async def test_mapped_domain_error_uses_its_status():
    response = await domain_error_handler(None, GameNotFound("ABCD"))
    assert response.status_code == 404


async def test_unmapped_domain_error_falls_back_to_400():
    response = await domain_error_handler(None, DomainError("boom"))
    assert response.status_code == 400
