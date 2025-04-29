import pytest
import asyncio
from risk_management import calculate_position_size

# Фейковые объекты для тестирования
class FakeClient:
    async def market_data(self, *args, **kwargs):
        pass

class FakeUserState:
    def __init__(self):
        self.balance = 100000
        self.instrument_info = {"lot": 1}
        self.position = None
        self.start_of_day_balance = 100000

@pytest.mark.asyncio
async def test_position_size():
    fake_client = FakeClient()
    fake_user_state = FakeUserState()
    size = await calculate_position_size(fake_client, fake_user_state, "BBG123")
    assert size > 0
