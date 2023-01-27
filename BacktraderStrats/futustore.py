import threading
import collections
import random
import itertools
import time
import futu_util

from backtrader.metabase import MetaParams
from backtrader.utils.py3 import bytes, bstr, queue, with_metaclass, long
from backtrader import TimeFrame, Position
from datetime import date, datetime, timedelta
from backtrader.utils import AutoDict, UTC
from futu import *


class OnBarClass(CurKlineHandlerBase):
    last_time = None
    
    def __init__(self, q, trading_period, datanames):
        super(OnBarClass, self).__init__()
        self.trading_period = trading_period
        self.q = q
        print('assigned q: %s ' % self.q)
        self.datanames = datanames
        print('period = %s' % self.trading_period)
        print('datanames = %s' % self.datanames)

    def on_bar_open(self, data):
        """_summary_

        Args:
            data (pd.DataFrame): [code, time_key, open, close, high, low, volume, turnover, pe_ratio, turnover_rate, last_close, k_type]
        """
        msg = {'data': data}
        print('try to put data in queue %s' % self.q)
        self.q.put(msg)
        print('on_bar_open...')
        print(data) 
    
    def put_err_msg(self, data, ret_code):
        msg = {'code': ret_code, 'data': data}
        self.q.put(msg)
        print(msg)

    def on_recv_rsp(self, rsp_pb):
        ret_code, data = super(OnBarClass, self).on_recv_rsp(rsp_pb)
        # print('on recv response...')
        if ret_code == RET_OK:
            cur_time = data['time_key'][0]
            if cur_time != self.last_time and data['k_type'][0] == self.trading_period:
                if self.last_time is not None:
                    self.on_bar_open(data)
                self.last_time = cur_time
            return data
        else:
            self.put_err_msg(data, ret_code)


class MetaSingleton(MetaParams):
    '''Metaclass to make a metaclassed class a singleton'''
    def __init__(cls, name, bases, dct):
        super(MetaSingleton, cls).__init__(name, bases, dct)
        cls._singleton = None

    def __call__(cls, *args, **kwargs):
        if cls._singleton is None:
            cls._singleton = (
                super(MetaSingleton, cls).__call__(*args, **kwargs))

        return cls._singleton

class FutuStore(with_metaclass(MetaSingleton, object)):
    params = (
        ('host', '127.0.0.1'),
        ('port', 11111),
        ('notifyall', False),
        ('_debug', False),
        ('trading_period', KLType.K_1M),
        ('reconnect', 3),  # -1 forever, 0 No, > 0 number of retries
        ('timeout', 3.0),  # timeout between reconnections
    )

    DataCls = None
    @classmethod
    def getdata(cls, *args, **kwargs):
        '''Returns ``DataCls`` with args, kwargs'''
        return cls.DataCls(*args, **kwargs)

    @classmethod
    def getbroker(cls, *args, **kwargs):
        '''Returns broker with *args, **kwargs from registered ``BrokerCls``'''
        return cls.BrokerCls(*args, **kwargs)

    def __init__(self):
        super(FutuStore, self).__init__()
        
        self._lock_q = threading.Lock()  # sync access to _tickerId/Queues
        self._lock_accupd = threading.Lock()  # sync account updates
        self._lock_pos = threading.Lock()  # sync account updates
        self._lock_notif = threading.Lock()  # sync access to notif queue

        # Account list received
        # self._event_managed_accounts = threading.Event()
        # self._event_accdownload = threading.Event()

        self.dontreconnect = False  # for non-recoverable connect errors
        self.trading_period = self.p.trading_period
        self._env = None  # reference to cerebro for general notifications
        self.broker = None  # broker instance
        self.datas = list()  # datas that have registered over start
        self.ccount = 0  # requests to start (from cerebro or datas)

        self._lock_tmoffset = threading.Lock()
        self.tmoffset = timedelta()  # to control time difference with server

        # Structures to hold datas requests
        self.qs = collections.OrderedDict()  # key: tickerId -> queues
        self.ts = collections.OrderedDict()  # key: queue -> tickerId
        self.iscash = dict()  # tickerIds from cash products (for ex: EUR.JPY)

        self.histexreq = dict()  # holds segmented historical requests
        self.histfmt = dict()  # holds datetimeformat for request
        self.histsend = dict()  # holds sessionend (data time) for request
        self.histtz = dict()  # holds sessionend (data time) for request

        self.acc_cash = AutoDict()  # current total cash per account
        self.acc_value = AutoDict()  # current total value per account
        self.acc_upds = AutoDict()  # current account valueinfos per account

        self.port_update = False  # indicate whether to signal to broker

        self.positions = collections.defaultdict(Position)  # actual positions

        self.orderid = None  # next possible orderid (will be itertools.count)

        self.cdetails = collections.defaultdict(list)  # hold cdetails requests

        self.managed_accounts = list()  # received via managedAccounts

        self.notifs = queue.Queue()  # store notifications for cerebro

        self.quote_context = None
        self.trade_context = None

        self._cash = 0.0
        self._value = 0.0

        def keyfn(x):
            n, t = x.split()
            tf, comp = self._sizes[t]
            return (tf, int(n) * comp)

        # This utility key function transforms a duration into a:
        #   (Timeframe, Compression) tuple which can be sorted
        def key2fn(x):
            n, d = x.split()
            tf = self._dur2tf[d]
            return (tf, int(n))

        # Generate a table of reverse durations
        self.revdur = collections.defaultdict(list)
        # The table (dict) is a ONE to MANY relation of
        #   duration -> barsizes
        # Here it is reversed to get a ONE to MANY relation of
        #   barsize -> durations
        # for duration, barsizes in self._durations.items():
        #     for barsize in barsizes:
        #         self.revdur[keyfn(barsize)].append(duration)

        # Once managed, sort the durations according to real duration and not
        # to the text form using the utility key above
        # for barsize in self.revdur:
        #     self.revdur[barsize].sort(key=key2fn)
    
    def streaming_events(slef, tmout=None):
        q = queue.Queue()
        kwargs = {'q': q, 'tmout': tmout}

        tlistener = threading.Thread(target=self._t_streaming_listener, kwargs=kwargs)
        tlistener.daemon = True
        tlistener.start()

        tevent = threading.Thread(target=self._t_streaming_events, kwargs=kwargs)
        tevent.daemon = True
        tevent.start()
        return q
      
    def _t_streaming_listener(self, q, tmout=None):
        pass


    def _t_streaming_events(self, q, tmout=None):
        pass

    def start(self, data=None, broker=None):
        # self.reconnect()
        if data is None and broker is None:
            self.cash = None
            return
        # Datas require some processing to kickstart data reception
        if data is not None:
            self._env = data._env
            # For datas simulate a queue with None to kickstart co
            self.datas.append(data)

            # if connection fails, get a fake registration that will force the
            # datas to try to reconnect or else bail out
            # return self.getTickerQueue(start=True)

        elif broker is not None:
            self.broker = broker
            

    def connected(self):
        if (not futu_util.trade_context) or (not futu_util.quote_context):
            return False
        if futu_util.quote_context.status != ContextStatus.READY or futu_util.trade_context.status != ContextStatus.READY: 
            return False
        return True

    def reconnect(self):
        first_connect = False
        if self.connected():
            # connected, nothing to do 
            return True
        retries = self.p.reconnect
        retries += 1
        while retries > 0:
            try:
                if not first_connect:
                    time.sleep(self.p.timeout)
                else:
                    first_connect = False
                # TODO
                # self.quote_context, self.trade_context = futu_util.open_context(host=self.p.host, port=self.p.port)
                return True
            except:
                retries -= 1
        return False

    def stop(self):
        if self.connected():
            futu_util.close_context()
        return True
    
    # def _receive(self, q):
    #     self.quote_context.set_handler(futu_util.OnBarClass(q, self.trading_period))

    # def receive(self):
    #     q = queue.Queue()
    #     print('trading period is %s ' % self.trading_period)
    #     kwargs = {'queue': q}
    #     t = threading.Thread(target=self._receive, kwargs=kwargs)
    #     t.daemon = True
    #     t.start()

    def _t_streaming_prices(self, q, trading_period, datanames):
        # futu context
        print("sreaming_price process starting...")
        self.quote_context, self.trade_context = futu_util.open_context(host=self.p.host, port=self.p.port)
        self.quote_context.set_handler(OnBarClass(q, trading_period, datanames))
        try:
            self.quote_context.subscribe(code_list=datanames, subtype_list=[SubType.TICKER, SubType.ORDER_BOOK, trading_period])
        except Exception as e:
            self._state = self._ST_OVER
            print("subscribe failed. msg: %s" % e)
            return
 
        print("streaming_price process started...")

    def streaming_prices(self, datanames):
        q = queue.Queue()
        print('create queue %s' % q)
        kwargs = {'q': q, 'trading_period': self.trading_period, 'datanames': datanames}
        print('kwargs = {}'.format(kwargs))
        t = threading.Thread(target=self._t_streaming_prices, kwargs=kwargs)
        t.daemon = True
        t.start()
        return q

    def get_cash(self):
        return self._cash
    
    def get_value(self):
        return self._value
    # def getTickerQueue(self, start=False):
    #     '''Creates ticker/Queue for data delivery to a data feed'''
    #     q = queue.Queue()
    #     if start:
    #         q.put(None)
    #         return q

    #     with self._lock_q:
    #         tickerId = self.nextTickerId()
    #         self.qs[tickerId] = q  # can be managed from other thread
    #         self.ts[q] = tickerId
    #         self.iscash[tickerId] = False

    #     return tickerId, q

    

