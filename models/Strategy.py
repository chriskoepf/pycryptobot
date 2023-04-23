from datetime import date, datetime
from pandas import DataFrame
from models.PyCryptoBot import PyCryptoBot
from models.PyCryptoBot import truncate as _truncate
from models.AppState import AppState
from models.helper.LogHelper import Logger
from os.path import exists as file_exists
try:
    from models.Strategy_myCS import Strategy_CS as myCS
    strategy_myCS = True
    myCS_error = None
except ImportError as err:
    strategy_myCS = False
    myCS_error = err
if strategy_myCS is False:
    from models.Strategy_CS import Strategy_CS as CS

class Strategy:
    def __init__(
        self,
        app: PyCryptoBot = None,
        state: AppState = AppState,
        df: DataFrame = DataFrame,
        iterations: int = 0,
    ) -> None:
        if not isinstance(df, DataFrame):
            raise TypeError("'df' not a Pandas dataframe")

        if len(df) == 0:
            raise ValueError("'df' is empty")

        self.app = app
        self.state = state
        self._df = df

        if app.enableCustomStrategy():
            if strategy_myCS is False and file_exists("models/Strategy_myCS.py"):
                raise ImportError(f"Custom Strategy Error: {myCS_error}")
            else:
                if strategy_myCS is True:
                    self.CS = myCS(self.app, self.state)
                else:
                    self.CS = CS(self.app, self.state)
                self.CS_ready = True
        else:
            self.CS_ready = False

        if self.app.isSimulation():
            self._df_last = self.app.getInterval(df, iterations)
        else:
            self._df_last = self.app.getInterval(df)

    def isBuySignal(
        self, state, price, now: datetime = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    ) -> bool:
        self.state = state
        # set to true for verbose debugging
        debug = False

        # buy signal exclusion (if disabled, do not buy within 3% of the dataframe close high)
        if (
            self.state.last_action == "SELL"
            and self.app.disableBuyNearHigh() is True
            and (
                price
                > (self._df["close"].max() * (1 - self.app.noBuyNearHighPcnt() / 100))
            )
        ):
            if not self.app.isSimulation() or (
                self.app.isSimulation() and not self.app.simResultOnly()
            ):
                log_text = (
                    str(now)
                    + " | "
                    + self.app.getMarket()
                    + " | "
                    + self.app.printGranularity()
                    + " | Ignoring Buy Signal (price "
                    + str(price)
                    + " within "
                    + str(self.app.noBuyNearHighPcnt())
                    + "% of high "
                    + str(self._df["close"].max())
                    + ")"
                )
                Logger.warning(log_text)

            return False

        ## if last_action was set to "WAIT" due to an API problem, do not buy
        if ( self.state.last_action == "WAIT"):
            log_text = (f"{str(now)} | {self.app.getMarket()} | {self.app.printGranularity()} | last_action is WAIT, do not buy yet")
            Logger.warning(log_text)
            return False

        # initial funds check
        if self.app.enableinsufficientfundslogging and self.app.insufficientfunds:
            Logger.warning(f"{str(now)} | Insufficient funds, ignoring buy signal.")
            return False

        # if Bull Only is set and no goldencross, return False 
        if (
            self.app.disableBullOnly() is False
            and bool(self._df_last["goldencross"].values[0]) is False
        ):
            return False

        # Custom Strategy options
        if self.CS_ready:
            if self.CS.buySignal():
                return True
            else:
                # If Custom Strategy active, don't process standard signals, return False
                return False

        # if standard EMA and MACD are disabled, do not run below tests
        if self.app.disableBuyEMA() and self.app.disableBuyMACD():
            log_text = f"{str(now)} | {self.app.getMarket()} | {self.app.printGranularity()} | EMA, MACD indicators are disabled"
            Logger.warning(log_text)

            return False

        # required technical indicators or candle sticks for buy signal strategy
        required_indicators = [
            "ema12gtema26co",
            "macdgtsignal",
            "obv_pc",
            "eri_buy",
        ]

        for indicator in required_indicators:
            if indicator not in self._df_last:
                raise AttributeError(f"'{indicator}' not in Pandas dataframe")

        # criteria for a buy signal 1
        if (
            (
                bool(self._df_last["ema12gtema26co"].values[0]) is True
                or self.app.disableBuyEMA()
            )
            and (
                bool(self._df_last["macdgtsignal"].values[0]) is True
                or self.app.disableBuyMACD()
            )
            and (
                float(self._df_last["obv_pc"].values[0]) > -5
                or self.app.disableBuyOBV()
            )
            and (
                bool(self._df_last["eri_buy"].values[0]) is True
                or self.app.disableBuyElderRay()
            )
            and self.state.last_action != "BUY"
        ):  # required for all strategies

            if debug:
                Logger.debug("*** Buy Signal ***")
                for indicator in required_indicators:
                    Logger.debug(f"{indicator}: {self._df_last[indicator].values[0]}")
                Logger.debug(f"last_action: {self.state.last_action}")

            return True

        # criteria for buy signal 2 (optionally add additional buy signals)
        elif (
            (
                bool(self._df_last["ema12gtema26co"].values[0]) is True
                or self.app.disableBuyEMA()
            )
            and bool(self._df_last["macdgtsignalco"].values[0]) is True
            and (
                float(self._df_last["obv_pc"].values[0]) > -5
                or self.app.disableBuyOBV()
            )
            and (
                bool(self._df_last["eri_buy"].values[0]) is True
                or self.app.disableBuyElderRay()
            )
            and self.state.last_action != "BUY"
        ):  # required for all strategies

            if debug:
                Logger.debug("*** Buy Signal ***")
                for indicator in required_indicators:
                    Logger.debug(f"{indicator}: {self._df_last[indicator].values[0]}")
                Logger.debug(f"last_action: {self.state.last_action}")

            return True

        return False

    def isSellSignal(self, margin) -> bool:
        # set to true for verbose debugging
        debug = False

        # additional sell signals - add additional functions and calls as necessary
        if self.CS_ready:
            if self.CS.sellSignal(margin):
                return True
            else:
                # If Custom Strategy active, don't process standard signals, return False
                return False

        # if standard EMA and MACD are disabled, do not run below tests
        if self.app.disableBuyEMA() and self.app.disableBuyMACD():
            # if custom trade signals is enabled, don't alert, just return False
            if self.CS_ready is False:
                log_text = f"{str(datetime.now())} | {self.app.getMarket()} | {self.app.printGranularity()} | "
                log_text += f" EMA, MACD indicators are needed for standard signals and they are disabled."
                Logger.warning(log_text)

            return False

        # required technical indicators or candle sticks for standard sell signal strategy
        required_indicators = ["ema12ltema26co", "macdltsignal"]

        for indicator in required_indicators:
            if indicator not in self._df_last:
                raise AttributeError(f"'{indicator}' not in Pandas dataframe")

        # criteria for a sell signal 1
        if (
            bool(self._df_last["ema12ltema26co"].values[0]) is True
            and (
                bool(self._df_last["macdltsignal"].values[0]) is True
                or self.app.disableBuyMACD()
            )
        ):

            if debug:
                Logger.debug("*** Sell Signal ***")
                for indicator in required_indicators:
                    Logger.debug(f"{indicator}: {self._df_last[indicator].values[0]}")
                Logger.debug(f"last_action: {self.state.last_action}")

            return True

        return False

    def checkPVLTime(self, pvlTime): # -> bool:

        # used to calculate how long the crossover has been in place
        # currently variables in place for SMA crossovers only
        # self.app.sma5gtsma10time, self.app.sma10gtsma50time, self.app.sma50gtsma100time

        if pvlTime is None:
            return (datetime.now().time(),0)
        else:
            length = (datetime.combine(date.min,datetime.now().time()) - datetime.combine(date.min, pvlTime))
            return (pvlTime,length.seconds)

    def isSellTrigger(
        self,
        app,
        state,
        price: float = 0.0,
        price_exit: float = 0.0,
        margin: float = 0.0,
        change_pcnt_high: float = 0.0,
        obv_pc: float = 0.0,
        macdltsignal: bool = False,
    ) -> bool:

        self.state = state
        # set to true for verbose debugging
        debug = False

        # if ALL CUSTOM signals are still buy and strength is strong don't trigger a sell yet
        if ( # Custom Strategy loaded
            self.CS_ready
            and self.app.sellTriggerOverride() is True
            and self.CS.override_pts >= self.CS.sell_override_pts
        ):
            return False

# original preventloss code
#                # preventloss - attempt selling before margin drops below 0%
#        if self.app.preventLoss():
#            if self.state.prevent_loss is False and margin > self.app.preventLossTrigger():
#                self.state.prevent_loss = True
#                Logger.warning(f"{self.app.getMarket()} - reached prevent loss trigger of {self.app.preventLossTrigger()}%.  Watch margin ({self.app.preventLossMargin()}%) to prevent loss.")
#            elif (
#                    self.state.prevent_loss is True and margin <= self.app.preventLossMargin()
#                ) or ( # trigger of 0 disables trigger check and only checks margin set point
#                    self.app.preventLossTrigger() == 0 and margin <= self.app.preventLossMargin()
#                ):
#                Logger.warning(f"{self.app.getMarket()} - time to sell before losing funds! Prevent Loss Activated!")
#                self.app.notifyTelegram(f"{self.app.getMarket()} - time to sell before losing funds! Prevent Loss Activated!")
#                return True

# try to add to Custom Strategy Files
# modified preventloss code.  Move to CS files and replace with original code.
        # preventloss - attempt selling before margin drops below 0%
        length = 0
        if self.app.preventLoss():
            if margin > self.state.tsl_trigger:
                self.app.preventloss = False
            elif margin > self.app.preventLossTrigger():
                self.state.prevent_loss = False
                self.app.pvlTime = None
            else:
                self.state.prevent_loss = True
                self.app.pvlTime, length = self.checkPVLTime(self.app.pvlTime)
#                self.app.notifyTelegram(f"{self.app.getMarket()} - Margin: {margin}, PVL check: {length} seconds")

            if self.state.prevent_loss is True:
                if length > 10800 and margin < 0:
                    pvl = True
                elif length > 7200 and margin < -1:
                    pvl = True
#                elif length > 300 and margin < -3:
#                    pvl = True
#                elif length > 3600 and margin < -5:
#                    pvl = True
#                elif length > 1800 and margin < -8:
#                    pvl = True
#                elif length > 900 and margin < 10:
#                    pvl = True
#                elif length > 120 and margin < -8:
#                    pvl = True
                else:
                    pvl = False
        #            Logger.warning(f"{self.app.getMarket()} - has not reached prevent loss trigger of {self.app.preventLossTrigger()}%.  Watch margin ({self.app.preventLossMargin()}%) to prevent loss.")

                if pvl is True and self.state.action != "BUY":
                    Logger.warning(f"{self.app.getMarket()} - Prevent loss sell - Margin: {margin} PVL Timer: {_truncate(length/60,1)}")
                    self.app.notifyTelegram(f"{self.app.getMarket()} - Prevent loss sell - Margin: {margin} PVL Timer: {_truncate(length/60,1)} mins")
                    return True

        # check sellatloss and nosell bounds before continuing
        if not self.app.allowSellAtLoss() and margin <= 0:
            return False
        elif (
            (self.app.nosellminpcnt is not None) and (margin >= self.app.nosellminpcnt)
        ) and (
            (self.app.nosellmaxpcnt is not None) and (margin <= self.app.nosellmaxpcnt)
        ):
            return False

        if debug:
            Logger.debug(f"Trailing Stop Loss Enabled {self.app.trailingStopLoss()}")
            Logger.debug(f"Change Percentage {change_pcnt_high} < Stop Loss Percent {self.state.tsl_pcnt} = {change_pcnt_high < self.state.tsl_pcnt}")
            Logger.debug(f"Margin {margin} > Stop Loss Trigger  {self.state.tsl_trigger} = {margin > self.state.tsl_trigger}")

        if self.state.tsl_pcnt != None:
            # dynamic trailing_stop_loss
            if self.app.dynamicTSL():
                if (
                    self.app.TSLTriggerMultiplier() != None
                    and margin > round(self.state.tsl_trigger * self.app.TSLTriggerMultiplier())
                    and self.state.tsl_max is False
                ):
                    # price increased, so check margin and reset trailingsellpcnt
                    self.state.tsl_triggered = False

                if self.state.tsl_triggered is False:
                    # check margin and set the trailingsellpcnt dynamically if enabled
                    if self.app.TSLTriggerMultiplier() != None and margin > round(self.state.tsl_trigger * self.app.TSLTriggerMultiplier()):
                        self.state.tsl_triggered = True
                        self.state.tsl_trigger = round(self.state.tsl_trigger * self.app.TSLTriggerMultiplier())
                        self.state.tsl_pcnt = float(round(self.state.tsl_pcnt * self.app.TSLMultiplier(), 1))
                        if self.state.tsl_pcnt >= self.app.TSLMaxPcnt(): # has tsl reached it's max setting
                            self.state.tsl_max = True
                    # tsl is triggered if margin is high enough
                    elif margin > self.state.tsl_trigger:
                        self.state.tsl_triggered = True

             # default, fixed trailingstoploss and trigger
            else:
                # loss failsafe sell at trailing_stop_loss
                if margin > self.state.tsl_trigger:
                    self.state.tsl_triggered = True

            if debug:
                debugtext = f"TSL Triggered: {self.state.tsl_triggered} TSL Pcnt: {self.state.tsl_pcnt}% TSL Trigger: {self.state.tsl_trigger}%"
                debugtext += f" TSL Next Trigger: {round(self.state.tsl_trigger * self.app.TSLTriggerMultiplier())}%\n" if self.app.dynamicTSL() else "\n"
                debugtext += f"Change Percentage {change_pcnt_high} < Stop Loss Percent {self.app.trailingStopLoss()} = {change_pcnt_high < self.app.trailingStopLoss()}"
                debugtext += f"Margin {margin} > Stop Loss Trigger  {self.app.trailingStopLossTrigger()} = {margin > self.app.trailingStopLossTrigger()}"
                Logger.debug(debugtext)

                # Telgram debug output
                self.app.notifyTelegram(
                    f"{self.app.getMarket()} ({self.app.printGranularity()})\n{debugtext}"
                )

            if self.state.tsl_triggered is True and change_pcnt_high < self.state.tsl_pcnt:
                log_text = f"! Trailing Stop Loss Triggered (Margin: {_truncate(margin,2)}% Stoploss: {str(self.state.tsl_pcnt)}%)"
                if not self.app.isSimulation() or (
                    self.app.isSimulation() and not self.app.simResultOnly()
                ):
                    Logger.warning(log_text)

                self.app.notifyTelegram(
                    f"{self.app.getMarket()} ({self.app.printGranularity()}) {log_text}"
                )

                return True

        if debug:
            Logger.debug("-- loss failsafe sell at sell_lower_pcnt --")
            Logger.debug(
                f"self.app.disableFailsafeLowerPcnt() is False (actual: {self.app.disableFailsafeLowerPcnt()})"
            )
            Logger.debug(
                f"and self.app.allowSellAtLoss() is True (actual: {self.app.allowSellAtLoss()})"
            )
            Logger.debug(
                f"and self.app.sellLowerPcnt() != None (actual: {self.app.sellLowerPcnt()})"
            )
            Logger.debug(
                f"and margin ({margin}) < self.app.sellLowerPcnt() ({self.app.sellLowerPcnt()})"
            )
            Logger.debug(
                f"(self.app.allowSellAtLoss() is True (actual: {self.app.allowSellAtLoss()}) or margin ({margin}) > 0)"
            )
            Logger.debug("\n")

        # loss failsafe sell at sell_lower_pcnt
        if (
            self.app.disableFailsafeLowerPcnt() is False
            and self.app.allowSellAtLoss()
            and self.app.sellLowerPcnt() != None
            and margin < self.app.sellLowerPcnt()
        ):
            log_text = (
                "! Loss Failsafe Triggered (< " + str(self.app.sellLowerPcnt()) + "%)"
            )
            Logger.warning(log_text)
            self.app.notifyTelegram(
                f"{self.app.getMarket()} ({self.app.printGranularity()}) {log_text}"
            )
            return True

        if debug:
            Logger.debug("\n*** isSellTrigger ***\n")
            Logger.debug("-- ignoring sell signal --")
            Logger.debug(
                f"self.app.nosellminpcnt is None (nosellminpcnt: {self.app.nosellminpcnt})"
            )
            Logger.debug(f"margin >= self.app.nosellminpcnt (margin: {margin})")
            Logger.debug(
                f"margin <= self.app.nosellmaxpcnt (nosellmaxpcnt: {self.app.nosellmaxpcnt})"
            )
            Logger.debug("\n")

        if debug:
            Logger.debug("\n*** isSellTrigger ***\n")
            Logger.debug("-- loss failsafe sell at fibonacci band --")
            Logger.debug(
                f"self.app.disableFailsafeFibonacciLow() is False (actual: {self.app.disableFailsafeFibonacciLow()})"
            )
            Logger.debug(
                f"self.app.allowSellAtLoss() is True (actual: {self.app.allowSellAtLoss()})"
            )
            Logger.debug(
                f"self.app.sellLowerPcnt() is None (actual: {self.app.sellLowerPcnt()})"
            )
            Logger.debug(f"self.state.fib_low {self.state.fib_low} > 0")
            Logger.debug(f"self.state.fib_low {self.state.fib_low} >= {float(price)}")
            Logger.debug(
                f"(self.app.allowSellAtLoss() is True (actual: {self.app.allowSellAtLoss()}) or margin ({margin}) > 0)"
            )
            Logger.debug("\n")

        # loss failsafe sell at fibonacci band
        if (
            self.app.disableFailsafeFibonacciLow() is False
            and self.app.allowSellAtLoss()
            and self.app.sellLowerPcnt() is None
            and self.state.fib_low > 0
            and self.state.fib_low >= float(price)
        ):
            log_text = (
                f"! Loss Failsafe Triggered (Fibonacci Band: {str(self.state.fib_low)})"
            )
            Logger.warning(log_text)
            self.app.notifyTelegram(
                f"{self.app.getMarket()} ({self.app.printGranularity()}) {log_text}"
            )
            return True

        if debug:
            Logger.debug("-- loss failsafe sell at trailing_stop_loss --")
            Logger.debug(
                f"self.app.trailingStopLoss() != None (actual: {self.app.trailingStopLoss()})"
            )
            Logger.debug(
                f"change_pcnt_high ({change_pcnt_high}) < self.app.trailingStopLoss() ({self.app.trailingStopLoss()})"
            )
            Logger.debug(
                f"margin ({margin}) > self.app.trailingStopLossTrigger() ({self.app.trailingStopLossTrigger()})"
            )
            Logger.debug(
                f"(self.app.allowSellAtLoss() is True (actual: {self.app.allowSellAtLoss()}) or margin ({margin}) > 0)"
            )
            Logger.debug("\n")

        if debug:
            Logger.debug("-- profit bank at sell_upper_pcnt --")
            Logger.debug(
                f"self.app.disableProfitbankUpperPcnt() is False (actual: {self.app.disableProfitbankUpperPcnt()})"
            )
            Logger.debug(
                f"and self.app.sellUpperPcnt() != None (actual: {self.app.sellUpperPcnt()})"
            )
            Logger.debug(
                f"and margin ({margin}) > self.app.sellUpperPcnt() ({self.app.sellUpperPcnt()})"
            )
            Logger.debug(
                f"(self.app.allowSellAtLoss() is True (actual: {self.app.allowSellAtLoss()}) or margin ({margin}) > 0)"
            )
            Logger.debug("\n")

        # profit bank at sell_upper_pcnt
        if (
            self.app.disableProfitbankUpperPcnt() is False
            and self.app.sellUpperPcnt() != None
            and margin > self.app.sellUpperPcnt()
        ):
            log_text = f"! Profit Bank Triggered (> {str(self.app.sellUpperPcnt())}%)"
            if not self.app.isSimulation() or (
                self.app.isSimulation() and not self.app.simResultOnly()
            ):
                Logger.warning(log_text)
            self.app.notifyTelegram(
                f"{self.app.getMarket()} ({self.app.printGranularity()}) {log_text}"
            )
            return True

        if debug:
            Logger.debug("-- profit bank when strong reversal detected --")
            Logger.debug(
                f"self.app.sellAtResistance() is True (actual {self.app.sellAtResistance()})"
            )
            Logger.debug(f"and price ({price}) > 0")
            Logger.debug(f"and price ({price}) >= price_exit ({price_exit})")
            Logger.debug(
                f"(self.app.allowSellAtLoss() is True (actual: {self.app.allowSellAtLoss()}) or margin ({margin}) > 0)"
            )
            Logger.debug("\n")

        # profit bank when strong reversal detected
        if (
            self.app.sellAtResistance() is True
            and margin >= 2
            and price > 0
            and price >= price_exit
            and (self.app.allowSellAtLoss() or margin > 0)
        ):
            log_text = "! Profit Bank Triggered (Selling At Resistance)"
            if not self.app.isSimulation() or (
                self.app.isSimulation() and not self.app.simResultOnly()
            ):
                Logger.warning(log_text)
            if not (not self.app.allowSellAtLoss() and margin <= 0):
                self.app.notifyTelegram(
                    f"{self.app.getMarket()} ({self.app.printGranularity()}) {log_text}"
                )
            return True

        return False

    def isWaitTrigger(self, margin: float = 0.0, goldencross: bool = False):
        # set to true for verbose debugging
        debug = False

        # if prevent_loss is enabled and activated, don't WAIT
#        if (self.state.prevent_loss is True and margin <= self.app.preventLossMargin()
#           ) or ( # trigger of 0 disables trigger check and only checks margin set point
#                self.app.preventLossTrigger() == 0 and margin <= self.app.preventLossMargin()
#        ):
#            return False

        if debug and self.state.action != "WAIT":
            Logger.debug("\n*** isWaitTrigger ***\n")

        if debug and self.state.action == "BUY":
            Logger.debug(
                "-- if bear market and bull only return true to abort buy --"
            )
            Logger.debug(f"self.state.action == 'BUY' (actual: {self.state.action})")
            Logger.debug(
                f"and self.app.disableBullOnly() is True (actual: {self.app.disableBullOnly()})"
            )
            Logger.debug(f"and goldencross is False (actual: {goldencross})")
            Logger.debug("\n")

        # if bear market and bull only return true to abort buy
        if (
            self.state.action == "BUY"
            and not self.app.disableBullOnly()
            and not goldencross
        ):
            log_text = "! Ignore Buy Signal (Bear Buy In Bull Only)"
            Logger.warning(log_text)
            return True

        if debug and self.state.action == "SELL":
            Logger.debug("-- configuration specifies to not sell at a loss --")
            Logger.debug(f"self.state.action == 'SELL' (actual: {self.state.action})")
            Logger.debug(
                f"and self.app.allowSellAtLoss() is False (actual: {self.app.allowSellAtLoss()})"
            )
            Logger.debug(f"and margin ({margin}) <= 0")
            Logger.debug("\n")

        # configuration specifies to not sell at a loss
        if (
            self.state.action == "SELL"
            and not self.app.allowSellAtLoss()
            and margin <= 0
        ):
            if not self.app.isSimulation() or (
                self.app.isSimulation() and not self.app.simResultOnly()
            ):
                log_text = "! Ignore Sell Signal (No Sell At Loss)"
                Logger.warning(log_text)
            return True

        if debug and self.state.action == "SELL":
            Logger.debug(
                "-- configuration specifies not to sell within min and max margin percent bounds --"
            )
            Logger.debug(f"self.state.action == 'SELL' (actual: {self.state.action})")
            Logger.debug(
                f"(self.app.nosellminpcnt is not None (actual: {self.app.nosellminpcnt})) and (margin ({margin}) >= self.app.nosellminpcnt ({self.app.nosellminpcnt}))"
            )
            Logger.debug(
                f"(self.app.nosellmaxpcnt is not None (actual: {self.app.nosellmaxpcnt})) and (margin ({margin}) <= self.app.nosellmaxpcnt ({self.app.nosellmaxpcnt}))"
            )
            Logger.debug("\n")

        # configuration specifies not to sell within min and max margin percent bounds
        if (
            self.state.action == "SELL"
            and (
                (self.app.nosellminpcnt is not None)
                and (margin >= self.app.nosellminpcnt)
            )
            and (
                (self.app.nosellmaxpcnt is not None)
                and (margin <= self.app.nosellmaxpcnt)
            )
        ):
            if not self.app.isSimulation() or (
                self.app.isSimulation() and not self.app.simResultOnly()
            ):
                Logger.warning("! Ignore Sell Signal (Within No-Sell Bounds)")
            return True

        return False

    def checkTrailingBuy(self, state, price):

        self.state = state
        # If buy signal, save the price and check if it decreases before buying.
        immediate_action = False
        trailingbuypcnt = self.app.getTrailingBuyPcnt() # get pcnt from config, if not, use 0%
        if self.state.trailing_buy is True and self.state.waiting_buy_price > 0:
            pricechange = float(_truncate((self.state.waiting_buy_price - price) / self.state.waiting_buy_price * -100,2))
        else:
            self.state.waiting_buy_price = price
            pricechange = 0
            self.state.trailing_buy = True

        waitpcnttext = f"** {self.app.getMarket()} ({self.app.printGranularity()}) - "
        if price < self.state.waiting_buy_price:
            self.state.waiting_buy_price = price
            self.state.action = "WAIT"
            trailing_action_logtext = f" - Wait Chg: Dec {str(pricechange)}%"
            waitpcnttext += f"Price decreased - resetting wait price. "
        elif (
            self.app.getTrailingBuyImmediatePcnt() is not None
            and (self.state.trailing_buy_immediate is True
                or self.app.trailingImmediateBuy() is True)
            and pricechange > self.app.getTrailingBuyImmediatePcnt()
# add config option at some point
            and self.app.buySgnlLength >= 180 # added check to see if signal has been in place X seconds
        ): # If price increases by more than trailingbuyimmediatepcnt, do an immediate buy
            self.state.action = "BUY"
            immediate_action = True
            trailing_action_logtext = f" - Immediate Buy - Chg: {str(pricechange)}%/{self.app.getTrailingBuyImmediatePcnt()}%"
            waitpcnttext += f"Ready for immediate buy. {self.state.waiting_buy_price} change of {str(pricechange)}% is above setting of {self.app.getTrailingBuyImmediatePcnt()}%"
            self.app.notifyTelegram(waitpcnttext)
        # added 10% fluctuation to prevent holding another full candle for 0.025%
        elif pricechange < (trailingbuypcnt * 0.9):
            self.state.action = "WAIT"
            trailing_action_logtext = f" - Wait Chg: {str(pricechange)}%"
            trailing_action_logtext += f"/{trailingbuypcnt}%" if trailingbuypcnt > 0 else ""
            waitpcnttext += f"Waiting to buy until price of {self.state.waiting_buy_price} increases {trailingbuypcnt}% (+/- 10%) - change {str(pricechange)}%"
# if continuing to use, add config var for this
        # if standard buy signal has only been in place X minutes or less, don't buy at close
        # immediate buys will still occur based on settings above
        elif self.app.buySgnlLength is None or self.app.buySgnlLength < 300:
            trailing_action_logtext = f" - Wait < 5m"
            self.state.action = "WAIT"
            waitpcnttext += f"Buy signal less than 5 minutes, not safe to buy yet."
        else:
            self.state.action = "BUY"
            trailing_action_logtext = f" - Buy Chg: {str(pricechange)}%/{trailingbuypcnt}%"
            waitpcnttext += f"Ready to buy at close. Price of {self.state.waiting_buy_price}, change of {str(pricechange)}%, is greater than setting of {trailingbuypcnt}%  (+/- 10%)"

        if self.app.isVerbose() and (
            not self.app.isSimulation()
            or (self.app.isSimulation() and not self.app.simResultOnly())
        ):
            Logger.info(waitpcnttext)

        return self.state.action, self.state.trailing_buy, trailing_action_logtext, immediate_action

    def checkTrailingSell(self, state, price, margin):

        debug = False

        self.state = state
        # If sell signal, save the price and check if it increases before selling.
        immediate_action = False
        if self.state.trailing_sell is True and self.state.waiting_sell_price != None:
            pricechange = float(_truncate((self.state.waiting_sell_price - price) / self.state.waiting_sell_price * -100,2))
        else:
            self.state.waiting_sell_price = price
            pricechange = 0
            self.state.trailing_sell = True

        waitpcnttext = f"** {self.app.getMarket()} ({self.app.printGranularity()}) - "
        if price >= self.state.waiting_sell_price:
            self.state.waiting_sell_price = price
            self.state.action = "WAIT"
            trailing_action_logtext = f" - Wait Chg: Inc {str(pricechange)}%"
            waitpcnttext += f"Price increased - resetting wait price."
        # bailout setting.  If price drops x%, sell immediately.
        elif self.app.getTrailingSellBailoutPcnt() is not None and pricechange < self.app.getTrailingSellBailoutPcnt():
            self.state.action = "SELL"
            immediate_action = True
            trailing_action_logtext = f" - Bailout Immediately - Chg: {str(pricechange)}%/{self.app.getTrailingSellBailoutPcnt()}%"
            waitpcnttext += f"Bailout Immediately. Price {self.state.waiting_sell_price}, change of {str(pricechange)}%, is lower than setting of {self.app.getTrailingSellBailoutPcnt()}%"
            self.app.notifyTelegram(waitpcnttext)
        # When all indicators signal strong sell and price decreases more than "self.app.getTrailingSellImmediatePcnt()", immediate sell
        elif ( # This resets after a sell occurs
            self.app.getTrailingSellImmediatePcnt() is not None
            and (self.state.trailing_sell_immediate is True
                or self.app.trailingImmediateSell() is True)
            and pricechange < self.app.getTrailingSellImmediatePcnt()
        ):
            self.state.action = "SELL"
            immediate_action = True
            trailing_action_logtext = f" - Immediate Sell - Chg: {str(pricechange)}%/{self.app.getTrailingSellImmediatePcnt()}%"
            waitpcnttext += f"Sell Immediately. Price {self.state.waiting_sell_price}, change of {str(pricechange)}%, is lower than setting of {self.app.getTrailingSellImmediatePcnt()}%"
            self.app.notifyTelegram(waitpcnttext)
        # added 10% fluctuation to prevent holding another full candle for 0.025%
        elif pricechange > (self.app.getTrailingSellPcnt() * .9): 
            self.state.action = "WAIT"
            if self.app.getTrailingSellPcnt() == 0:
                trailing_action_logtext = f" - Wait Chg: {str(pricechange)}%"
                waitpcnttext += f"Waiting to sell until {self.state.waiting_sell_price} stops increasing - change {str(pricechange)}%"
            else:
                trailing_action_logtext = f" - Wait Chg: {str(pricechange)}%/{self.app.getTrailingSellPcnt()}%"
                waitpcnttext += f"Waiting to sell until price of {self.state.waiting_sell_price} decreases {self.app.getTrailingSellPcnt()}% (+/- 10%) - change {str(pricechange)}%"
# custom sell if margin goes negative on first candle after buy
        elif (
            self.state.candles_since_buy is not None
            and self.state.candles_since_buy <= 1
            and margin < 0
            and self.app.sellSgnlLength is not None
            and self.app.sellSgnlLength >= 180
        ):
            self.state.action = "SELL"
#            immediate_action = True
            trailing_action_logtext = f" Sell - Margin is < 0% on 1st candle after buy."
            waitpcnttext += f"Sell at close, Margin is < 0% on 1st candle after buy."
            #self.app.notifyTelegram(waitpcnttext)
# if continuing to use, add config var for this
        # if standard sell signal has only been in place X minutes or less, don't sell at close
        # immediate sells will still occur based on settings above
        elif self.app.sellSgnlLength is None or self.app.sellSgnlLength < 180:
            self.state.action = "WAIT"
            trailing_action_logtext = f" - Wait < 3m"
            waitpcnttext += f"Sell signal less than 3 minutes, don't sell yet."
        else:
            self.state.action = "SELL"
            trailing_action_logtext = f" - Sell Chg: {str(pricechange)}%/{self.app.getTrailingSellPcnt()}%"
            waitpcnttext += f"Sell at Close. Price of {self.state.waiting_sell_price}, change of {str(pricechange)}%, is lower than setting of {str(self.app.getTrailingSellPcnt())}% (+/- 10%)"
            if self.CS_ready: # Custom Strategy loaded
                trailing_action_logtext += self.CS.logtext 
                waitpcnttext += self.CS.logtext

        if self.app.isVerbose() and (
            not self.app.isSimulation()
            or (self.app.isSimulation() and not self.app.simResultOnly())
        ):
            Logger.info(waitpcnttext)

        if debug:
            Logger.debug(waitpcnttext)
            Logger.debug(f"Trailing Sell Triggered: {self.state.trailing_sell}  Wait Price: {self.state.waiting_sell_price} Current Price: {price} Price Chg: {_truncate(pricechange,2)} Immed Sell Pcnt: -{str(self.app.getTrailingSellImmediatePcnt())}%")

        return self.state.action, self.state.trailing_sell, trailing_action_logtext, immediate_action

    def getAction(self, df_last, state, price, margin, current_sim_date, websocket):
        self.state = state
        # if Custom Strategy requirements are met, run tradeSignals function and report any errors.
        if self.CS_ready is True:
            # use try/except since this is a customizable file
            try:
                # indicatorvalues displays indicators in log and telegram if debug is True in CS.tradeSignals
                indicatorvalues = self.CS.tradeSignals(df_last, self._df, current_sim_date, websocket)
            except Exception as err:
                self.CS_ready = False
                Logger.warning(f"Custom Strategy Error: {err}")
        else: # strategy not enabled or an error occurred.
            indicatorvalues = ""

        if  self.state.last_action != "BUY" and self.isBuySignal(self.state, price, current_sim_date):
            return "BUY", indicatorvalues
        elif self.state.last_action not in ["", "SELL"] and self.isSellSignal(margin):
            return "SELL", indicatorvalues
        else:
            return "WAIT", indicatorvalues
