import backtrader as bt
import backtrader.feeds as btfeeds
import logging
import datetime
from datetime import timedelta
from collections import OrderedDict
from futu import *
from futudata import FutuData
from futucomminfo import FutuCommInfo
from teststrat import TestStrategy
from jam_momentum_one_strat import MultiStochRSIMacdCompStrategy
from logging.config import fileConfig

fileConfig('logging.conf')
logger = logging.getLogger()

def get_indicator_params():
    params = {
        "default": {
            "fastk_period": 10,
            "slowk_period": 3,
            "slowd_period": 3,
            "fastd_period": 3,
            "slowk_matype": 0,
            "slowd_matype": 0,
            "fastd_matype": 0,
            "rsi_period": 10
        },
        "HK.03606": {
            "fastk_period": 10,
            "slowk_period": 3,
            "slowd_period": 3,
            "fastd_period": 3,
            "slowk_matype": 0,
            "slowd_matype": 0,
            "fastd_matype": 0,
            "rsi_period": 10
        },
        "HK.01316": {
            "fastk_period": 7,
            "slowk_period": 3,
            "slowd_period": 3,
            "fastd_period": 3,
            "slowk_matype": 0,
            "slowd_matype": 0,
            "fastd_matype": 0,
            "rsi_period": 5
        },
        "HK.00241": {
            "fastk_period": 7,
            "slowk_period": 3,
            "slowd_period": 3,
            "fastd_period": 3,
            "slowk_matype": 0,
            "slowd_matype": 0,
            "fastd_matype": 0,
            "rsi_period": 5
        },
        "HK.01209": {
            "fastk_period": 7,
            "slowk_period": 3,
            "slowd_period": 3,
            "fastd_period": 3,
            "slowk_matype": 0,
            "slowd_matype": 0,
            "fastd_matype": 0,
            "rsi_period": 5
        },
    }
    return params

def runstrat():
    cerebro = bt.Cerebro()
    DataFactory = FutuData
    dataname1 = 'HK.01316'
    dataname0 = 'HK.03606'
    # dataname1 = 'HK.00700'
    start_time = datetime.now() - timedelta(days=60) 
    start_time = start_time.strftime('%Y-%m-%d')
    data0 = DataFactory(dataname=dataname0, trading_period=KLType.K_DAY, start_time=start_time)
    logger.info('data0 feed created successfully: {}'.format(data0))
    cerebro.adddata(data0, name=dataname0)
    data1 = DataFactory(dataname=dataname1, trading_peiord=KLType.K_DAY, start_time=start_time)
    logger.info('data1 feed created successfully: {}'.format(data1))
    cerebro.adddata(data1, name=dataname1)
    stock_codes = ['HK.01316', 'HK.03606']
    # stock_codes = ['HK.01316']
    stakes = {
        'HK.01316': 1000,
        'HK.03606': 400
    }
    stakes = OrderedDict(stakes)
    ind_periods = OrderedDict(get_indicator_params())
    strat_params = dict(stakes=stakes, fastk_period=7, 
                        rsi_period=5, stop_loss=0.6, ind_periods=ind_periods)
    cerebro.addstrategy(MultiStochRSIMacdCompStrategy, **strat_params)
    cerebro.broker.setcash(45000)
    futu_comminfo = FutuCommInfo(commission=0.0003)
    cerebro.broker.addcommissioninfo(futu_comminfo)
    
    results = cerebro.run()

if __name__ == '__main__':

    runstrat()
