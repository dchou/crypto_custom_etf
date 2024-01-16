"""
Strategy Description


"""

import os
from datetime import datetime

import pandas_ta
from dotenv import load_dotenv
from lumibot.backtesting import PolygonDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.entities import Asset, TradingFee
from lumibot.strategies.strategy import Strategy
from lumibot.traders import Trader

# load .env file (if one exists)
load_dotenv()

"""
Strategy Description

This strategy uses bollinger bands to determine when to buy and sell. It will buy when the price is below the lower bollinger band,
and sell when the price is above the upper bollinger band. It will also use the fast and slow exponential moving averages to determine
when to buy and sell. It will buy when the fast EMA is above the slow EMA, and sell when the fast EMA is below the slow EMA.
"""

###################
# Configuration
###################

# Set to True to run the strategy live, False to backtest
IS_LIVE = os.environ.get("IS_LIVE")
# Set this to False if you want to trade with real money, or True if you want to paper trade
IS_PAPER_TRADING = os.environ.get("ALPACA_IS_PAPER")
# The date and time to start backtesting from
BACKTESTING_START = datetime(2019, 1, 1)
# The date and time to end backtesting
BACKTESTING_END = datetime(2023, 12, 30)
# The asset to use as the quote asset
QUOTE_ASSET = Asset(symbol="USD", asset_type="forex")
# The trading fee to use for backtesting
TRADING_FEE = TradingFee(percent_fee=0.001)  # Assuming 0.1% fee per trade


class Crypto_BBands_v2(Strategy):
    parameters = {
        "asset": Asset("BTC", asset_type="crypto"),  # The asset to trade
        "secondary_asset": Asset(
            "ETH", asset_type="crypto"
        ),  # The secondary asset to trade
        "bbands_length_days": 20,  # Number of days to use for the bollinger bands
        "fixed_income_symbol": "USFR",  # The fixed income ETF that we will be using when we are out of the market
        "slow_ema_length_days": 50,  # The length of the slow EMA
        "fast_ema_length_days": 20,  # The length of the fast EMA
        "days_length_supertrend": 5,  # The number of days to use for the super trend
    }

    def initialize(self):
        # Run the strategy every 1 day
        self.sleeptime = "1D"

        # Set supertrend counter to 0
        self.supertrend_counter = 0

    def on_trading_iteration(self):
        asset = self.parameters["asset"]
        secondary_asset = self.parameters["secondary_asset"]
        bbands_length_days = self.parameters["bbands_length_days"]
        fixed_income_symbol = self.parameters["fixed_income_symbol"]
        slow_ema_length_days = self.parameters["slow_ema_length_days"]
        fast_ema_length_days = self.parameters["fast_ema_length_days"]
        days_length_supertrend = self.parameters["days_length_supertrend"]

        # Calculate the number of days we should get historical prices for
        days_length = max(
            bbands_length_days, slow_ema_length_days, fast_ema_length_days
        )

        # Get the historical prices
        minute_count = (
            60 * 24 * days_length
        )  # The number of minutes to use for the bollinger bands
        historical_prices = self.get_historical_prices(
            asset, minute_count, timestep="minute"
        )
        df = historical_prices.df

        current_price = self.get_last_price(asset)

        # Calculate the bollinger bands
        bbands_length_minutes = (
            60 * 24 * bbands_length_days
        )  # The number of minutes to use for the bollinger bands
        bbands = df.ta.bbands(length=bbands_length_minutes, append=True)

        # Find the columns that has BBU in it
        bbu_columns = [col for col in bbands.columns if "BBU" in col]

        # Find the columns that has BBL in it
        bbl_columns = [col for col in bbands.columns if "BBL" in col]

        # Add the bollinger bands to the dataframe
        df["BBANDS_UPPER"] = bbands[bbu_columns[0]]
        df["BBANDS_LOWER"] = bbands[bbl_columns[0]]

        current_upper = df["BBANDS_UPPER"].iloc[-1]
        current_lower = df["BBANDS_LOWER"].iloc[-1]

        # Calculate the EMAs
        slow_ema_length_minutes = (
            60 * 24 * slow_ema_length_days
        )  # The number of minutes to use for the slow EMA
        df["EMA_SLOW"] = df["close"].ewm(span=slow_ema_length_minutes).mean()
        fast_ema_length_minutes = (
            60 * 24 * fast_ema_length_days
        )  # The number of minutes to use for the fast EMA
        df["EMA_FAST"] = df["close"].ewm(span=fast_ema_length_minutes).mean()

        current_slow_ema = df["EMA_SLOW"].iloc[-1]
        current_fast_ema = df["EMA_FAST"].iloc[-1]

        # Add lines for the current price and the current bollinger bands
        self.add_line("current_price", current_price)
        self.add_line("current_upper", current_upper)
        self.add_line("current_lower", current_lower)
        self.add_line("current_slow_ema", current_slow_ema)
        self.add_line("current_fast_ema", current_fast_ema)

        # Check if we are in super trend mode
        if current_fast_ema > current_slow_ema:
            # We are in super trend mode, so increment the counter
            self.supertrend_counter += 1
        else:
            # We are not in super trend mode, so reset the counter
            self.supertrend_counter = 0

        # If we are in super trend mode for more than days_length_supertrend, then we should buy
        if self.supertrend_counter > days_length_supertrend:
            self.log_message(
                f"We have been in super trend mode for {self.supertrend_counter} days, so we should buy"
            )

            # Buy the primary asset
            self.buy_asset(asset, fixed_income_symbol, 0.45)

            # Buy the secondary asset
            self.buy_asset(secondary_asset, fixed_income_symbol, 0.45)

            return

        # If it's the first time we're running the strategy, we should buy
        if self.first_iteration:
            self.log_message(
                f"Buying {asset.symbol} because it's the first time we're running the strategy"
            )

            # Buy the asset
            self.buy_asset(asset, fixed_income_symbol, 0.9)

        # Check if we should buy
        elif current_price < current_lower:
            self.log_message(
                f"Current price is {current_price}, which is below the lower bollinger band of {current_lower}, so we should buy"
            )

            # Buy the asset
            self.buy_asset(asset, fixed_income_symbol, 0.9)

        # Check if we should sell
        elif current_price > current_upper:
            self.log_message(
                f"Current price is {current_price}, which is above the upper bollinger band of {current_upper}, so we should sell (or just stay in cash for now)"
            )

            # Sell the asset
            self.sell_asset(asset, fixed_income_symbol)

        else:
            self.log_message(
                f"Current price is {current_price}, which is between the bollinger bands of {current_lower} and {current_upper}, so we should do nothing"
            )

    def buy_asset(self, asset, fixed_income_symbol, pct_portfolio_to_use):
        # Check first if we already have a position in the asset
        current_position = self.get_position(asset)

        self.log_message(f"Considering to buy {asset.symbol}")

        if current_position is not None:
            self.log_message(
                "We already have a position in the asset, so we should not buy"
            )
            return

        self.log_message("We do not have a position in the asset, so we should buy")

        # First, sell all of our fixed income ETF
        # Get the position for the fixed income ETF
        fixed_income_asset = Asset(fixed_income_symbol, asset_type="stock")
        fixed_income_position = self.get_position(fixed_income_asset)

        # Sell all of the fixed income ETF
        if fixed_income_position is not None:
            order = self.create_order(
                fixed_income_asset, fixed_income_position.quantity, "sell"
            )
            self.submit_order(order)

            # Sleep for 5 seconds to make sure the sell orders go through first before buying
            self.sleep(5)

        # Calculate how many shares we can buy (use all of our cash)
        cash_to_buy = self.get_portfolio_value() * pct_portfolio_to_use
        current_price = self.get_last_price(asset)
        shares_to_buy = cash_to_buy / current_price

        if shares_to_buy > 0:
            order = self.create_order(asset, shares_to_buy, "buy")
            self.submit_orders([order])

            # Add markers to the chart
            self.add_marker(
                "buy", symbol="triangle-up", value=current_price, color="green"
            )

    def sell_asset(self, asset, fixed_income_symbol):
        current_price = self.get_last_price(asset)

        # Check first if we already have a position in the asset
        current_position = self.get_position(asset)

        # Only sell if we have a position
        if current_position is not None:
            self.log_message("We have a position in the asset, so we should sell")
            self.sell_all()

            # Add markers to the chart
            self.add_marker(
                "sell", symbol="triangle-down", value=current_price, color="red"
            )

            # Sleep for 5 seconds to make sure the sell orders go through first before buying
            self.sleep(5)

            # Buy the fixed income ETF

            # Calculate how many shares we can buy (use all of our cash)
            cash_to_buy = self.get_portfolio_value()
            fixed_income_asset = Asset(symbol=fixed_income_symbol, asset_type="stock")
            fixed_income_price = self.get_last_price(fixed_income_asset)
            fixed_income_quantity = cash_to_buy // fixed_income_price

            if fixed_income_quantity > 0:
                order = self.create_order(
                    fixed_income_asset, fixed_income_quantity, "buy"
                )
                self.submit_order(order)


###################
# Run Strategy
###################

if __name__ == "__main__":
    # Convert the string to a boolean.
    # This will be True if the string is "True", and False otherwise.
    is_live = IS_LIVE.lower() != "false"

    if is_live:
        ############################################
        # Run the strategy live
        ############################################
        from credentials import ALPACA_CONFIG
        from lumibot.brokers import Alpaca

        trader = Trader()

        broker = Alpaca(ALPACA_CONFIG)

        strategy = Crypto_BBands_v2(broker=broker)
        trader.add_strategy(strategy)
        trader.run_all()

    else:
        ############################################
        # Backtest the strategy
        ############################################

        # Polygon API key
        POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")

        Crypto_BBands_v2.backtest(
            PolygonDataBacktesting,
            BACKTESTING_START,
            BACKTESTING_END,
            benchmark_asset=Asset(symbol="BTC", asset_type="crypto"),
            quote_asset=QUOTE_ASSET,
            buy_trading_fees=[TRADING_FEE],
            sell_trading_fees=[TRADING_FEE],
            polygon_api_key=POLYGON_API_KEY,
            polygon_has_paid_subscription=False,
        )
