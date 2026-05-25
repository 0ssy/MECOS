import asyncio
import os

from memory_system import MemorySystem
from trading.trading_agent import TradingAgent
from trading.broker_connector import BrokerConnector

SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA"
]


async def main():

    memory = MemorySystem()

    quant_mode = os.getenv("MECOS_QUANT_MODE", "balanced")
    print(f"Quant mode selected: {quant_mode}")

    trader = TradingAgent(memory, quant_mode=quant_mode)

    broker = BrokerConnector()

    while True:

        try:

            for symbol in SYMBOLS:
                try:
                    data = await broker.get_market_data(
                        symbol,
                        timeframe="1Hour",
                        limit=200
                    )
                    if not data:
                        print(f"\n{symbol}")
                        print("NO_DATA")
                        continue

                    result = await trader.analyze_market(
                        symbol,
                        data
                    )

                    print(f"\n{symbol}")
                    print(result["final_decision"])

                    decision = result.get("final_decision")

                    if decision in ["BUY", "SELL"]:

                        position_size = result.get(
                            "position_size",
                            0.01
                        )

                        account = await broker.get_account_info()

                        equity = account["equity"]

                        dollar_size = equity * position_size

                        current_price = data[-1]["close"]

                        qty = max(
                            1,
                            int(dollar_size / current_price)
                        )

                        order = await broker.place_order(
                            symbol=symbol,
                            qty=qty,
                            side=decision
                        )

                        print(order)
                except Exception as symbol_error:
                    print(f"\n{symbol}")
                    print("ERROR:", symbol_error)
                    continue

            await asyncio.sleep(300)

        except Exception as e:

            print("ERROR:", e)

            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
