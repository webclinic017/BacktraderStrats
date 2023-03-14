from email.quoprimime import quote
from futu import *
from backtrader import CommInfoBase

import logging
from logging.config import fileConfig


fileConfig('logging.conf')
logger = logging.getLogger()

############################ 全局变量设置 ############################
FUTUOPEND_ADDRESS = '127.0.0.1'  # FutuOpenD 监听地址
FUTUOPEND_PORT = 11111  # FutuOpenD 监听端口

TRADING_ENVIRONMENT = TrdEnv.SIMULATE  # 交易环境：真实 / 模拟
TRADING_PWD = '914138'  # 交易密码，用于解锁交易
TRADING_PERIOD = KLType.K_1M  # 信号 K 线周期
# TRADING_PERIOD = KLType.K_DAY
TRADING_SECURITY = 'HK.00700'  # 交易标的

quote_context = None
trade_context = None

def on_bar_open(data):
    logger.info("*****************************")
    logger.info(data)



class OnBarClass(CurKlineHandlerBase):
    last_time = None
    
    def __init__(self, trading_period):
        self.trading_period = trading_period
        logger.info('period = %s' % self.trading_period)

    def on_recv_rsp(self, rsp_pb):
        ret_code, data = super(OnBarClass, self).on_recv_rsp(rsp_pb)
        if ret_code == RET_OK:
            cur_time = data['time_key'][0]
            if cur_time != self.last_time and data['k_type'][0] == self.trading_period:
                if self.last_time is not None:
                    on_bar_open(data)
                self.last_time = cur_time
        else:
            logger.info(data)


def open_context(host=FUTUOPEND_ADDRESS, port=FUTUOPEND_PORT):
    global quote_context, trade_context
    quote_context = OpenQuoteContext(
        host=host, port=port)  # 行情对象
    trade_context = OpenHKTradeContext(host=host, port=port,
                                       security_firm=SecurityFirm.FUTUSECURITIES)  # 交易对象，根据交易标的修改交易对象类型
    # quote_context.set_handler(OnBarClass)
    return quote_context, trade_context


def close_context():
    quote_context.close()
    trade_context.close()


def unlock_trade(trade_context=trade_context, trading_pwd=TRADING_PWD, trading_env=TRADING_ENVIRONMENT):
    if trading_env == TrdEnv.REAL:
        ret, data = trade_context.unlock_trade(trading_pwd)
        if ret != RET_OK:
            logger.info('unlock trade failure：', data)
            return False
        logger.info('unlock trade successfully!')
    return True


def is_normal_trading_time(code):
    ret, data = quote_context.get_market_state([code])
    if ret != RET_OK:
        logger.info('retrieve market state failure：', data)
        return False
    market_state = data['market_state'][0]
    '''
    MarketState.MORNING            港、A 股早盘
    MarketState.AFTERNOON          港、A 股下午盘，美股全天
    MarketState.FUTURE_DAY_OPEN    港、新、日期货日市开盘
    MarketState.FUTURE_OPEN        美期货开盘
    MarketState.NIGHT_OPEN         港、新、日期货夜市开盘
    '''
    if market_state == MarketState.MORNING or \
            market_state == MarketState.AFTERNOON or \
            market_state == MarketState.FUTURE_DAY_OPEN or \
            market_state == MarketState.FUTURE_OPEN or \
            market_state == MarketState.NIGHT_OPEN:
        return True
    logger.info('market not in traidng hour')
    return False


# 获取一档摆盘的 ask1 和 bid1
def get_ask_and_bid(code):
    ret_sub, data_sub = quote_context.subscribe([code], [SubType.ORDER_BOOK], subscribe_push=False)
    if ret_sub == RET_OK:
        ret, data = quote_context.get_order_book(code, num=1)
        if ret != RET_OK:
            logger.info('获取摆盘数据失败：', data)
            return None, None
        return data['Ask'][0][0], data['Bid'][0][0]
    else:
        logger.info('code: %s subscription failure, ERR Message: %s' % (code, data_sub))


# 判断购买力是否足够
def is_valid_quantity(code, quantity, price):
    ret, data = trade_context.acctradinginfo_query(order_type=OrderType.NORMAL, code=code, price=price,
                                                   trd_env=TRADING_ENVIRONMENT)
    if ret != RET_OK:
        logger.info('获取最大可买可卖失败：', data)
        return False
    max_can_buy = data['max_cash_buy'][0]
    max_can_sell = data['max_sell_short'][0]
    if quantity > 0:
        return quantity < max_can_buy
    elif quantity < 0:
        return abs(quantity) < max_can_sell
    else:
        return False

def get_holding_position(code, trd_env=TRADING_ENVIRONMENT):
    holding_position = 0
    ret, data = trade_context.position_list_query(
        code=code, trd_env=trd_env)
    if ret != RET_OK:
        logger.info('retrieve holding position failure：', data)
        return None
    else:
        if data.shape[0] > 0:
            holding_position = data['qty'][0]
        logger.info('【holding status】 {} holding positions：{}'.format(code, holding_position))
    return holding_position



# 开仓函数
def open_position(code, open_quantity):
    # 获取摆盘数据
    ask, bid = get_ask_and_bid(code)
    
    if not open_quantity:
        # 计算下单量
        # smallest qty
        open_quantity = calculate_quantity(code)

    # 判断购买力是否足够
    if is_valid_quantity(code, open_quantity, ask):
        # if is_valid_quantity(TRADING_SECURITY, open_quantity, ask):
        # 下单
        ret, data = trade_context.place_order(price=ask, qty=open_quantity, code=code, trd_side=TrdSide.BUY,
                                              order_type=OrderType.NORMAL, trd_env=TRADING_ENVIRONMENT)
        if ret != RET_OK:
            logger.info('开仓失败：', data)
        logger.info('code %s open position successfully! quantity: %d' % (code, open_quantity))
    else:
        logger.info('下单数量超出最大可买数量。')


# 平仓函数
def close_position(code, quantity):
    # 获取摆盘数据
    ask, bid = get_ask_and_bid(code)

    # 检查平仓数量
    if quantity == 0:
        logger.info('无效的下单数量。')
        return False

    # 平仓
    logger.info("平仓 {} 价格 {} 数量 {}".format(code, bid, quantity))
    ret, data = trade_context.place_order(price=bid, qty=quantity, code=code, trd_side=TrdSide.SELL,
                                          order_type=OrderType.NORMAL, trd_env=TRADING_ENVIRONMENT, remark='moving_average_strategy')
    if ret != RET_OK:
        logger.info('平仓失败：', data)
        return False
    return True


def clear_position(code, trd_env=TRADING_ENVIRONMENT):
    qty = get_holding_position(code, trd_env=trd_env)
    close_position(code, qty)


# 计算下单数量
def calculate_quantity(code):
    price_quantity = 0
    # 使用最小交易量
    ret, data = quote_context.get_market_snapshot([code])
    if ret != RET_OK:
        logger.info('获取快照失败：', data)
        return price_quantity
    price_quantity = data['lot_size'][0]
    return price_quantity



# 展示订单回调
def show_order_status(data):
    order_status = data['order_status'][0]
    order_info = dict()
    order_info['代码'] = data['code'][0]
    order_info['价格'] = data['price'][0]
    order_info['方向'] = data['trd_side'][0]
    order_info['数量'] = data['qty'][0]
    logger.info('【订单状态】', order_status, order_info)



class Futu_CommInfo(CommInfoBase):
    params = (
        ('stocklike', True),
        ('commtype', CommInfoBase.COMM_PERC),
    )

    def _getcommission(self, size, price, pseudoexec):
        return abs(size) * price * self.p.commission + 15