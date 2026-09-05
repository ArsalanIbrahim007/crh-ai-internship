import pytest
from app.services.sql_service import sql_service
@pytest.mark.parametrize("q",["DELETE FROM sales","DROP TABLE sales","UPDATE sales SET revenue=0","SELECT 1; DROP TABLE sales"])
def test_blocks_writes(q):
    with pytest.raises(ValueError): sql_service.validate_read_only(q)
def test_select_ok(): assert sql_service.validate_read_only("SELECT 1;")=="SELECT 1"
