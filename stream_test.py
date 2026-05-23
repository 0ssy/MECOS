import os
from dotenv import load_dotenv
from alpaca.data.live.stock import StockDataStream

# LOAD .env
load_dotenv(dotenv_path=".env")

API_KEY = os.getenv("APCA_API_KEY_ID")
API_SECRET = os.getenv("APCA_API_SECRET_KEY")

print("ENV EXISTS:", os.path.exists(".env"))
print("KEY:", API_KEY[:6] if API_KEY else "MISSING")
print("SECRET:", "LOADED" if API_SECRET else "MISSING")


async def quote_handler(q):
    print(
        f"{q.symbol} | "
        f"BID: {q.bid_price} | "
        f"ASK: {q.ask_price}"
    )


stream = StockDataStream(
    API_KEY,
    API_SECRET,
)

stream.subscribe_quotes(quote_handler, "AAPL")

stream.run()