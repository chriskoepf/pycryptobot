from datetime import date, datetime, timedelta
from models.AppState import AppState
from models.PyCryptoBot import PyCryptoBot
from models.PyCryptoBot import truncate as _truncate
from models.helper.LogHelper import Logger
from models.TradingAccount import TradingAccount
from models.exchange.Granularity import Granularity

class Strategy_CS:
    def __init__(self, app: PyCryptoBot, state: AppState) -> None:
        self.app = app
        self.state = state
        self.use_adjusted_buy_pts = False # default, leave this here and change below
        self.use_adjusted_sell_pts = False # default, leave this here and change below
        self.sell_override_pts = 100 # set default super high so it doesn't work unless a reasonable number is set below
        self.myCS = True

        if self.state.pandas_ta_enabled is False:
            raise ImportError("This Custom Strategy requires pandas_ta, but pandas_ta module is not loaded. Are requirements-advanced.txt modules installed?")

        if self.state.trading_myPta is True:
            from models.Trading_myPta import TechnicalAnalysis
        else:
            from models.Trading_Pta import TechnicalAnalysis
        self.TA = TechnicalAnalysis

    def tradeSignals(self, data, df, current_sim_date, websocket):

        """ 
        #############################################################################################
        If customizing this file it is recommended to make a copy and name it Strategy_myCS.py
        It will be loaded automatically if pandas-ta is enabled in configuration and it will not
        be overwritten by future updates.
        #############################################################################################
        """

        # buy indicators - using non-traditional settings
        # *** currently requires pandas-ta module and optional talib 

        # will output indicator values in log and after a trade in telgram when True
        debug = True

        # create additional DataFrames to analyze for indicators
        # first option is the short_granularity (5m, 15min, 1h, 6h, 1d, etc.)
        # granularity abbreviations can be found in ./models/exchange/Granularity.py
        # next option is websocket if being used, if omitting and enabled websockets later, error will occur
        # self.df_1d = self.addDataFrame("1d", websocket).copy()

        # if only wanting to know EMAbull like smartswitch checks fore, there are already built in
        # functions that will add the required dataframes and return results.  Just use:
        # EMA1hBull = self.app.is1hEMA1226Bull(current_sim_date, websocket)
        # EMA6hBull = self.app.is6hEMA1226Bull(current_sim_date, websocket)
        try:
            ''''''
            # 1 hour dataframe and indicators
            # name and add the dataframe
            df_1h = self.app.getAdditionalDf("1h", websocket).copy()
            # set variable to call technical analysis in Trading_Pta (or myPta)
            ta_1h = self.TA(df_1h)
            # add any individual signals/inicators or addAll()
#            ta_1h.addSMA(25, True)
            ta_1h.addSMA(50, True)
            ta_1h.addSMA(200, True)
            ta_1h.addEMA(12, True)
            ta_1h.addEMA(26)
#            ta_1h.addTSI(14,10,5,"ema",True)
#            ta_1h.addVWMACD(12,26,5,True)
#            ta_1h.addVWMA(8,True)
            ta_1h.addOBV("sma",5,True)
           # retrieve the ta results
            df_1h = ta_1h.getDataFrame()
            # name and create last row reference like main dataframe
            data_1h = self.app.getInterval(df_1h)

            # 1 hour dataframe and indicators
            # name and add the dataframe
            df_1d = self.app.getAdditionalDf("1d", websocket).copy()
            # set variable to call technical analysis in Trading_Pta (or myPta)
            ta_1d = self.TA(df_1d)
            # add any individual signals/inicators or addAll()
            ta_1d.addSMA(50, True)
            if len(df_1d) >= 200:
                ta_1d.addSMA(200, True)
                df200 = True
            else:
                df200 = False
            ta_1d.addOBV("sma",5,True)
            ta_1d.addATR_RSRL(14,14,use_wicks=True,add_cross=True)
           # retrieve the ta results
            df_1d = ta_1d.getDataFrame()
            # name and create last row reference like main dataframe
            data_1d = self.app.getInterval(df_1d)

        except Exception as err:
            raise Exception(f"Custom Strategy DF Error: {err}")

        # create some variables to calculate difference between 2 signals
        # these can be used in evaluations below and are not in the dataframe to help keep it cleaner
        # helps make changing/adding easier and we only need diff for last row anyway
        # Usage:  self.calcDiff(firstSignal, secondSignal)
        # a negative value means the first signal is below the second signal
#        rsi_ma_diff = self.calcDiff(data['rsi_atr'][0], data['rsi_atr_ma'][0], True) # RSI and MA
#        tsi_sig_diff_2h = self.calcDiff(data_2h['tsi'][0], data_2h['tsi_signal'][0], True) # TSI and Signal
#        obv_diff = self.calcDiff(data['obv'][0], data['obvsm'][0], True)

        # config settings for default, *** make sure they are still in config.json
#        self.app.trailingsellimmediatepcnt = -0.75

        # crossover/greater than time checks - send 1 of 3 global variables and 2 indicators to check
        # returns same global variable length of time in minutes.  If not greater than, returns None and 0.
        # have to store global variable or it won't be able to check the next pass
        self.app.gtTime1, sma1hCoTime = self.checkGtTime(self.app.gtTime1, data_1h['sma50'][0], data_1h['sma200'][0])
        self.app.gtTime2, ema1hCoTime = self.checkGtTime(self.app.gtTime2, data_1h['ema12'][0], data_1h['ema26'][0])

        EMA1hBull = bool(
            ema1hCoTime > 900
            and data_1h['ema12_pc'][0] > 0
            )

        SMA1hBull = bool(
            sma1hCoTime > 900
            and data_1h['sma50_pc'][0] > 0
        )

        if (data['close'][0] - data['open'][0]) > 0:
            greencandle = True
        else:
            greencandle = False

        # to disable any indicator used in this file, set the buy and sell pts to 0 or comment the whole indicator out
        # the lines for buy and sell pts.
        # ** Be sure to adjust total counts below.

        # if using smartswitch granularity, recommend lowering each pt total by 1 pt due to the EMA Bull being disabled
        self.max_pts = 4
        self.sell_override_pts = 3 # this is used if sell_trigger_override setting is True, if activate, TSL and preventloss will be bypassed
        # total points required to buy
        self.pts_to_buy = 4 # more points requires more signals to activate, less risk
        # total points to trigger immediate buy if trailingbuyimmediatepcnt is configured, else ignored
        self.immed_buy_pts = 4
        if self.calcDiff(data['high'][0],data['close'][0] > 15):
            self.immed_buy_pts = 10
#        immedbuyenabled = False
 
        # reset trailingbuy wait price after this many candles have passed without a buy
#        self.reset_trailing_buy = 12 # 3 candles using 1hr indicators, but 15m candles is 3 * 4 = 12

        # use adjusted buy or sell pts? Set to True or False, default is false if not added
        # adjusting buy, will subtract sell_pts from total buy_pts before signaling a buy
        self.use_adjusted_buy_pts = False
        # adjusting sell, will subtract buy_pts from total sell_pts before signaling a sell
        self.use_adjusted_sell_pts = False

        # total points required to sell
        self.pts_to_sell = 3 # requiring fewer pts results in quicker sell signal
        # total points to trigger immediate sell if trailingsellimmediatepcnt is configured, else ignored
        self.immed_sell_pts = 3

        # Required signals.
        # Specify how many have to be triggered
        # Buys - add self.pts_sig_required_buy += 1 to section for each signal
        self.sig_required_buy = 0
        # Sells - add self.pts_sig_required_sell += 1 to section for each signal
        self.sig_required_sell = 0 # set to 0 for default

        # don't edit these, need to start at 0
        self.buy_pts = 0
        self.sell_pts = 0
        self.pts_sig_required_buy = 0
        self.pts_sig_required_sell = 0
        self.override_pts = 0

        # allowbuy variable can turn buying off based on criteria you specifiy
        # set to True by default, but you can set to False when you wish or reverse it
        if (
            data_1d["obv_pc"][0] > 0
            and data_1d["obv"][0] > data_1d["obvsm"][0]
            and data_1d['halfcandle'][0] > data_1d['sma50'][0]
            and data_1d['halfcandle'][0] > data_1d['sma50'][0]
            and (
                data_1d['candle_xresist_last'][0] == "up"
                or (
                    df200
                    and data_1d['sma50'][0] > data_1d['sma200'][0]
                    and data_1d['sma50_pc'][0] > 0
                )
            )
       ):
            allowbuy = True
        else:
            allowbuy = False

        # market trend
        if ( # bull market, use lower requirements
            EMA1hBull
            and SMA1hBull
        ):
            markettrend = "bull"
        elif ( # if only EMA bull, we are likely only sideways
            EMA1hBull
            or SMA1hBull
        ):
            markettrend = "sideways"
        else:
            markettrend = "bear"

        # use below if wanting to hold some pairs

#        if self.app.getMarket() == "":
#            self.app.manual_trades_only == True

        # For this strategy, we require candle
        # candle above atr resistance line, this checks resistance
        # and adds required pts
#        if (
#            data['candle_xresist'][0] == "up"
#            or df['candle_xresist'].iloc[-2] == "up"
#            or df['candle_xresist'].iloc[-3] == "up"
#        ):
#            self.pts_sig_required_buy += 1

        # TSI
        if (
            data['tsi_pc'][0] > 0
#            and data['tsi'][0] > 0
#            and data['tsi'][0] > data['tsi_signal'][0]
        ):
            self.tsi_action = "buy"
            self.buy_pts += 1

            if (data['tsi'][0] - data['tsi_signal'][0]) > (df['tsi'].iloc[-2] > df['tsi_signal'].iloc[-2]):
                self.override_pts += 1

        elif ( 
            data['tsi_pc'][0] < 0
        ):
            self.tsi_action = "sell"
            self.sell_pts += 1

        else:
            self.tsi_action = "wait"

        # OBV 1h
        if (
            data_1h['obv_pc'][0] > 0
#            and data_1h['obv'][0] > data_1h['obvsm'][0]
        ):
            self.obv_action = "buy"
            self.buy_pts += 1

#            if data['candle_xresist_last'][0] == "up":
#                self.pts_sig_required_buy += 1

            if (data_1h['obv'][0] - data_1h['obvsm'][0]) > (df_1h['obv'].iloc[-2] > df_1h['obvsm'].iloc[-2]):
                self.override_pts += 1

        elif (
            data_1h['obv_pc'][0] < 0
        ):
            # when obv has a sell signal, it is decreasing, don't allow buying
            # and remove required buy pts
#            self.pts_sig_required_buy -= 1

            self.obv_action = "sell"
            self.sell_pts += 1

            # additional sell criteria added when OBV is declining
#            if data['close'][0] < data['tf'][0]:
#                self.sell_pts += 2

        else:
            self.obv_action = "wait"

        # VWMACD
        if (
            data['vwmacd_pc'][0] > 0
            and data['vwmacd_hist'][0] > 0
        ):
            self.vwmacd_action = "buy"
            self.buy_pts += 1

            if (
                data['vwmacd_hist'][0] >= df['vwmacd_hist'].iloc[-2]
                and df['vwmacd_hist'].iloc[-2] >= df['vwmacd_hist'].iloc[-3]
            ):
                self.override_pts += 1

        elif (
            data['vwmacd_pc'][0] < 0
        ):
            self.vwmacd_action = "sell"
            self.sell_pts += 1

        else:
            self.vwmacd_action = "wait"

        # MACD
        if (
            data['macd_pc'][0] > 0
            and (
                (
                    data['macd'][0] > data['signal'][0]
                    and df['macd'].iloc[-2] < 0
                    and data['macd'][0] > 0
                ) or (
                    data['macd'][0] > 0
                    and df['macd'].iloc[-2] < df['signal'].iloc[-2]
                    and data['macd'][0] > data['signal'][0]
                )
                
            )
        ):
            self.macd_action = "buy"
            self.buy_pts += 1

        elif (
            data['macd_pc'][0] < 0
        ):
            self.macd_action = "sell"
            self.sell_pts += 1

        else:
            self.macd_action = "wait"

        # adjust sell override if price is below VWMA
#        if data['halfcandle'][0] < data['vwma8'][0]:
#            self.override_pts -= 1
        # if OBV  is below it's SMA, also remove override points
        if data_1h['obv_pc'][0] < 0 and data_1h['obv'][0] < data_1h['obvsm'][0]:
            self.override_pts -= 1
        if data['obv_pc'][0] < 0 and data['obv'][0] < data['obvsm'][0]:
            self.override_pts -= 1
        # if VWMACD has already crossed downward, remove override pts
        if data['vwmacd_pc'][0] < 0 and data['vwmacd_hist'][0] < 0:
            self.override_pts -= 1


        # reset buy pts based on allow buy
        if allowbuy is False:
            self.buy_pts = 0
            self.pts_sig_required_buy = 0

        # adjusted buy pts - subtract any sell pts from buy pts
        if self.use_adjusted_buy_pts is True:
            self.buy_pts = self.buy_pts - self.sell_pts

        # adjusted sell pts - subtract any buy pts from sell pts
        if self.use_adjusted_sell_pts is True:
            self.sell_pts = self.sell_pts - self.buy_pts

        if (
            debug is True
            # use some checks to NOT fill the log with all this data.  Only at candle close
            # and when there currently is a buy or sell signal.
            and (self.state.closed_candle_row == -1
                or (self.buy_pts >= self.pts_to_buy and self.state.last_action != "BUY")
                or (self.sell_pts >= self.pts_to_sell and self.state.last_action not in ["", "SELL"])
            )
        ):
            # some pairs don't have 200 days, so we can't display sma200 at 1d
            if df200:
                sma200 = round(data_1d['sma200'][0],2)
            else:
                sma200 = "Short DF"

            indicatorvalues = (
                # Strategy ver 6.3.1 - 1d OBV and ATR_RSRL required to buy, 15m granularity with 1h OBV, TSI, MACD and VWMACD
                "\n"
                f"CrazyC's Strategy v6.3.1\n"
                f"~ Mkt: {self.app.getMarket()} Trd: {markettrend} ~\n"
                # Actions
                f"Allow Buy: {allowbuy} "
                "\n"
                f"BuyPts: {self.buy_pts}/{self.pts_to_buy} Req: {self.pts_sig_required_buy}/{self.sig_required_buy}"
                f" SellPts: {self.sell_pts}/{self.pts_to_sell} Req: {self.pts_sig_required_sell}/{self.sig_required_sell}"
                "\n"
                #f"SMA Action: {sma_action}
                f"Actions: OBV {self.obv_action}"
#                f" VWMA - {self.vwma_action}"
#                "\n"
                f"/TSI {self.tsi_action}"
                f"/VWMACD {self.vwmacd_action}"
                f"/MACD {self.macd_action}"
                "\n"
                # Open/High/Low/Close
#                f"O: {data['open'][0]} H: {data['high'][0]}"
#                f" L: {data['low'][0]} C: {data['close'][0]}"
#                "\n"
#                f"PVL Enb: {self.app.preventloss}" # Immediate Buy Enabled: {immedbuyenabled}"
#                "\n"
                f"Half Cdl: {round(data['halfcandle'][0],2)}"
                f" Cdl X: {data['candle_xresist'][0]} Prv X: {df['candle_xresist'].iloc[-2]}"
                f" Last Cdl X: {data['candle_xresist_last'][0]}"
                "\n"
                # Previous Open/High/Low/Close
#                f"Prv O: {df['open'].iloc[-2]} H: {df['high'].iloc[-2]}"
#                f" L: {df['low'].iloc[-2]} C: {df['close'].iloc[-2]}"
#                "\n"
                # SMA
                f"SMA50 1d: {round(data_1d['sma50'][0],2)} SMA200 1d: {sma200}"
#                f"VWMA: {round(data['vwma8'][0],2)} PC: {round(data['vwma8_pc'][0],2)}"
#                f" vwma8 1h: {round(data_1h['vwma8'][0],2)} PC: {round(data_1h['vwma8_pc'][0],2)}"
                "\n"
                # VWMACD
                f"VWMACD: {round(data['vwmacd'][0],4)} PC: {round(data['vwmacd_pc'][0],2)}"
                f" Sig: {round(data['vwmacd_sig'][0],4)} Hist: {round(data['vwmacd_hist'][0],4)}"
                "\n"
                # MACD
                f"MACD: {round(data['macd'][0],4)} PC: {round(data['macd_pc'][0],2)}"
                f" Sig: {round(data['signal'][0],4)}"
                "\n"
                # OBV
                f"OBV 1h: {round(data_1h['obv'][0],2)} MA: {round(data_1h['obvsm'][0],2)}"
                f" PC: {round(data_1h['obv_pc'][0],2)}"
                "\n"
                f"OBV 1d: {round(data_1d['obv'][0],2)} MA: {round(data_1d['obvsm'][0],2)}"
                f" PC: {round(data_1d['obv_pc'][0],2)}"
                "\n"
                # TSI
                f"TSI: {_truncate(data['tsi'][0], 2)} PC: {data['tsi_pc'][0]}"
                f" TSI Sig: {_truncate(data['tsi_signal'][0], 2)}"
            )
            Logger.info(indicatorvalues)
        else:
            indicatorvalues = ""

        return indicatorvalues

    def buySignal(self) -> bool:

        # non-Traditional buy signal criteria
        # *** currently requires pandas-ta module and optional talib 

        if (
            self.buy_pts >= self.pts_to_buy
            and self.pts_sig_required_buy >= self.sig_required_buy
        ):
            if (
                self.app.getTrailingBuyImmediatePcnt() is not None
                and self.buy_pts >= self.immed_buy_pts
            ):
                self.state.trailing_buy_immediate = True
            else:
                self.state.trailing_buy_immediate = False

            self.app.buySgnlTime, self.app.buySgnlLength = self.checkTimePassed(self.app.buySgnlTime)
            return True
        else:
            self.app.buySgnlTime = None
            self.app.buySgnlLength = None
            return False

    def sellSignal(self, margin) -> bool:

        # non-Traditional sell signal criteria
        # *** currently requires pandas-ta module and optional talib 
        if (
            self.buy_pts < self.pts_to_buy
            and (
                self.app.sellTriggerOverride() is False
                or self.override_pts < self.sell_override_pts
            ) and margin < 0
            and self.state.candles_since_buy is not None
            and self.state.candles_since_buy <= 1
        ):
            self.app.sellSgnlTime, self.app.sellSgnlLength = self.checkTimePassed(self.app.sellSgnlTime)
            self.logtext = "/nSell signal triggered.  Margin < 0 on first candle after buy./n"
            return True
        elif (
            self.sell_pts >= self.pts_to_sell
            and self.pts_sig_required_sell >= self.sig_required_sell
        ):
            if (
                self.app.getTrailingSellImmediatePcnt() is not None
                and self.sell_pts >= self.immed_sell_pts
            ):
                self.state.trailing_sell_immediate = True
            else:
                self.state.trailing_sell_immediate = False

            self.app.sellSgnlTime, self.app.sellSgnlLength = self.checkTimePassed(self.app.sellSgnlTime)
            self.logtext = ""
            return True
        else:
            self.app.sellSgnlTime = None
            self.app.sellSgnlLength = None
            self.logtext = ""
            return False

    def calcDiff(self, first, second, subtractonly: bool = False) -> None:

        # used to calculate the difference between to values as a percentage
        # negative result means first value is below second value
        if abs(first) == 0:
            return 0
        if subtractonly:
            return (first - second)
        else:
            return (round((first - second) / abs(first) * 100, 2))

    def checkGtTime(self, coTime, first, second): # -> bool:

        # used to calculate how long the crossover has been in place
        # currently variables in place for SMA crossovers only
        # self.app.sma5gtsma10time, self.app.sma10gtsma50time, self.app.sma50gtsma100time

        if first > second:
            if coTime is None:
                return (datetime.now().time(),0)
            else:
                length = (datetime.combine(date.min,datetime.now().time()) - datetime.combine(date.min, coTime))
                return (coTime,length.seconds)
        else:
            return (None,0)


    def setCoTime(self, first, second, coTime):
        if first > second:
            if coTime is None:
                return datetime.now().time()
            else:
                return coTime
        else:
            return None

    def checkTimePassed(self, time): # -> bool:

        # used to calculate how long the crossover has been in place
        # currently variables in place for SMA crossovers only
        # self.app.sma5gtsma10time, self.app.sma10gtsma50time, self.app.sma50gtsma100time

        if time is None:
            return (datetime.now().time(),0)
        else:
            length = (datetime.combine(date.min,datetime.now().time()) - datetime.combine(date.min, time))
            return (time,length.seconds)

    '''
    def preventLoss(self,margin):

        # preventloss - attempt selling before margin drops below 0%
        if self.app.preventLoss():
            if margin > self.state.tsl_trigger:
                self.app.preventloss = False
            elif margin > self.app.preventLossTrigger():
                self.state.prevent_loss = False
                self.app.pvlTime = None
            else:
                self.state.prevent_loss = True
                self.app.pvlTime, length = self.checkPVLTime(self.app.pvlTime)
    #            self.app.notifyTelegram(f"{self.app.getMarket()} - Margin: {margin}, PVL check: {length} seconds")

            if self.state.prevent_loss is True:
#                if length > 14400 and margin < 0:
#                    pvl = True
#                elif length > 7200 and margin < -0.5:
#                    pvl = True
#                elif length > 3600 and margin < -1:
#                    pvl = True
                if length > 1800 and margin < -2.5:
                    pvl = True
                elif length > 300 and margin < -5:
                    pvl = True
                elif length > 120 and margin < -8:
                    pvl = True
                else:
                    pvl = False
        #            Logger.warning(f"{self.app.getMarket()} - has not reached prevent loss trigger of {self.app.preventLossTrigger()}%.  Watch margin ({self.app.preventLossMargin()}%) to prevent loss.")

                if pvl is True and self.state.action != "BUY":
                    Logger.warning(f"{self.app.getMarket()} - Prevent loss sell - Margin: {margin} PVL Timer: {_truncate(length/60,1)}")
                    self.app.notifyTelegram(f"{self.app.getMarket()} - Prevent loss sell - Margin: {margin} PVL Timer: {_truncate(length/60,1)} mins")
                    return True
        else:
            return False

    def sellTriggers(self,margin):

        # if ALL CUSTOM signals are still buy and strength is strong don't trigger a sell yet
        if (
            self.app.sellTriggerOverride() is True
            and self.CS.buy_pts >= self.CS.sell_override_pts
        ):
            return False
        
        # Prevent Loss
        if self.preventLoss(margin):
            return True
    '''