import backtrader as bt
import backtrader.feeds as btfeeds

from futustore import FutuStore
from futudata import FutuData
from teststrat import TestStrategy

def runstrat():
    cerebro = bt.Cerebro()
    futustore = FutuStore()
    DataFactory = FutuData
    dataname = ['HK.00700']
    data0 = DataFactory(dataname=dataname)
    cerebro.adddata(data0, name=dataname[0])
    cerebro.addstrategy(TestStrategy)
    results = cerebro.run()

if __name__ == '__main__':
    runstrat()
