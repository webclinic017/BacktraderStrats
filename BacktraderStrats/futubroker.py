#!/usr/bin/env python
from backtrader.metabase import MetaParams
from backtrader.comminfo import CommInfoBase
from backtrader.position import Position

from backtrader import BrokerBase
from backtrader.utils.py3 import with_metaclass
from futucomminfo import FutuCommInfo

import futustore
import collections

class MetaFutuBroker(BrokerBase.__class__):
    def __init__(cls, name, bases, dct):
        super(MetaFutuBroker, cls).__init__(name, bases, dct)
        print('MetaFutuBroker initialized...')
        futustore.FutuStore.BrokerCls = cls
    
class FutuBroker(with_metaclass(MetaFutuBroker, BrokerBase)):
    params = (
        ('use_positions', True),
        ('commission', FutuCommInfo)
    )

    def __init__(self, **kwargs):
        super(FutuBroker, self).__init__()

        self.futustore = futustore.FutuStore(**kwargs)
        self.orders = collections.OrderedDict()
        self.notifis = collections.deque()

        self.opending = collections.defaultdict(list)
        self.startingcash = self.cash = 0.0
        self.startingvalue = self.value = 0.0
        self.positions = collections.defaultdict(Position)
    
    def start(self):
        super(FutuBroker, self).start()
        self.futustore.start(broker=self)
        self.startingcash = self.cash = self.futustore.get_cash()
        self.startingvalue = self.value = self.futustore.get_value()