import backtrader as bt
import backtrader.feeds as btfeeds
import backtrader.indicators as btind
import logging
import pytz
import smtp
from datetime import datetime, timezone, timedelta
from collections import OrderedDict
from logging.config import fileConfig


fileConfig('logging.conf')
logger = logging.getLogger()

class MultiStochRSIMacdCompStrategy(bt.Strategy):
    params = dict(
        stop_loss=0.5,
        fastk_period=10,
        slowk_period=3,
        slowd_period=3,
        overbought_threshold=80.0,
        oversold_threshold=30.0,
        rsi_period=10,
        macd_fastperiod=10,
        macd_slowperiod=22,
        macd_signalperiod=7,
        comp_period=5,
        stakes=OrderedDict(),
        ind_periods=OrderedDict(),
        order_amount_limit=30000,
        tz=pytz.timezone('Asia/Hong_Kong')

    )

    def is_overbought(self, slowk, slowd):
        for i in range(-self.p.comp_period + 1, 1):
            if slowk[i] >= self.p.overbought_threshold and slowd[i] >= self.p.overbought_threshold:
                return True
            else:
                continue
        return False
    
    def is_oversold(self, slowk, slowd):
        for i in range(-self.p.comp_period + 1, 1):
            if slowk[i] <= self.p.oversold_threshold and slowd[i] <= self.p.oversold_threshold:
                return True
            else:
                continue
        return False
    
    def is_rsi_over_mid(self, rsi):
        for i in range(-self.p.comp_period + 1, 1):
            if rsi[i] > 50.0:
                return True
            else:
                continue
        return False

    def is_rsi_under_mid(self, rsi):
        for i in range(-self.p.comp_period + 1, 1):
            if rsi[i] < 50.0:
                return True
            else:
                continue
        return False

    def is_macd_over_macdsignal(self, macd, macdsignal):
        if macd[0] > macdsignal[0]:
            return True
        else:
            return False
    
    def is_macd_under_macdsignal(self, macd, macdsignal):
        if macd[0] < macdsignal[0]:
            return True
        else:
            return False
        
    def __init__(self):
        self.orderid = None
        self.slowks = OrderedDict()
        self.slowds = OrderedDict()
        self.rsis = OrderedDict()
        self.macds = OrderedDict()
        self.macdsignals = OrderedDict()
        self.macdhists = OrderedDict()
         
        for i, data in enumerate(self.datas):
            code = data._name
            default_periods = self.p.ind_periods.get('default', OrderedDict())
            ind_periods = self.p.ind_periods.get(code, default_periods)
            # stochastic kdj
            fastk_period = ind_periods.get('fastk_period', self.p.fastk_period)
            slowk_period = ind_periods.get('slowk_period', self.p.slowk_period)
            slowd_period = ind_periods.get('slowd_period', self.p.slowd_period)
            # rsi
            rsi_period = ind_periods.get('rsi_period', self.p.rsi_period)
            # macd
            macd_fastperiod = ind_periods.get('macd_fastperiod', self.p.macd_fastperiod)
            macd_slowperiod = ind_periods.get('macd_slowperiod', self.p.macd_slowperiod)
            macd_signalperiod = ind_periods.get('macd_signalperiod', self.p.macd_signalperiod)
            stoch = bt.talib.STOCH(
                data.high, data.low, data.close, 
                fastk_period=fastk_period, 
                slowk_period=slowk_period, 
                slowd_period=slowd_period)
            self.slowks[code] = stoch.slowk
            self.slowds[code] = stoch.slowd
            self.rsis[code]  = bt.talib.RSI(data, timeperiod=rsi_period)
            macdlines = bt.talib.MACD(
                data, 
                fastperiod=macd_fastperiod, 
                slowperiod=macd_slowperiod, 
                signalperiod=macd_signalperiod)
            self.macds[code] = macdlines.macd 
            self.macdsignals[code] = macdlines.macdsignal
            self.macdhists[code] = macdlines.macdhist

    def adjust_order_amount(self, cash):
        amount = self.p.order_amount_limit if cash >= self.p.order_amount_limit else cash
        return amount

    def calculate_quantity(self, amount, close, stake):
        self.log("amount: {}, close: {}, stake: {}".format(amount, close, stake))
        quantity = int(amount / close)
        quantity = int(quantity / stake) * stake
        return quantity

    def per_next(self, data):
        sysdt = datetime.now(self.p.tz).date()
        dt = data.datetime.date()
        portfolio_value = self.broker.get_value()
        possize = self.getposition(data, self.broker).size
        cash = self.broker.cash
#         self.log('stop_loss: %.2f' % self.stop_loss)

        slowk = self.slowks[data._name]
        slowd = self.slowds[data._name]
        rsi = self.rsis[data._name]
        macd = self.macds[data._name]
        macdsignal = self.macdsignals[data._name]
        
        self.log('cash: %.2f' % cash)
        self.log('Data %s Close: %.2f' % (data._name, data.close[0]))
        self.log('%04d - %s - Data Position Size:  %02d - Value %.2f' %
              (len(data), dt.isoformat(), possize, portfolio_value))
        ind_str = 'slowk: %.2f, slowd: %.2f, rsi: %.2f, macd: %.2f, macdsignal: %.2f ' % (
            slowk[0], slowd[0], rsi[0], macd[0], macdsignal[0])
        rsi_over_mid_str = 'rsi over mid: %r' % (self.is_rsi_over_mid(rsi))
        rsi_under_mid_str = 'rsi under mid : %r' % (self.is_rsi_under_mid(rsi))
        overbouhgt_str = 'overbought: %r' % (self.is_overbought(slowk, slowd))
        oversold_str = 'oversold: %r' % (self.is_oversold(slowk, slowd))
        macd_over_signal_str = 'macd over macdsignal: %r' % (self.is_macd_over_macdsignal(macd, macdsignal))
        macd_under_signal_str = 'macd under macdsignal: %r' % (self.is_macd_under_macdsignal(macd, macdsignal))
        self.log(ind_str)
        self.log(rsi_over_mid_str)
        self.log(rsi_under_mid_str)
        self.log(overbouhgt_str)
        self.log(oversold_str)
        self.log(macd_over_signal_str)
        self.log(macd_under_signal_str)
        info_str = '\n'.join([dt.isoformat(), ind_str, rsi_over_mid_str, rsi_under_mid_str, overbouhgt_str, 
                   oversold_str, macd_over_signal_str, macd_under_signal_str])
        if self.orderid:
            return
        
        if  not (self.p.stop_loss is None) and \
            ((self.broker.getvalue() - self.broker.startingcash) / self.broker.startingcash >= self.p.stop_loss \
            or (self.broker.getvalue() - self.broker.startingcash) / self.broker.startingcash <= - self.p.stop_loss) and \
            possize > 0:
            self.log('STOP LOSS, SELL SIGNAL')
            order = self.order_target_percent(data, 0)
            self.log('%s - %s - OrderNo: %s - Order Target Percent: %.2f' % (data._name, dt.isoformat(), order, 0))
            return
        # buy
        if self.is_rsi_over_mid(rsi) and self.is_oversold(slowk, slowd) and self.is_macd_over_macdsignal(macd, macdsignal):
            buy_signal_subject = 'Data %s BUY SIGNAL!' % data._name
            self.log(buy_signal_subject) 
            msg_text = info_str
            if possize == 0:
                amount = self.adjust_order_amount(cash)
                quantity = self.calculate_quantity(amount, data.close[0], self.p.stakes.get(data._name, 100))
                # TODO can implement after live trading part finished
                # self.buy(data=data, size=quantity)
                buy_create_str = 'BUY CREATE %s, price = %.2f, qty = %d' % (data._name, data.close[0], quantity)
                msg_text = msg_text + '\n' + buy_create_str
                self.log(buy_create_str)
            if sysdt - dt <= timedelta(days=2):
                logger.info('buy signal create within 2 days, try to send mail')
                logger.info('mail msg: %s' % msg_text)
                smtp.send_mail(msg_text=msg_text, subject=buy_signal_subject)
        # sell
#         if self.is_rsi_under_mid() and self.is_overbought() and self.is_macd_under_macdsignal() and possize > 0:
        if self.is_rsi_under_mid(rsi) and (not self.is_oversold(slowk, slowd)) and self.is_macd_under_macdsignal(slowk, slowd):
            sell_signal_subject = 'Data %s SELL SIGNAL!' % data._name
            self.log(sell_signal_subject)
            if possize > 0:
                # TODO can implement after live trading part finished
                # order = self.order_target_percent(data, 0)
                self.log('%s - %s - OrderNo: %s - Order Target Percent: %.2f' % (data._name, dt.isoformat(), order, 0))
            msg_text = 'SELL CREATE %s, price = %.2f' % (data._name, data.close[0])
            if sysdt - dt <= timedelta(days=2):
                logger.info('sell signal create within 2 days, try to send mail')
                logger.info('mail msg: %s' % msg_text)
                smtp.send_mail(msg_text=msg_text, subject=sell_signal_subject)
    def next(self):
        for i, data in enumerate(self.datas):
            self.per_next(data)

    def prenext(self):
        logger.debug('prenext')

    def notify_order(self, order):
        pass

    def log(self, txt, dt=None):
        dt = dt or self.data.datetime[0]
        dt = bt.num2date(dt, tz=self.p.tz)
        logger.info('%s, %s' % (dt.isoformat(), txt))
    
    def stop(self):
        self.log('==================================================')
        self.log('Starting Value - %.2f' % self.broker.startingcash)
        self.log('Ending   Value - %.2f' % self.broker.getvalue())
        self.log('==================================================')

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))