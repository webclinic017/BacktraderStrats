import datetime
import logging

import backtrader as bt
from backtrader.feed import DataBase
from backtrader import TimeFrame, date2num, num2date
from backtrader.utils.py3 import (integer_types, queue, string_types,
                                  with_metaclass)
from backtrader.metabase import MetaParams
from futu import *
import futustore

from logging.config import fileConfig

fileConfig('logging.conf')
logger = logging.getLogger()

class MetaFutuData(DataBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaFutuData, cls).__init__(name, bases, dct)
        # logger.info(name, bases, dct)
        # Register with the store
        futustore.FutuStore.DataCls = cls

class FutuData(with_metaclass(MetaFutuData, DataBase)):
    params = (
        ('qcheck', 0.5),
        ('reconnections', 3)
    )
    _store = futustore.FutuStore 
    # States for the Finite State Machine in _load
    _ST_FROM, _ST_START, _ST_LIVE, _ST_HISTORBACK, _ST_OVER = range(5)

    # autoregister
    DataCls = None


    def __init__(self, **kwargs):
        logger.info("futudata init...")
        self.futustore = self._store(**kwargs)
        logger.info('futustore initialized: {}'.format(self.futustore))
        logger.info("params = {}".format(self.p))

    def islive(self):
        return True

    def start(self):
        super(FutuData, self).start()
        self.futustore.start(data=None) 
        self.qlive = queue.Queue()
        self._storedmsg = dict()
        self._statelivereconn = False
        self._state = self._ST_OVER
        self._reconns = 0
        # if not self.futustore.connected():
            # return
        self._st_start()
        self.put_notification(self.CONNECTED)
    
    def _st_start(self, instart=True, tmout=None):
        # TODO: maybe open_context should put in this part not in connected
        # and about connected, need to try to find a way to check context's status
        if not self.futustore.connected():
            # TODO
            pass
        #     if not self.futustore.reconnect():
        #         self._state = self._ST_OVERE
        #         self.push_notification(self.DISCONNECTED)
        logger.info('futudata _st_start...')
        # self.qlive = self.futustore.streaming_prices([self.p.dataname])
        self.futustore.subscribe_klines(self.p.dataname)
        self.qlive = self.futustore.streaming_klines(self.p.dataname)
        logger.info('data {} live queue is {}'.format(self.p.dataname, self.qlive))
        if self._statelivereconn:
            self.put_notification(self.DELAYED)

        self._state = self._ST_LIVE
        if instart:
            self._reconns = self.p.reconnections
        logger.info('futudata state trans done. state: %s' % self._state)
        return True

    def stop(self):
        super(FutuData, self).stop()
        self.futustore.stop()

    def reqdata(self):
        pass

    def _load(self):
        # logger.info('futudata _load...')
        if self._state == self._ST_OVER:
            return False

        while True:
            # logger.info('_load state: %s' % self._state)
            if self._state == self._ST_LIVE:
                try:
                    # logger.info('try to pop up msg from queue %s' % self.qlive)
                    msg = (self._storedmsg.pop(None, None) or
                           self.qlive.get(timeout=self._qcheck))
                    # logger.info('_load popup msg %s ' % msg)
                except queue.Empty:
                    return None
                if 'code' in msg:
                    self.put_notification(self.CONNBROKEN)
                    if not self.p.reconnect or self._reconns == 0:
                        # Can no longer reconnect
                        self.put_notification(self.DISCONNECTED)
                        self._state = self._ST_OVER
                        return False  # failed

                    # Can reconnect
                    self._reconns -= 1
                    self._st_start(instart=False, tmout=self.p.reconntimeout)
                    continue

                if not self._statelivereconn:
                    if self._laststatus != self.LIVE:
                        if self.qlive.qsize() <= 1:  # very short live queue
                            self.put_notification(self.LIVE)
                    ret = self._load_tick(msg)
                    if ret:
                        return True

                    # could not load bar ... go and get new one
                    continue
            elif self._state == self._ST_START:
                if not self._st_start(instart=False):
                    self._state = self._ST_OVER
                    return False

            
    def _load_tick(self, msg):
        """_summary_

        Args:
            msg (pd.DataFrame): [code, time_key, open, close, high, low, volume, turnover, pe_ratio, turnover_rate, last_close, k_type]

        """
        data = msg['data']
        logger.debug('data:')
        logger.debug(data)
        dtobj = datetime.strptime(data['time_key'][0], "%Y-%m-%d %H:%M:%S") 
        dt = date2num(dtobj)
        if dt <= self.lines.datetime[-1]:
            return False  # time already seen
        # get data by code
        data = data[data.code == self.p.dataname]
        if data.empty:
            return False

        # # Common fields
        self.lines.datetime[0] = dt
        self.lines.volume[0] = data['volume'][0]
        self.lines.openinterest[0] = 0.0

        # # Put the prices into the bar
        # tick = float(msg['ask']) if self.p.useask else float(msg['bid'])
        self.lines.open[0] = data['open'][0]
        self.lines.high[0] = data['high'][0]
        self.lines.low[0] = data['low'][0]
        self.lines.close[0] = data['close'][0]

        logger.info('load tick successfully')
        return True
