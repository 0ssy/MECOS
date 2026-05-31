import ccxt
import os
from dotenv import load_dotenv

# Load your MECOS .env file
load_dotenv()

def fetch_binance_testnet():
    # 1. Initialize Binance in Testnet Mode
    # Make sure these keys are in your .env file as BINANCE_API_KEY and BINANCE_SECRET_KEY
    api_key = os.getenv('BINANCE_API_KEY')
    secret_key = os.getenv('BINANCE_SECRET_KEY')

    if not api_key or not secret_key:
        print("ERROR: BINANCE_API_KEY or BINANCE_SECRET_KEY not found in .env")
        return

    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': secret_key,
        'enableRateLimit': True,
    })

    # CRITICAL: Tell CCXT to use the Testnet (Spot Test Network)
    exchange.set_sandbox_mode(True)

    try:
        print("\n--- Fetching Binance Spot Test Network Data ---")
        
        # 2. Fetch Balance
        balance = exchange.fetch_balance()
        print("\n[BALANCES]")
        for asset, data in balance['total'].items():
            if data > 0:
                print(f"{asset}: {data} (Free: {balance['free'][asset]}, Used: {balance['used'][asset]})")

        # 3. Fetch Open Orders
        open_orders = exchange.fetch_open_orders()
        print(f"\n[OPEN ORDERS]: {len(open_orders)}")
        for order in open_orders:
            print(f"- {order['symbol']} {order['side']} {order['amount']} @ {order['price']}")

        # 4. Fetch Recent Trades (My Trades)
        # Note: Testnet often clears trade history, but we'll try to fetch recent ones
        print("\n[RECENT TRADES]")
        # We'll check for a few common pairs
        for symbol in ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']:
            try:
                trades = exchange.fetch_my_trades(symbol, limit=5)
                for t in trades:
                    print(f"- {t['datetime']} | {t['symbol']} | {t['side']} | {t['amount']} @ {t['price']} | PnL: {t.get('fee', {}).get('cost', 'N/A')}")
            except:
                continue

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    fetch_binance_testnet()
