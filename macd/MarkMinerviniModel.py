from os import close
import sys
import talib
import pandas as pd

DEFAULT_MA_ONE_PERIOD = 50
DEFAULT_MA_TWO_PERIOD = 150
DEFAULT_MA_THREE_PERIOD = 200
VALID_CLOSE_THRESHOLD = 2
MMMODEL_PERIOD = 360

def adjustMAPeriod(close_df, maOnePeriod, maTwoPeriod, maThreePeriod):
    close_len = close_df['close'].size
    if close_len > maThreePeriod:
        return maOnePeriod, maTwoPeriod, maThreePeriod
    if close_len < maThreePeriod and close_len >= 200:
        return 50, 150, 200
    elif close_len < maThreePeriod and close_len >= 150 and close_len < 200:
        return 50, 100, 150 
    elif close_len < maThreePeriod and close_len >= 100 and close_len <150:
        return 10, 20, 60
    else:
        raise Exception("No match period")


def getSMA(close_df, maOnePeriod=50, maTwoPeriod=150, maThreePeriod=200):
    close_df['MA1'] = talib.EMA(close_df['close'], timeperiod=maOnePeriod)
    close_df['MA2'] = talib.EMA(close_df['close'], timeperiod=maTwoPeriod)
    close_df['MA3'] = talib.EMA(close_df['close'], timeperiod=maThreePeriod)
    return close_df

# current price is above between 150-MA & 200-MA
def isAboveTwoMA(current_close, close_df: pd.DataFrame):
    # print("checking isAboveTwoMA...")
    if 'MA2' not in close_df.columns or 'MA3' not in close_df.columns:
        raise Exception("close dataframe should contains columns MA2 MA3")
    if (current_close > close_df['MA2'].iloc[-1]) and (current_close > close_df['MA3'].iloc[-1]):
        return True
    # print("isAboveTwoMA false")
    return False

# MA2(150 DAYS) above MA3(200 DAYS)
def isLongtermIncreasing(close_df):
    # print("checking isLongtermIncreasing...")
    if 'MA2'not in close_df.columns or 'MA3' not in close_df.columns:
        raise Exception("close dataframe should contains columns MA2 MA3")
    if close_df['MA2'].iloc[-1] > close_df['MA3'].iloc[-1]:
        return True
    # print("isLongtermIncreasing false")
    return False

# is 200MA trending up at least one month
def isSlowMATrendingUp(close_df):
    # print("checking isSlowMATrendingUp...")
    if 'MA3' not in close_df.columns:
        raise Exception("close dataframe should contains columns MA3") 
    ema_slow_smooth = talib.EMA(close_df['MA3'], 20).iloc[-1]
    if close_df['MA3'].iloc[-1] > ema_slow_smooth:
        return True 
    # print("isSlowMATrendingUp false")
    return False

# MA1(50 DAYS) above MA2(150 DAYS) and MA3(200 DAYS)
def isShorttermIncreasing(close_df: pd.DataFrame):
    # print("checking isShorttermIncreasing...")
    if 'MA3' not in close_df.columns:
        raise Exception("close dataframe should contains columns MA3") 
    if (close_df['MA1'].iloc[-1] > close_df['MA2'].iloc[-1]) and (close_df['MA1'].iloc[-1]> close_df['MA3'].iloc[-1]):
        return True
    # print("isShorttermIncreasing false")
    return False 

def isAboveMAOne(current_close, close_df):
    # print("checking isAboveMAOne...")
    if 'MA1' not in close_df.columns: 
        raise Exception("close dataframe should contains columns MA3") 
    if close_df['MA1'].iloc[-1] < current_close:
        return True
    # print("isAboveMAOne false")
    return False

def isAboveRecentLow(current_close, close_df, weeks=52, threshold=0.3):
    # print("checking isAboveRecentLow...")
    recent_low = getRecentLow(close_df, weeks)
    if current_close > recent_low * (1 + threshold):
        return True 
    # print("isAboveRecentLow false")
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

def isWithinRecentHigh(current_close, close_df, weeks=52, threshold=0.25):
    # print("checking isWithinRecentHigh...")
    recent_high = getRecentHigh(close_df, weeks)
    # print("0.75 recent high close: {}, current close = {}".format(recent_high * (1 - threshold), current_close))
    if (current_close >= recent_high * (1 - threshold)) or (current_close <= recent_high * (1 + threshold)):
        return True 
    # print("isWithinRecentHigh false")
    return False

def pushConds(result, cond, func_name):
    # print("func_name = {}, cond = {}".format(func_name, cond))
    result['cond'] = result['cond'] & cond
    if not cond:
        result[func_name] = cond
    print("result = {}".format(result))
    return result

def isValidClose(close_df: pd.DataFrame) -> bool:
    """ If close is too low DO NOT consider this stock

    Args:
        close_df (pd.DataFrame): [close, MA1, MA2, MA3, ...]

    Returns:
        bool: Is valid close or not
    """
    if close_df['MA1'].iloc[-1] >= VALID_CLOSE_THRESHOLD:
        return True 
    return False

def checkMMRules(current_close, close_df, period_1, period_2, period_3) -> dict:
    try:
        period_1, period_2, period_3 = adjustMAPeriod(close_df, period_1, period_2, period_3)
        close_df = getSMA(close_df, period_1, period_2, period_3)
        # TODO IBD RS Rating Rule
        rs = {"cond": True}
        # print(close_df)
        ##############################
        ####### Custom Rule ##########
        rs = pushConds(rs, isValidClose(close_df), "isValidClose")
        ####### Prunning #############
        if not rs['cond']:
            return rs
        ##############################
        rs = pushConds(rs, isAboveTwoMA(current_close, close_df), "isAboveTwoMA")
        rs = pushConds(rs, isLongtermIncreasing(close_df), "isLongtermIncreasing") 
        rs = pushConds(rs, isSlowMATrendingUp(close_df), "isSlowMATrendingUp")
        rs = pushConds(rs, isShorttermIncreasing(close_df), "isShorttermIncreasing")
        rs = pushConds(rs, isAboveMAOne(current_close, close_df), "isAboveMAOne")
        rs = pushConds(rs, isAboveRecentLow(current_close, close_df, weeks=52, threshold=0.3), "isAboveRecentLow")
        rs = pushConds(rs, isWithinRecentHigh(current_close, close_df, weeks=52, threshold=0.25), "isWithinRecentHigh")
        return rs

    except Exception as ex:
        raise ex