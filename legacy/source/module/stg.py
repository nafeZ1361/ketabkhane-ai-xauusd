from .mt5 import *
from .indicators import *

def supertrend_stg(symbol , tf, atr_period=10, multiplier=3.0 , candle_type = 'ha' ,lot = 0.01 , rr = 2 , comment = 'hashem'):
    trend = supertrend(symbol , tf, atr_period, multiplier , candle_type)
    signal = Trend_change_signal(trend['position'])
    price = mt5.symbol_info_tick(symbol)

    if signal == 'buy' :
        sl = trend['value'][-1]
        tp = price.ask + ((price.ask - sl )* rr)
        create_order(symbol , lot , buy , sl , tp , comment)

    if signal == 'sell' :
        sl = trend['value'][-1]
        tp = price.bid - ((sl - price.bid)* rr)
        create_order(symbol , lot , sell , sl , tp , comment)