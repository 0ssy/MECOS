import asyncio
import os

from trading.live_trading_connector import LiveTradingConnector

async def on_quote(data):

    print()
    print('QUOTE RECEIVED')
    print(data)

async def main():

    connector = LiveTradingConnector(
        api_key=os.getenv('ALPACA_API_KEY'),
        secret_key=os.getenv('ALPACA_SECRET_KEY'),
        paper=True
    )

    await connector.stream_quotes(
        ['AAPL'],
        on_quote
    )

asyncio.run(main())
