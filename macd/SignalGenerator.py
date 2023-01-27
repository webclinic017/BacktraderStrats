from os import close
import pandas as pd
import talib

STOCHASTIC_OVERBOUGHT_THRESHOLD = 0.75
STOCHASTIC_OVERSOLD_THRESHOLD = 0.25
STOCHASTIC_K_PERIOD = 14 
STOCHASTIC_MA_PERIOD = 3
RSI_PERIOD = 14
MACD_FAST_PERIOD = 8 
MACD_SLOW_PERIOD = 21 
MACD_SIGNAL_PERIOD = 5 


def macdCN(close, fastperiod, slowperiod, signalperiod):
    macdDIFF, macdDEA, macd = talib.MACDEXT(close, fastperiod=fastperiod, fastmatype=1, slowperiod=slowperiod, slowmatype=1, signalperiod=signalperiod, signalmatype=1)
    macd = macd * 2
    return macdDIFF, macdDEA, macd

def getMACD(close_df: pd.DataFrame):
    macd, macdsignal, macdhist = macdCN(close_df['close'], fastperiod=MACD_FAST_PERIOD, slowperiod=MACD_SLOW_PERIOD, signalperiod=MACD_SIGNAL_PERIOD) 
    close_df['DIFF'] = macd
    close_df['DEA'] = macdsignal
    close_df['HIST'] = macdhist
    return close_df
 

def calSlowKSlowD(close_df: pd.DataFrame):
    current_close = close_df.iloc[-1]
    high = max(close_df['close'][-STOCHASTIC_K_PERIOD:])
    low = min(close_df['close'][-STOCHASTIC_K_PERIOD:])
    slowk, slowd = talib.STOCH(high, low, current_close,
                               fastk_period=STOCHASTIC_K_PERIOD, slowk_period=STOCHASTIC_MA_PERIOD, 
                               slowk_matype=0, slowd_period=STOCHASTIC_MA_PERIOD, slowd_matype=0)
    return slowk, slowd

def isStochasticOverbought(close_df: pd.DataFrame):
    slowk, slowd = calSlowKSlowD(close_df)
    if slowk.iloc[-1] >= STOCHASTIC_OVERBOUGHT_THRESHOLD and slowd.iloc[-1] >= STOCHASTIC_OVERBOUGHT_THRESHOLD:
        return True
    return False

def isStochasticOversold(close_df: pd.DataFrame):
    slowk, slowd = calSlowKSlowD(close_df)
    if slowk.iloc[-1] <= STOCHASTIC_OVERSOLD_THRESHOLD and slowd.iloc[-1] <= STOCHASTIC_OVERSOLD_THRESHOLD:
        return True
    return False

def isRsiUptrend(close_df: pd.DataFrame):
    rsi = talib.RSI(close_df['close'], timeperiod=RSI_PERIOD) 
    if rsi.iloc[-1] > 50:
        return True
    return False

def isRsiDowntrend(close_df: pd.DataFrame):
    rsi = talib.RSI(close_df['close'], timeperiod=RSI_PERIOD) 
    if rsi.iloc[-1] < 50:
        return True
    return False

# need to get macd frame by getMACD first
def isMacdUpMomentum(macd_frame: pd.DataFrame):
    if pd.isna(macd_frame['DIFF']) or pd.isna(macd_frame['DEA']) or pd.isna(macd_frame['HIST']):
        return False
    if macd_frame['DIFF'].iloc[-1] >= 0 and macd_frame['DEA'].iloc[-1] >= 0 and macd_frame['HIST'].iloc[-2] <= 0 and macd_frame['HIST'].iloc[-1] > 0:
        return True
    return False

# need to get macd frame by getMACD first
def isMacdDownMomentum(macd_frame: pd.DataFrame):
    if pd.isna(macd_frame['DIFF']) or pd.isna(macd_frame['DEA']) or pd.isna(macd_frame['HIST']):
        return False
    if macd_frame['HIST'].iloc[-2] > 0 and macd_frame['HIST'].iloc[-1] <= 0:
        return True
    return False