from futu.quote.open_quote_context import OpenQuoteContext
from futu import *


PLATE_NO_NEW_ENERGY = "HK.BK1033"  # 新能源板块
PLATE_NO_TESLA = "HK.BK1180"  # 特斯拉概念板块
PLATE_NO_TENCENT = "HK.BK1190"  # 腾讯概念板块
PLATE_NO_SOLAR_ENERGY = "HK.BK1233"  # 光伏太阳能板块
PLATE_NO_HOLIDAYS = "HK.BK1998"  # 节假日概念
PLATE_NO_FOOD = "HK.BK1227"  # FOOD CONCEPT
PLATE_NO_BABY = "HK.BK1209"  # BABY CONCEPT
PLATE_NO_MEDICAL_BEAUTY = "HK.BK1086"  # 医疗美容
PLATE_NO_CIGA = "HK.BK1283"  # 烟草
PLATE_NO_RESTAURANT = "HK.BK1083"  # 餐饮


def getFutuPlateList(quote_context: OpenQuoteContext, market=Market.HK) -> pd.DataFrame:
    """a function wrapper to get plate code via futu api

    Args:
        quote_context (OpenQuoteContext): FUTU quote context
        market ([type], optional): [description]. Defaults to Market.HK.

    Returns:
        pd.DataFrame: [code, plate_name, plate_id]
    """
    ret, data = quote_context.get_plate_list(market, Plate.ALL)
    if ret != RET_OK:
        logger.debug('error: ', data)
    return data

def getPlateList():
    plate_list = [PLATE_NO_NEW_ENERGY, PLATE_NO_SOLAR_ENERGY, PLATE_NO_TESLA, 
                  PLATE_NO_TENCENT, PLATE_NO_FOOD, PLATE_NO_HOLIDAYS, PLATE_NO_BABY,
                  PLATE_NO_MEDICAL_BEAUTY, PLATE_NO_CIGA, PLATE_NO_RESTAURANT] 
 
    return plate_list

def getStockByPlate(quote_context: OpenQuoteContext, plate_code: str) -> pd.DataFrame:
    """get stock by plate code

    Args:
        quote_context (OpenQuoteContext): FUTU quote context
        plate_code (str): plate code, eg. HK.BK1033

    Returns:
        pd.DataFrame: ['code', 'lot_size', 'stock_name', 'stock_type', 'list_time', 'last_trade_time']
    """
    logger.debug("get stock dataframe of plate code: {}".format(plate_code))
    ret, data = quote_context.get_plate_stock(plate_code)
    if ret != RET_OK:
        logger.debug('error: ', data)
        return None
    return data[['code', 'lot_size', 'stock_name', 'stock_type', 'list_time', 'last_trade_time']]


def getStocksByPlates(quote_context: OpenQuoteContext, plate_code_list: list) -> dict:
    """get stocks by plate code list

    Args:
        quote_context (OpenQuoteContext): FUTU quote context
        plate_code_list (list): list of plate code

    Returns:
        dict: {plate_code <str>: stock_df <pd.Dataframe ['code', 'stock_name', 'list_time']>}
    """
    plate_stocks = {}
    for plate_code in plate_code_list:
        stock_df = getStockByPlate(quote_context=quote_context, plate_code=plate_code)
        plate_stocks[plate_code] = stock_df[['code', 'stock_name', 'list_time']] 
    return plate_stocks

def getStocks(quote_context: OpenQuoteContext) -> pd.DataFrame:
    """generate stock list for further analysis

    Args:
        quote_context (OpenQuoteContext): FUTU quote context

    Returns:
        pd.DataFrame: ['code', 'stock_name', 'list_time']
    """
    plate_code_list = getPlateList() 
    plate_stocks = getStocksByPlates(quote_context, plate_code_list)
    stock_dataframes = [stock_dataframe for plate, stock_dataframe in plate_stocks.items()] 
    stock_df = pd.concat(stock_dataframes)
    # remove duplicates
    stock_df.drop_duplicates('code', keep='first', inplace=True)
    return stock_df
