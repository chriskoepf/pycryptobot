CrazyC's custom PCB branch

* Current custom strategy is using Strategy_myCS.py and Trading_myPta.py as included with this branch.  The 2 original, default files Strategy_CS.py and Trading_Pta.py have not been updated since last version with Custom Strategies enabled before Michael's new v7 code.

# Files differing from main code base

# models/exchange/kucoin/api.py
- Kucoin api file modified to disable websockets for getting historical data temporarily until adding new code for the websocket connection.  Historical data is pulled via standard api call.
- Ticker weboscket feed was modified slightly from main code base to process ticker correctly and uses current date of utc-now for time stamp
- added a 2hr and 4hr granularity option for KuCoin.

# models/exchange/coinbasepro/api.py
- edited in the same way as the Kucoin file above except for 2 and 4 hour granularity as Coinbase doesn't support them.
- changed coinbase api url when Coinbase changed from pro. to exchange.

# models/exchange/Granularity.py
- added a 2hr and 4hr granularity option.  May not work on all exchanges, currently only added to KuCoin api file.

# models/AppState.py
- added additional global variables for use in custom strategies - ultimately need to add a new file for these.  If the file exists, import it so custom variables can be added at will
    These are "state." variables
    - time_until_close used for check time until candle close with api calls and can be used in strategy to assure buy/sell signal has been in place more than a few seconds
    - candles_since_buy is used to check margins and/or losses.  Presently if margin is negative by the end of the first candle after buy AND there isn't a buy signal or an override for sell signal (optional), sell off because it shouldn't be losing that fast.

# models/BotConfig.py
- added additional global variables for use in custom strategies - ultimately need to add a new file for these.  If the file exists, import it so custom variables can be added at will
    These are "app." variables

    - gtTime(1 through 5) - used when wanting to check the amount of time one signal is above the other.  There are functions in Strategy_myCS.py for this purpose.
    - pvlTime - was used for custom prevent loss code to use time based prevent loss checks.
    - buySgnlLength & buySgnlTime are used in custom trailing buy code to check how long a buy signal has been in place.  This prevents buy signals from occurring just before candle close or initiating an immediate buy signal when the conditon happens for just a split second and then changes again which would make it a bad buy.
    The setting is currently hard coded in the Trailing Buy code in Strategy.py and is set for 5 mins for both standard and immediate buys.
    - sellSgnlLength & sellSgnlTime are the same as the vars for buying, but used with trailing sell the same way.
    As with buys, the settings in Trailing Sell are hard code in Strategy.py.  For selling, standard sells are set for 3 mins and immediate sells don't have a time check currently.

# models/PyCryptoBot.py
- added a function for updating the last row of TradingData DF or additional DF's because it's called in multiple places and previously had duplicated code.
- revised additional DF code to use the update last row code and only pull 1 period if historical data already exists in the main dataframe, rather than pulling all 300 periods every time.

# models/Strategy.py
- added margin variable to isSellSignal and TrailingSell so it can be passed to the custom strategy for checking.
- added a checkPVLTime function to check how long the margin has been below the preventloss trigger and use multiple if statements to check specific margin levels at time increments.
    * Custom Preventloss is not currently enabled as part of current strategy.  There are 2 versions of preventloss code in this file for now.  Original is commented out and the customer code is enabled with the standard preventloss settings in the config file and the time increments and margin levels are hard coded.  If this is something to keep using, should look at adding to custom strategy files.
    * preventloss code at the beginning of isWaitTrigger is commented out so the above custom code works correctly.
- buy and sell signal time checks are added to Trailing buy and Trailing sell as described above.
- as mentioned for AppState, added check for loss on first candle after buy.

# pycryptobot.py
- added comments to the ticker and get historical data section of code near and after line 180.  Customized a little to accomodate updated websocket code that does not use websockets for getting historical data on Coinbase or Kucoin.
- made additional revisions to ticker and historical data section to only update last row of existing TradingData dataframe, rather than pull 300 periods and create new df at candle close.
- commented out code referencing websocket.candles dataframe which was used for historical data as that is all commented out for Coinbase and Kucoin. Not sure how it will work with Binance.  might need to add a check for Binance to enable it if needed.  This is near line 2186.
- revised TradingData
- commented out tons of unnecessary candle indicator/pattern code that is not used for anything other than log entries
- commented out standard strategy code to minimize processing because of custom strategies.  This needs to be optional with config options at some point.
- added code for the candles since buy options mentioned above.
- added code for custom strategy log messages

# custom strategy - myCS and myPta files
- both custom Trading and Strategy files updated to latest vesion of CrazyC's Strategy v6.2.3

