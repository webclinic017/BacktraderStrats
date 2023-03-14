import enum
import backtrader as bt
import datetime
import logging
from logging.config import fileConfig

fileConfig('logging.conf')
logger = logging.getLogger()


class TestStrategy(bt.Strategy):
    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime[0]
        dt = bt.num2date(dt)
        logger.info('%s, %s' % (dt.isoformat(), txt))
    
    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        logger.info("TestStrategy init")
        self.dataclose = dict()
        self.ema = dict()
        self.order = dict()
        # self.buyprice = dict()
        # self.buycomm = dict()
        for i, d in enumerate(self.datas):
            self.dataclose[d] = d.close 
            self.ema[d] = bt.talib.EMA(d, timeperiod=3)
            self.order[d] = None
            # self.buyprice[d] = None
            # self.buycomm[d] = None
        # self.dataclose = self.datas[0].close
        # self.ema = bt.talib.EMA(self.data, timeperiod=14)
        # self.order = None
        # self.buyprice = None
        # self.buycomm = None
    def prenext(self):
        logger.debug('prenext tick')

    def next(self):
        # for d in self.datas:
            # print('d = {}'.format(d))
        logger.debug('next tick')
        for i, d in enumerate(self.datas): 
            # if self.order[d]:
                # continue
            # Simply log the closing price of the series from the reference
            self.log('Code: %s, Close: %.2f' % (d._name, self.dataclose[d][0]))
            position = self.getposition(d).size
            if not position:
                if self.dataclose[d][0] > self.ema[d][0]:
                    # BUY, BUY, BUY!!! (with all possible default parameters)
                    # self.log('BUY CREATE, %.2f' % self.dataclose[0])
                    self.log("CODE = {}, BUY CREATE, {}, EMA = {}".format(d._name, self.dataclose[d][0], self.ema[d][0]))
                    self.order[d] = self.buy(data=d)
            else:
                # already in the market, try to sell
                if self.dataclose[d][0] < self.ema[d][0]:
                    # SELL, SELL, SELL!!! (with all possible default parameters)
                    # self.log('SELL CREATE, %.2f' % self.dataclose[0])
                    self.log("CODE = {}, SELL CREATE, {}, EMA = {}".format(d._name, self.dataclose[d][0], self.ema[d][0]))
                    # Keep track of the created order to avoid a 2nd order
                    self.order[d] = self.sell(data=d)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log('BUY EXECUTED, Code: %s , ' \
                         'Size: %d, Price: %.2f, CurrOpenPositionSize: %d, Cost: %.2f, Comm: %.4f'
                          % (order.data._name, order.size, 
                             order.executed.price, order.executed.psize, order.executed.value, 
                             order.executed.comm))
                # self.buyprice = order.executed.price
                # self.buycomm = order.executed.comm
            elif order.issell():
                # self.log('SELL EXECUTED, %.2f' % order.executed.price)
                self.log('SELL EXECUTED, Code: %s, ' \
                         'Size: %d, Price: %.2f, CurrentOpenPositionSize: %d, Cost: %.2f, Comm: %.2f' 
                         % (order.data._name, order.size, order.executed.price, order.executed.psize, 
                            order.executed.value, order.executed.comm))

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        # Write down: no pending order
        self.order[order.data] = None
    
    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))