import backtrader as bt
import backtrader.feeds as btfeeds
import logging
from futustore import FutuStore
from futudata import FutuData
from teststrat import TestStrategy

from logging.config import fileConfig

fileConfig('logging.conf')
logger = logging.getLogger()

def runstrat():
    cerebro = bt.Cerebro()
    futustore = FutuStore()
    DataFactory = FutuData
    dataname0 = 'HK.00700'
    dataname1 = 'HK.03606'
    data0 = DataFactory(dataname=dataname0)
    logger.info('data0 feed created successfully: {}'.format(data0))
    cerebro.adddata(data0, name=dataname0)
    data1 = DataFactory(dataname=dataname1)
    logger.info('data1 feed created successfully: {}'.format(data1))
    cerebro.adddata(data1, name=dataname1)
    cerebro.addstrategy(TestStrategy)
    results = cerebro.run()

if __name__ == '__main__':
    runstrat()
