from futu import *
from MarkMinerviniModel import *
import talib
import datetime
import numpy as np
import pandas as pd
import logging

logging.basicConfig(level = logging.INFO, format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
############################ 全局变量设置 ############################
FUTUOPEND_ADDRESS = '127.0.0.1'  # FutuOpenD 监听地址
FUTUOPEND_PORT = 11111  # FutuOpenD 监听端口

TRADING_ENVIRONMENT = TrdEnv.SIMULATE  # 交易环境：真实 / 模拟
TRADING_PWD = '123456'  # 交易密码，用于解锁交易
TRADING_PERIOD = KLType.K_1M  # 信号 K 线周期
TRADING_SECURITY = 'HK.00700'  # 交易标的
FAST_MOVING_AVERAGE = 9  # 均线快线的周期
SLOW_MOVING_AVERAGE = 26  # 均线慢线的周期

quote_context = OpenQuoteContext(host=FUTUOPEND_ADDRESS, port=FUTUOPEND_PORT)  # 行情对象
trade_context = OpenHKTradeContext(host=FUTUOPEND_ADDRESS, port=FUTUOPEND_PORT, security_firm=SecurityFirm.FUTUSECURITIES)  # 交易对象，根据交易标的修改交易对象类型


# get stock close price by code
def getCloseByCode(code):
    ret_sub, err_message = quote_context.subscribe([code], [SubType.K_DAY], subscribe_push=False)
    if ret_sub == RET_OK:
        ret_code, data = quote_context.get_cur_kline(code, 365, SubType.K_DAY, AuType.QFQ)
        if ret_code != RET_OK:
            logger.debug("fetch Kline failed")
        close = data['close']
        time_key = data['time_key']
    return close, time_key

def macdCN(close, fastperiod, slowperiod, signalperiod):
    macdDIFF, macdDEA, macd = talib.MACDEXT(close, fastperiod=fastperiod, fastmatype=1, slowperiod=slowperiod, slowmatype=1, signalperiod=signalperiod, signalmatype=1)
    macd = macd * 2
    return macdDIFF, macdDEA, macd

def getMACDbyCode(code):
    close, time_key = getCloseByCode(code)
    # macd, macdsignal, macdhist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    macd, macdsignal, macdhist = macdCN(close, fastperiod=12, slowperiod=26, signalperiod=9) 
    macd_frame = {"time_key": time_key, "DIFF": macd, "DEA": macdsignal, "HIST": macdhist}
    macd_frame = pd.DataFrame(macd_frame)
    macd_frame["sell_signal"] = 0
    macd_frame["buy_signal"] = 0
    # logger.debug(macd_frame)
    return macd_frame
    
def generateBuySignal(macd_frame):
    if pd.isna(macd_frame['DIFF']) or pd.isna(macd_frame['DEA']) or pd.isna(macd_frame['HIST']):
        return 0
    if macd_frame['DIFF'] >= 0 and macd_frame['DEA'] >= 0 and macd_frame['HIST'] > 0:
        return 1
    # elif abs(macd_frame['DIFF']) <= 0.1 and abs(macd_frame['DEA']) <= 0.1 and macd_frame['HIST'] > 0:
        # return 1
    else:
        return 0

def generateSellSignal(macd_frame):
    if pd.isna(macd_frame['DIFF']) or pd.isna(macd_frame['DEA']) or pd.isna(macd_frame['HIST']):
        return 0
    if macd_frame['DIFF'] < 0 and macd_frame['DEA'] < 0 and macd_frame['HIST'] < 0:
        return 1
    elif macd_frame['DIFF'] >= 0 and macd_frame['DEA'] >= 0 and macd_frame['HIST'] < 0:
        return 1
    else:
        return 0

def generateSignals(macd_frame):
    logger.debug("try to generate buy signal...")
    macd_frame['buy_signal'] = macd_frame.apply(generateBuySignal, axis=1)
    logger.debug("try to generate sell signal...")
    macd_frame['sell_signal'] = macd_frame.apply(generateSellSignal, axis=1)
    return macd_frame

def getPlateList():
    ret, data = quote_context.get_plate_list(Market.HK, Plate.ALL)
    if ret != RET_OK:
        logger.debug('error: ', data)
    return data

def getPlateStock(plate_code, plate_df):
    logger.debug("get stock of plate code: {}".format(plate_code))
    sub_plate_df = plate_df.query('code == @plate_code')
    ret, data = quote_context.get_plate_stock(plate_code)
    if ret != RET_OK:
        logger.debug('error: ', data)
    return data

def getCandidateStocksByPlate(plate_code_list, plate_df):
    candidates = {}
    for plate_code in plate_code_list:
        stock_df = getPlateStock(plate_code, plate_df)
        candidates[plate_code] = stock_df[['code', 'stock_name', 'list_time']] 
    logger.debug(candidates)
    return candidates

def generateStockPool():
    pass

def filterByMMModel(candidates):
    filtered = []
    for plate_code, stock_df in candidates.items():
        try:
            stock_codes = stock_df[['code']].squeeze().values.tolist()
        except:
            logger.debug("get stock code list error")
            logger.debug(stock_df[['code']])
            continue
        
        for stock_code in stock_codes:
            try:
                stock_name = stock_df[['stock_name']][stock_df.code == stock_code].squeeze()
                close, time_key = getCloseByCode(stock_code)
                close_df = pd.DataFrame({"close": close, "time_key": time_key})
                current_close = close_df['close'].iloc[-1]
                mmRulesConds = checkMMRules(current_close, close_df, 50, 150, 200)
                if mmRulesConds['cond']:
                    filtered.append({"stock_name": stock_name, "stock_code": stock_code})
                logger.debug("stock name = {}, code = {}".format(stock_name, stock_code))
            except Exception as ex:
                logger.debug(ex)
                continue
    return filtered

def scanAllCandidates(candidates):
    cur_month = datetime.datetime.now().strftime('%Y-%m')
    for plate_code, stock_df in candidates.items():
        logger.debug("plate_code = {}".format(plate_code))
        try:
            stock_codes = stock_df[['code']].squeeze().values.tolist()
        except:
            logger.debug("get stock code list error")
            logger.debug(stock_df[['code']])
            continue
        for stock_code in stock_codes:
            stock_name = stock_df[['stock_name']][stock_df.code == stock_code].squeeze()
            macd_frame = getMACDbyCode(stock_code)
            macd_frame = generateSignals(macd_frame)
            buysignal_df = macd_frame[["time_key", "DIFF", "DEA", "HIST", "buy_signal"]][macd_frame.buy_signal == 1]
            recent_buysignal_df = buysignal_df.query('time_key.str.contains(@cur_month)')
            if not recent_buysignal_df.empty: 
                logger.info("plate_code = {}, stock_code = {}, stock_name = {}".format(plate_code, stock_code, stock_name))
                logger.info(recent_buysignal_df)

if __name__ == '__main__':
    # np.set_logger.debugoptions(threshold=np.inf)
    pd.set_option('display.max_columns', None)  # or 1000
    pd.set_option('display.max_rows', None)  # or 1000
    pd.set_option('display.max_colwidth', -1)  # or 199
    # macd_frame = getMACDbyCode(code)
    # macd_frame = generateSignals(macd_frame)
    
    # logger.debug("try to logger.debug buy signal...")
    # logger.debug(macd_frame[["time_key", "DIFF", "DEA", "HIST", "buy_signal"]][macd_frame.buy_signal == 1])
    # logger.debug("try to logger.debug sell signal...")
    # logger.debug(macd_frame[["time_key", "DIFF", "DEA", "HIST", "sell_signal"]][macd_frame.sell_signal == 1])
    plate_df = getPlateList()
    # logger.debug(plate_df)
    # logger.debug(plate_df.columns)
    PLATE_NO_NEW_ENERGY = "HK.BK1033" #新能源板块
    PLATE_NO_TESLA = "HK.BK1180" #特斯拉概念板块
    PLATE_NO_TENCENT = "HK.BK1190" #腾讯概念板块
    PLATE_NO_SOLAR_ENERGY = "HK.BK1233" #光伏太阳能板块
    PLATE_NO_HOLIDAYS = "HK.BK1998" # 节假日概念
    PLATE_NO_FOOD = "HK.BK1227" #FOOD CONCEPT
    PLATE_NO_BABY = "HK.BK1209" # BABY CONCEPT
    PLATE_NO_MEDICAL_BEAUTY = "HK.BK1086" # 医疗美容
    PLATE_NO_CIGA = "HK.BK1283" # 烟草
    PLATE_NO_RESTAURANT = "HK.BK1083" #餐饮
    
    PLATE_LIST = [PLATE_NO_NEW_ENERGY, PLATE_NO_SOLAR_ENERGY, PLATE_NO_TESLA, 
                  PLATE_NO_TENCENT, PLATE_NO_FOOD, PLATE_NO_HOLIDAYS, PLATE_NO_BABY,
                  PLATE_NO_MEDICAL_BEAUTY, PLATE_NO_CIGA, PLATE_NO_RESTAURANT] 
    candidates = getCandidateStocksByPlate(PLATE_LIST, plate_df=plate_df)
    # scanAllCandidates(candidates=candidates)
    mmmodel_stock_name_code_obj = filterByMMModel(candidates)
    logger.info("printing filtered stocks by MM Model...")
    logger.info(mmmodel_stock_name_code_obj)
    quote_context.close()
    trade_context.close()
