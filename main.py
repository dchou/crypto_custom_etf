import math
from datetime import datetime

from dotenv import load_dotenv
from lumibot.entities import Asset, TradingFee
from lumibot.strategies.strategy import Strategy
from lumibot.traders import Trader

# load .env file (if one exists)
load_dotenv()

"""
Strategy Description

This strategy will rebalance a portfolio of crypto assets every X days. The portfolio is defined in the parameters
section of the strategy. The portfolio is a list of assets, each with a symbol, a weight, and a quote asset. The
quote asset is the asset that the symbol is quoted in. For example, if you want to trade BTC/USDT, then the quote
asset is USDT. If you want to trade BTC/USD, then the quote asset is USD. The quote asset is used to calculate
the value of the portfolio. The weight is the percentage of the portfolio that the asset should take up. For example,
if you have 3 assets in your portfolio, each with a weight of 0.33, then each asset will take up 33% of the portfolio.

"""


class CustomETF(Strategy):
    # =====Overloading lifecycle methods=============

    parameters = {
        "portfolio": [
            {
                "symbol": Asset(symbol="BTC", asset_type="crypto"),
                # "quote": Asset(symbol="USDT", asset_type="crypto"),  # Use for Kucoin
                "quote": Asset(symbol="USD", asset_type="forex"),  # For Alpaca/Backtest
                "weight": 0.32,
            },
            {
                "symbol": Asset(symbol="ETH", asset_type="crypto"),
                # "quote": Asset(symbol="USDT", asset_type="crypto"),  # Use for Kucoin
                "quote": Asset(symbol="USD", asset_type="forex"),  # For Alpaca/Backtest
                "weight": 0.32,
            },
            {
                "symbol": Asset(symbol="LTC", asset_type="crypto"),
                # "quote": Asset(symbol="USDT", asset_type="crypto"),  # Use for Kucoin
                "quote": Asset(symbol="USD", asset_type="forex"),  # For Alpaca/Backtest
                "weight": 0.32,
            },
        ],
        "rebalance_period": 10,
    }

    def initialize(self):
        self.sleeptime = "1D"
        self.set_market("24/7")

        # Setting the counter
        self.counter = None

    def on_trading_iteration(self):
        # If the target number of minutes (period) has passed, rebalance the portfolio
        if self.counter == self.parameters["rebalance_period"] or self.counter is None:
            self.counter = 0
            self.rebalance_portfolio()
            self.log_message(
                f"Next portfolio rebalancing will be in {self.parameters['rebalance_period']} cycles"
            )
        else:
            self.log_message(
                "Waiting for next rebalance, counter is {self.counter} but should be {self.parameters['rebalance_period']} to rebalance"
            )

        self.counter += 1

    # =============Helper methods===================

    def rebalance_portfolio(self):
        """Rebalance the portfolio and create orders"""
        orders = []
        for asset in self.parameters["portfolio"]:
            # Get all of our variables from portfolio
            asset_to_trade = asset.get("symbol")
            weight = asset.get("weight")
            quote = asset.get("quote")
            symbol = asset_to_trade.symbol

            last_price = self.get_last_price(asset_to_trade, quote=quote)

            if last_price is None:
                self.log_message(
                    f"Couldn't get a price for {symbol} self.get_last_price() returned None"
                )
                continue

            self.log_message(
                f"Last price for {symbol} is {last_price:,f}, and our weight is {weight}. Current portfolio value is {self.portfolio_value}"
            )

            # Get how many shares we already own
            # (including orders that haven't been executed yet)
            quantity = self.get_asset_potential_total(asset_to_trade)

            # Calculate how many shares we need to buy or sell
            shares_value = self.portfolio_value * weight
            new_quantity = shares_value / last_price

            quantity_difference = new_quantity - quantity
            self.log_message(
                f"Currently own {quantity} shares of {symbol} but need {new_quantity}, so the difference is {quantity_difference}"
            )

            # If quantity is positive then buy, if it's negative then sell
            side = ""
            if quantity_difference > 0:
                side = "buy"
            elif quantity_difference < 0:
                side = "sell"

            # Execute the
            # order if necessary
            if side:
                qty = abs(quantity_difference)

                # Trim to 2 decimal places because the API only accepts
                # 2 decimal places for some assets. This could be done better
                # on an asset by asset basis. e.g. for BTC, we want to use 4
                # decimal places at Alpaca, or a 0.0001 increment. See other coins
                # at Alpaca here: https://alpaca.markets/docs/trading/crypto-trading/
                qty_trimmed = math.floor(qty * 100) / 100

                if qty_trimmed > 0:
                    order = self.create_order(
                        asset_to_trade,
                        qty_trimmed,
                        side,
                        quote=quote,
                    )
                    orders.append(order)

        if len(orders) == 0:
            self.log_message("No orders to execute")

        # Execute sell orders first so that we have the cash to buy the new shares
        for order in orders:
            if order.side == "sell":
                self.submit_order(order)

        # Sleep for 5 seconds to make sure the sell orders are filled
        self.sleep(5)

        # Execute buy orders
        for order in orders:
            if order.side == "buy":
                self.submit_order(order)


###################
# Run Strategy
###################

if __name__ == "__main__":
    # Set to True to run the strategy live, or False to backtest
    is_live = False

    if is_live:
        ############################################
        # Run the strategy live
        ############################################
        from lumibot.brokers import Alpaca

        from credentials import ALPACA_CONFIG

        trader = Trader()

        broker = Alpaca(ALPACA_CONFIG)

        strategy = CustomETF(broker=broker)
        trader.add_strategy(strategy)
        trader.run_all()

    else:
        ####
        # Backtest the strategy
        ####
        from lumibot.backtesting import PolygonDataBacktesting

        from credentials import POLYGON_CONFIG

        # Backtest this strategy
        backtesting_start = datetime(2020, 1, 1)
        backtesting_end = datetime.now()

        # 0.1% fee, loosely based on Kucoin (might actually be lower bc we're trading a lot)
        # https://www.kucoin.com/vip/level
        trading_fee = TradingFee(percent_fee=0.001)
        quote_asset = Asset(symbol="USD", asset_type="forex")

        CustomETF.backtest(
            PolygonDataBacktesting,
            backtesting_start,
            backtesting_end,
            benchmark_asset=Asset(symbol="BTC", asset_type="crypto"),
            quote_asset=quote_asset,
            buy_trading_fees=[trading_fee],
            sell_trading_fees=[trading_fee],
            polygon_api_key=POLYGON_CONFIG["API_KEY"],
            polygon_has_paid_subscription=POLYGON_CONFIG["IS_PAID_SUBSCRIPTION"],
        )
