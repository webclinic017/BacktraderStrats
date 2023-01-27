from os import close
import talib
import pandas as pd

def getSMA(close_df, maOnePeriod=50, maTwoPeriod=150, maThreePeriod=200):
    close_df['MA1'] = talib.MA(close_df['close'], timeperiod=maOnePeriod, matype=0)
    close_df['MA2'] = talib.MA(close_df['close'], timeperiod=maTwoPeriod, matype=0)
    close_df['MA3'] = talib.MA(close_df['close'], timeperiod=maThreePeriod, matype=0)


# current price is above between 150-MA & 200-MA
def isAboveTwoMA(current_close, close_df: pd.DataFrame):
    if 'MA2' or 'MA3' not in close_df.columns:
        raise Exception("close dataframe should contains columns MA2 MA3")
    if current_close > close_df['MA2'][-1] and current_close > close_df['MA3'][-1]:
        return True
    return False

# MA2(150 DAYS) above MA3(200 DAYS)
def isLongtermIncreasing(close_df):
    if 'MA2' or 'MA3' not in close_df.columns:
        raise Exception("close dataframe should contains columns MA2 MA3")
    if close_df['MA2'][-1] > close_df['MA3'][-1]:
        return True
    return False

# is 200MA trending up at least one month
def isSlowMATrendingUp(close_df, slope_threshold=0.1, days=30):
    if 'MA3' not in close_df.columns:
        raise Exception("close dataframe should contains columns MA3") 
    if close_df['MA3'].size < 30:
        days = close_df['MA3'].size
    slope = talib.LINEARREG_SLOPE(close_df['MA3'], timeperiod=days)
    if slope[-1] >= slope_threshold:
        return True
    return False

# MA1(50 DAYS) above MA2(150 DAYS) and MA3(200 DAYS)
def isShorttermIncreasing(close_df: pd.DataFrame):
    if 'MA3' not in close_df.columns:
        raise Exception("close dataframe should contains columns MA3") 
    if close_df['MA1'][-1] > close_df['MA2'][-1] and close_df['MA1'][-1]> close_df['MA3'][-1]:
        return True
    return False 

def isAboveMAOne(current_close, close_df):
    if 'MA1' not in close_df.columns: 
        raise Exception("close dataframe should contains columns MA3") 
    if close_df['MA1'] < current_close:
        return True
    return False

def isAboveRecentLow(current_close, close_df, weeks=52, threshold=0.3):
    recent_low = getRecentLow(close_df, weeks)
    if current_close > recent_low * (1 + threshold):
        return True 
    return False

def getRecentLow(close_df, weeks=52):
    days = weeks * 5
    if close_df['close'].size < days:
        days = close_df['close'].size
    return min(close_df['close'][-days:]) 

def getRecentHigh(close_df, weeks=52):
    days = weeks * 5
    if close_df['close'].size < days:
        days = close_df['close'].size
    return max(close_df['close'][-days:])

def isBelowRecentHigh(current_close, close_df, weeks=52, threshold=0.25):
    recent_high = getRecentHigh(close_df, weeks)
    if current_close < recent_high * (1 - threshold):
        return True 
    return False

def checkMMRules(current_close, close_df):
    try:
        # TODO IBD RS Rating Rule
        cond = True
        cond = cond & isAboveTwoMA(current_close, close_df)
        cond = cond & isLongtermIncreasing(close_df) 
        cond = cond & isSlowMATrendingUp(close_df, slope_threshold=0.1, days=30)
        cond = cond & isShorttermIncreasing(close_df)
        cond = cond & isAboveMAOne(current_close, close_df)
        cond = cond & isAboveRecentLow(current_close, close_df, weeks=52, threshold=0.3)
        cond = cond & isBelowRecentHigh(current_close, close_df, weeks=52, threshold=0.25)
        return cond
    except Exception as ex:
        print(ex)