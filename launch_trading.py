import asyncio
import os
from trading.live_trading_connector import LiveTradingConnector

async def main():

    connector = LiveTradingConnector(
        api_key=os.getenv('ALPACA_API_KEY'),
        secret_key=os.getenv('ALPACA_SECRET_KEY'),
        paper=True
    )

    account = await connector.get_account()

    print()
    print('MECOS TRADING CORE ACTIVE')
    print(account)

asyncio.run(main())
