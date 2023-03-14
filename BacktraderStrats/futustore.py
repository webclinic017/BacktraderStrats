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
from logging.config import fileConfig

fileConfig('logging.conf')
logger = logging.getLogger()



class Streamer():
    last_time = None
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.quote_context = kwargs['quote_context'] 
        self.dataname = kwargs['dataname']
        self.trading_period = kwargs['trading_period']
        self.q = kwargs['q']
        self.sleep_sec = 10

    def connected(self):
        if (not futu_util.trade_context) or (not futu_util.quote_context):
            return False
        if futu_util.quote_context.status != ContextStatus.READY or futu_util.trade_context.status != ContextStatus.READY: 
            return False
        return True

    def stream(self):
        while self.connected():
            try:
                time.sleep(self.sleep_sec)
                ret, data = self.quote_context.get_cur_kline(self.dataname, 1, self.trading_period, autype=AuType.NONE)
                if ret == RET_OK:
                    cur_time = data['time_key'][0]
                    if cur_time != self.last_time: 
                        logger.info('try to put code %s data in queue %s' % (self.dataname, self.q))
                        # logger.info(data)
                        msg = {'data': data}    
                        self.q.put(msg)
                        logger.info('put code %s data in queue %s successfully' % (self.dataname, self.q))
                        self.last_time = cur_time
                else:
                    msg = {'code': ret, 'data': data}
                    logger.error(msg)
            except Exception as e:
                    logger.info('stream klines failed. msg: %s' % e)
        return



class OnBarClass(CurKlineHandlerBase):
    last_time = None

    def __init__(self, trading_period):
        super(OnBarClass, self).__init__()
        self.code_info_dict = dict()
        self.trading_period = trading_period

    def add_code(self, q, dataname):
        self.code_info_dict[dataname] = {'queue': q, 'datanames': dataname} 
        logger.info('add code info {} successfully'.format(self.code_info_dict[dataname])) 

    def on_bar_open(self, data):
        """_summary_

        Args:
            data (pd.DataFrame): [code, time_key, open, close, high, low, volume, turnover, pe_ratio, turnover_rate, last_close, k_type]
        """
        # logger.info('on bar open tick data: ')
        # logger.info(data)
        codes = data.code.drop_duplicates().tolist() 
        for code in codes:
            subdata = data[data.code == code]
            if code in self.code_info_dict:
                q = self.code_info_dict[code]['queue']
                logger.info('try to put code %s data in queue %s' % (code, q))
                msg = {'data': subdata}    
                q.put(msg)
                logger.info('put data in queue successfully')
    
    def put_err_msg(self, data, ret_code):
        msg = {'code': ret_code, 'data': data}
        logger.error(msg)

    def on_recv_rsp(self, rsp_pb):
        ret_code, data = super(OnBarClass, self).on_recv_rsp(rsp_pb)
        logger.info('on recv response...')
        logger.info(data)
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
        # self._bar_handler = OnBarClass(self.p.trading_period) 
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
    
    def streaming_events(self, tmout=None):
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
    

    def _t_streaming_prices(self, q, datanames):
        # futu context
        logger.info("sreaming_price process starting...")
        self.quote_context, self.trade_context = futu_util.open_context(host=self.p.host, port=self.p.port)
        self._bar_handler.add_code(q, datanames[0])
        self.quote_context.set_handler(self._bar_handler)

        try:
            logger.info('current subscription status :{}'.format(self.quote_context.query_subscription()))
            self.quote_context.subscribe(code_list=datanames, subtype_list=[SubType.TICKER, SubType.ORDER_BOOK, self.trading_period])
            logger.info('subscribe successfully！current subscription status: {}'.format(self.quote_context.query_subscription()))
        except Exception as e:
            self._state = self._ST_OVER
            logger.info("subscribe failed. msg: %s" % e)
            return
 
        logger.info("streaming_price process started...")

    def streaming_prices(self, datanames):
        q = queue.Queue()
        logger.info('create queue %s' % q)
        kwargs = {'q': q, 'datanames': datanames}
        logger.info('kwargs = {}'.format(kwargs))
        t = threading.Thread(target=self._t_streaming_prices, kwargs=kwargs)
        t.daemon = True
        t.start()
        return q

    def subscribe_klines(self, dataname):
        logger.info('streaming klines starting')
        self.quote_context, self.trade_context = futu_util.open_context(host=self.p.host, port=self.p.port)
        try:
            logger.info('current subscription status :{}'.format(self.quote_context.query_subscription()))
            self.quote_context.subscribe(code_list=[dataname], subtype_list=[SubType.TICKER, SubType.ORDER_BOOK, self.trading_period])
            logger.info('subscribe successfully！current subscription status: {}'.format(self.quote_context.query_subscription()))
        except Exception as e:
            self._state = self._ST_OVER
            logger.info("subscribe failed. msg: %s" % e)
            return
 
        logger.info("streaming klines process started successfully.")

    def _t_streaming_klines(self, q, dataname):
        streamer = Streamer(quote_context=self.quote_context, 
                            dataname=dataname, trading_period=self.trading_period,
                            q=q)
        streamer.stream()

    def streaming_klines(self, dataname):
        q = queue.Queue()
        logger.info('create queue %s' % q)
        kwargs = {'q': q, 'dataname': dataname}
        logger.info('kwargs = {}'.format(kwargs))
        t = threading.Thread(target=self._t_streaming_klines, kwargs=kwargs)
        t.daemon = True
        t.start()
        return q
       
    def get_cash(self):
        return self._cash
    
    def get_value(self):
        return self._value
    

