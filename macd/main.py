from random import sample
from futu import *
import PlateSelectionModel
import datetime
from MarkMinerviniModel import DEFAULT_MA_ONE_PERIOD, DEFAULT_MA_THREE_PERIOD, DEFAULT_MA_TWO_PERIOD, MMMODEL_PERIOD, VALID_CLOSE_THRESHOLD, checkMMRules

############################ 全局变量设置 ############################
FUTUOPEND_ADDRESS = '127.0.0.1'  # FutuOpenD 监听地址
FUTUOPEND_PORT = 11111  # FutuOpenD 监听端口

TRADING_ENVIRONMENT = TrdEnv.SIMULATE  # 交易环境：真实 / 模拟
TRADING_PWD = '914138'  # 交易密码，用于解锁交易
TRADING_PERIOD = KLType.K_1M  # 信号 K 线周期
# TRADING_PERIOD = KLType.K_DAY
TRADING_SECURITY = 'HK.00700'  # 交易标的
FAST_MOVING_AVERAGE = 5  # 均线快线的周期
SLOW_MOVING_AVERAGE = 10  # 均线慢线的周期
SUBSCRIBE_NUM_THRESHOLD = 20
quote_context = OpenQuoteContext(
    host=FUTUOPEND_ADDRESS, port=FUTUOPEND_PORT)  # 行情对象
trade_context = OpenHKTradeContext(host=FUTUOPEND_ADDRESS, port=FUTUOPEND_PORT,
                                   security_firm=SecurityFirm.FUTUSECURITIES)  # 交易对象，根据交易标的修改交易对象类型


def get_acc_holdings():
    ret, data = trade_context.position_list_query(trd_env=TRADING_ENVIRONMENT)
    if ret != RET_OK:
        print('获取持仓数据失败：', data)
        return None
    else:
        if data.shape[0] > 0:
            holding_position = data['qty'][0]
        codes = data.code.tolist()
        quantity_list = data['qty'].tolist()
    return codes, quantity_list


def get_code_list():
    # get holding first
    valid_codes = []
    holding_codes, quantity_list = get_acc_holdings()
    valid_codes.append(list(holding_codes))
    if len(valid_codes) >= SUBSCRIBE_NUM_THRESHOLD:
        return valid_codes
    stock_df = PlateSelectionModel.getStocks(quote_context)
    codes = stock_df['code'].tolist()
    print("holding codes = {}".format(holding_codes))
    print("candidate codes = {}".format(codes))
    valid_codes_2 = []
    end_time = datetime.datetime.now().strftime('%Y-%m-%d')
    codes.append('HK.03690')
    for code in codes:
        try:
            # ret, data = quote_context.get_cur_kline(code, num=MMMODEL_PERIOD, ktype=SubType.K_DAY, autype=AuType.NONE)
            print("code = {}, end_time = {}".format(code, end_time))
            ret, data, page_req_key = quote_context.request_history_kline(
                code, start=None, end=end_time, max_count=1000, ktype=SubType.K_DAY, autype=AuType.NONE)
            time.sleep(1)
            if ret != RET_OK:
                print(data)
                raise Exception("get code list k line failed")
            if data.empty:
                continue
            rule_result = checkMMRules(
                data['close'].iloc[-1], data, DEFAULT_MA_ONE_PERIOD, DEFAULT_MA_TWO_PERIOD, DEFAULT_MA_THREE_PERIOD)
            if rule_result['cond']:
                valid_codes_2.append(code)
        except Exception as ex:
            print(ex)
            continue
    # TODO it is only a temp solution to sample n stocks for reducing api access times
    if len(valid_codes_2) > SUBSCRIBE_NUM_THRESHOLD - len(valid_codes):
        rest_num = SUBSCRIBE_NUM_THRESHOLD - len(valid_codes)
        valid_codes.extend(sample(valid_codes_2, rest_num))
    else:
        valid_codes.extend(valid_codes_2)
    return valid_codes


code_list = get_code_list()
# code_list, qty_list = get_acc_holdings()
logger.info("code_list size = {}, code_list = {}".format(
    len(code_list), code_list))

# 解锁交易


def unlock_trade():
    if TRADING_ENVIRONMENT == TrdEnv.REAL:
        ret, data = trade_context.unlock_trade(TRADING_PWD)
        if ret != RET_OK:
            print('解锁交易失败：', data)
            return False
        print('解锁交易成功！')
    return True


# 获取市场状态
def is_normal_trading_time(code):
    ret, data = quote_context.get_market_state([code])
    if ret != RET_OK:
        print('获取市场状态失败：', data)
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
    print('现在不是持续交易时段。')
    return False


def get_acc_info():
    ret, data = trade_context.accinfo_query(trd_env=TRADING_ENVIRONMENT)
    if ret != RET_OK:
        print("get account info failed: ", data)
        return None
    else:
        return data[['power', 'total_assets', 'cash', 'market_val', 'available_funds']].iloc[0]

# 获取持仓数量


def get_holding_position(code):
    holding_position = 0
    ret, data = trade_context.position_list_query(
        code=code, trd_env=TRADING_ENVIRONMENT)
    if ret != RET_OK:
        print('获取持仓数据失败：', data)
        return None
    else:
        if data.shape[0] > 0:
            holding_position = data['qty'][0]
        print('【持仓状态】 {} 的持仓数量为：{}'.format(code, holding_position))
    return holding_position


# 拉取 K 线，计算均线，判断多空
def calculate_bull_bear(code, fast_param, slow_param):
    if fast_param <= 0 or slow_param <= 0:
        return 0
    if fast_param > slow_param:
        return calculate_bull_bear(code, slow_param, fast_param)
    ret, data = quote_context.get_cur_kline(
        code=code, num=slow_param + 1, ktype=TRADING_PERIOD)
    if ret != RET_OK:
        print('获取K线失败：', data)
        return 0
    candlestick_list = data['close'].values.tolist()[::-1]
    fast_value = None
    slow_value = None
    if len(candlestick_list) > fast_param:
        fast_value = sum(candlestick_list[1: fast_param + 1]) / fast_param
    if len(candlestick_list) > slow_param:
        slow_value = sum(candlestick_list[1: slow_param + 1]) / slow_param
    if fast_value is None or slow_value is None:
        return 0
    return 1 if fast_value >= slow_value else -1


# 获取一档摆盘的 ask1 和 bid1
def get_ask_and_bid(code):
    ret, data = quote_context.get_order_book(code, num=1)
    if ret != RET_OK:
        print('获取摆盘数据失败：', data)
        return None, None
    return data['Ask'][0][0], data['Bid'][0][0]


# 开仓函数
def open_position(code):
    # 获取摆盘数据
    ask, bid = get_ask_and_bid(code)

    # 计算下单量
    # open_quantity = calculate_quantity()
    open_quantity = calculate_quantity(code)

    # 判断购买力是否足够
    if is_valid_quantity(code, open_quantity, ask):
        # if is_valid_quantity(TRADING_SECURITY, open_quantity, ask):
        # 下单
        ret, data = trade_context.place_order(price=ask, qty=open_quantity, code=code, trd_side=TrdSide.BUY,
                                              order_type=OrderType.NORMAL, trd_env=TRADING_ENVIRONMENT,
                                              remark='moving_average_strategy')
        if ret != RET_OK:
            print('开仓失败：', data)
    else:
        print('下单数量超出最大可买数量。')


# 平仓函数
def close_position(code, quantity):
    # 获取摆盘数据
    ask, bid = get_ask_and_bid(code)

    # 检查平仓数量
    if quantity == 0:
        print('无效的下单数量。')
        return False

    # 平仓
    print("平仓 {} 价格 {} 数量 {}".format(code, bid, quantity))
    ret, data = trade_context.place_order(price=bid, qty=quantity, code=code, trd_side=TrdSide.SELL,
                                          order_type=OrderType.NORMAL, trd_env=TRADING_ENVIRONMENT, remark='moving_average_strategy')
    if ret != RET_OK:
        print('平仓失败：', data)
        return False
    return True

# 计算下单数量


def calculate_quantity(code=TRADING_SECURITY):
    price_quantity = 0
    # 使用最小交易量
    ret, data = quote_context.get_market_snapshot([code])
    if ret != RET_OK:
        print('获取快照失败：', data)
        return price_quantity
    price_quantity = data['lot_size'][0]
    return price_quantity


# 判断购买力是否足够
def is_valid_quantity(code, quantity, price):
    ret, data = trade_context.acctradinginfo_query(order_type=OrderType.NORMAL, code=code, price=price,
                                                   trd_env=TRADING_ENVIRONMENT)
    if ret != RET_OK:
        print('获取最大可买可卖失败：', data)
        return False
    max_can_buy = data['max_cash_buy'][0]
    max_can_sell = data['max_sell_short'][0]
    if quantity > 0:
        return quantity < max_can_buy
    elif quantity < 0:
        return abs(quantity) < max_can_sell
    else:
        return False


# 展示订单回调
def show_order_status(data):
    order_status = data['order_status'][0]
    order_info = dict()
    order_info['代码'] = data['code'][0]
    order_info['价格'] = data['price'][0]
    order_info['方向'] = data['trd_side'][0]
    order_info['数量'] = data['qty'][0]
    print('【订单状态】', order_status, order_info)


def clear_all(codes, qtys):
    print("acc holdings, codes: {}, quantity: {}".format(codes, qtys))
    for code, qty in zip(codes, qtys):
        print("try to clear {} qty: {}".format(code, qty))
        # refresh qty
        qty = get_holding_position(code)
        # print('【持仓状态】 {} 的持仓数量为：{}'.format(code, qty))
        if qty > 0:
            close_position(code, qty)


def order_stocks(holding_position_list, bull_or_bear_signals, code_list):
    code_status_list = zip(
        code_list, holding_position_list, bull_or_bear_signals)
    for code, holding_position, bull_or_bear in code_status_list:
        order_stock(holding_position, bull_or_bear, code)


def order_stock(holding_position, bull_or_bear, code):
    # 下单判断
    if holding_position == 0:
        if bull_or_bear == 1:
            print("code={},【操作信号】 做多信号，建立多单。".format(code))
            # open_position(code_list[0])
            open_position(code)
        else:
            print("code={},【操作信号】 做空信号，不开空单。".format(code))
    elif holding_position > 0:
        if bull_or_bear == -1:
            print("code={},【操作信号】 做空信号，平掉持仓。".format(code))
            # close_position(code_list[0], holding_position)
            close_position(code, holding_position)
        else:
            print('code={},【操作信号】 做多信号，无需加仓。'.format(code))


############################ 填充以下函数来完成您的策略 ############################
# 策略启动时运行一次，用于初始化策略
def on_init():
    # 解锁交易（如果是模拟交易则不需要解锁）
    if not unlock_trade():
        return False
    print('************  策略开始运行 ***********')
    return True


# 每个 tick 运行一次，可将策略的主要逻辑写在此处
def on_tick():
    pass


# 每次产生一根新的 K 线运行一次，可将策略的主要逻辑写在此处
def on_bar_open():
    # 打印分隔线
    print('*************************************')

    # 只在常规交易时段交易
    if not is_normal_trading_time(TRADING_SECURITY):
        return

    # 获取 K 线，计算均线，判断多空
    # bull_or_bear_signals = [calculate_bull_bear(code, FAST_MOVING_AVERAGE, SLOW_MOVING_AVERAGE) for code in code_list]
    # 获取持仓数量
    # holding_position_list = [get_holding_position(code) for code in code_list]
    # order_stocks(holding_position_list, bull_or_bear_signals, code_list)
    # clear_all(code_list, qty_list)


# 委托成交有变化时运行一次
def on_fill(data):
    pass


# 订单状态有变化时运行一次
def on_order_status(data):
    # if data['code'][0] == TRADING_SECURITY:
    show_order_status(data)


################################ 框架实现部分，可忽略不看 ###############################
class OnTickClass(TickerHandlerBase):
    def on_recv_rsp(self, rsp_pb):
        on_tick()


class OnBarClass(CurKlineHandlerBase):
    last_time = None

    def on_recv_rsp(self, rsp_pb):
        ret_code, data = super(OnBarClass, self).on_recv_rsp(rsp_pb)
        if ret_code == RET_OK:
            # acc_df = get_acc_info()
            # print(acc_df)
            cur_time = data['time_key'][0]
            if cur_time != self.last_time and data['k_type'][0] == TRADING_PERIOD:
                if self.last_time is not None:
                    on_bar_open()
                self.last_time = cur_time


class OnOrderClass(TradeOrderHandlerBase):
    def on_recv_rsp(self, rsp_pb):
        ret, data = super(OnOrderClass, self).on_recv_rsp(rsp_pb)
        if ret == RET_OK:
            on_order_status(data)


class OnFillClass(TradeDealHandlerBase):
    def on_recv_rsp(self, rsp_pb):
        ret, data = super(OnFillClass, self).on_recv_rsp(rsp_pb)
        if ret == RET_OK:
            on_fill(data)


# 主函数
if __name__ == '__main__':
    # 初始化策略
    if not on_init():
        print('策略初始化失败，脚本退出！')
        quote_context.close()
        trade_context.close()
    else:
        # 设置回调
        quote_context.set_handler(OnTickClass())
        quote_context.set_handler(OnBarClass())
        trade_context.set_handler(OnOrderClass())
        trade_context.set_handler(OnFillClass())

        # 订阅标的合约的 逐笔，K 线和摆盘，以便获取数据
        quote_context.subscribe(code_list=code_list, subtype_list=[
                                SubType.TICKER, SubType.ORDER_BOOK, TRADING_PERIOD])
