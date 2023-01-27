import futu_util

from futu import *

code_list = ['HK.00700']

if __name__ == '__main__':
    futu_util.open_context()
    ret, data = futu_util.quote_context.subscribe(code_list=code_list, subtype_list=[KLType.K_1M]) 
    print('subscribe ret: %d' % ret)
    print('subscribe msg: %s ' % data)
    futu_util.quote_context.set_handler(futu_util.OnBarClass(KLType.K_1M))
    # futu_util.close_context()