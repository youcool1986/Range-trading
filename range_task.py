from trade_api import Order_type_class
from non_trade_api import Non_trade
from active_order import run_func
import pandas as pd
import time
from input import Range_trade
import trade_api as t_api
from datetime import datetime
from retrying import retry

trade_api = t_api.Trade
order_api = Order_type_class

@retry(stop_max_attempt_number=5, wait_fixed=2000)
def read_data(test_real, Accs):
    try:
        df = pd.read_excel(test_real)
    except Exception as e:
        print(f"读取 Excel 文件时出错：{e}")
        exit()

    df.set_index("Acc_Name", inplace=True)
    accs_info = {}

    for acc_name in Accs:
        try:
            api_key = df.loc[acc_name, "Api_key"]
            api_secret = df.loc[acc_name, "Api_secret"]
            accs_info[acc_name] = {"Api_key": api_key, "Api_secret": api_secret}
        except KeyError:
            print(f"无法找到 Acc_Name 为 {acc_name} 的信息。")

    return accs_info

@retry(stop_max_attempt_number=5, wait_fixed=2000)
def trading_session(acc_name, accs_info):
    trade_session = trade_api(acc_name, accs_info['Api_key'], accs_info['Api_secret'])
    order_session = Order_type_class(acc_name, accs_info['Api_key'], accs_info['Api_secret'])

    return trade_session,order_session

def init_func():
    print("init_func\n")
    init = {
            "open_position_order": {"orderID": None, "order_status": None,"traded_p": None ,"qty": None},
            "close_position_order": {"orderID": None, "order_status": None,"traded_p": None,"qty": None},
            "cut_loss_order": {"orderID": None, "order_status": None,"traded_p": None, "qty": None}
            }

    update_order_status = "init"
    next_action =  "no_position"
    return init , update_order_status,next_action

def scoure_broad_func(orders_status_dic):

    print("scoure_broad_func\n")
    print(f"orders_status_dic:{orders_status_dic}")
    open_posit_p = orders_status_dic["open_position_order"]['traded_p']
    close_posit_p = orders_status_dic["close_position_order"]['traded_p']
    cut_posit_p = orders_status_dic["cut_loss_order"]['traded_p']
    open_posit_qty = orders_status_dic["open_position_order"]['qty']
    close_posit_qty = orders_status_dic["close_position_order"]['qty']
    cut_posit_qty = orders_status_dic["cut_loss_order"]['qty']

    open_posit_p = 0 if open_posit_p is None else open_posit_p
    close_posit_p = 0 if close_posit_p is None else close_posit_p
    cut_posit_p = 0 if cut_posit_p is None else cut_posit_p
    open_posit_qty = 0 if open_posit_qty is None else open_posit_qty
    close_posit_qty = 0 if close_posit_qty is None else close_posit_qty
    cut_posit_qty = 0 if cut_posit_qty is None else cut_posit_qty

    if orders_status_dic["close_position_order"]["order_status"] == "Filled":

        P_n_L = (close_posit_p * close_posit_qty) -(open_posit_p * open_posit_qty)
        print("calculate the positive result")

    elif orders_status_dic["cut_loss_order"]["order_status"] == "Filled":
        P_n_L = (close_posit_p * close_posit_qty) -(cut_posit_p * cut_posit_qty)
        print("calculate the negative  result")
    else:
        P_n_L = 0
    print()
    return P_n_L

def is_within_time_range_func(start_time_str, end_time_str):
    print("is_within_time_range_func")
    # 定义时间格式
    time_format = "%d/%m/%Y, %H:%M"

    # 将字符串转换为 datetime 对象
    start_time = datetime.strptime(start_time_str, time_format)
    end_time = datetime.strptime(end_time_str, time_format)

    # 获取当前时间
    current_time = datetime.now()

    # 判断当前时间是否在开始时间和结束时间之间
    if start_time <= current_time <= end_time:
        within_time = True

    else:
        within_time = False

    return within_time

def time_break_func():
    print("time_break_func\n")
    return time.sleep(5)

@retry(stop_max_attempt_number=100, wait_fixed=2000)
def define_order_status_func(orderID):
    print("define_order_status_func\n")
    print(f"orderID:{orderID}")
    check_new_orders = order_session.check_specific_orders_func(orderID)
    if check_new_orders['result']['list'] != []:
        order_status = check_new_orders["result"]["list"][0]["orderStatus"]

    else:
        check_old_orders = order_session.check_old_orders_func(orderID)
        order_status = check_old_orders["result"]["list"][0]["orderStatus"]
    # print(f"old_order_status:{old_order_status}")
    return order_status

@retry(stop_max_attempt_number=100, wait_fixed=2000)
def update_orders_dic_func(init,orders_status_dic, update_order_status , order_status ,orderID,traded_p,qty ):
    print("update_orders_dic_func\n")
    print("bug0:orders_status_dic:", orders_status_dic)
    if update_order_status == "open_position":
        print("open_position")
        orders_status_dic["open_position_order"]["orderID"] = orderID
        orders_status_dic["open_position_order"]["order_status"] = order_status
        orders_status_dic["open_position_order"]["traded_p"] = traded_p
        orders_status_dic["open_position_order"]["qty"] = qty

    elif update_order_status == "close_position":
        print("close_position")
        orders_status_dic["close_position_order"]["orderID"] = orderID
        orders_status_dic["close_position_order"]["order_status"] = order_status
        orders_status_dic["close_position_order"]["traded_p"] = traded_p
        orders_status_dic["close_position_order"]["qty"] = qty

    elif update_order_status == "cut_loss":
        print("cut_loss")
        orders_status_dic["cut_loss_order"]["orderID"] = orderID
        orders_status_dic["cut_loss_order"]["order_status"] = order_status
        orders_status_dic["cut_loss_order"]["traded_p"] = traded_p
        orders_status_dic["cut_loss_order"]["qty"] = qty

    elif update_order_status == "init":
        orders_status_dic = init
    P_n_L = scoure_broad_func(orders_status_dic)
    return orders_status_dic, P_n_L

@retry(stop_max_attempt_number=100, wait_fixed=2000)
def update_order_data_func(orderID,init,orders_status_dic, update_order_status,traded_p,qty ):
    print("update_order_data_func\n")
    order_status = define_order_status_func(orderID)
    orders_status_dic, P_n_L = update_orders_dic_func(init,orders_status_dic, update_order_status , order_status ,orderID,traded_p,qty )

    return orders_status_dic , P_n_L

@retry(stop_max_attempt_number=100, wait_fixed=2000)
def CP_greater_TBP_func(range_trade_list,init,orders_status_dic, coin_symbol,TBP,side,capital_ratio, p, order_type,start_time_str,end_time_str,update_order_status):
    print("CP_greater_TBP_func\n")
    while True:
        within_time = is_within_time_range_func(start_time_str, end_time_str)
        CP = Non_trade().get_current_coin_price(coin_symbol)
        time.sleep(5)

        if CP > TBP and within_time == True:

            print(f"現價：{CP}大於觸發價：{TBP},等待建倉：等待跌穿{TBP}")

        elif CP <= TBP and within_time == True:
            print(f"現價：{CP}跌穿觸發價：{TBP}，建倉！！")

            flat_order = False
            trade_list = run_func(trade_session,coin_symbol, flat_order, side, order_type, p, capital_ratio)
            orderID = [trade['orderID'] for trade in trade_list if 'orderID' in trade]
            orderID = orderID[0]
            print(f"orderID:{orderID}")
            update_order_status = "open_position"
            traded_p = [trade['p'] for trade in trade_list if 'p' in trade]
            traded_p = traded_p[0]
            print(f"traded_p:{traded_p}")
            traded_qty = [trade['qty'] for trade in trade_list if 'qty' in trade]
            traded_qty = traded_qty[0]
            print(f"traded_qty:{traded_qty}")
            orders_status_dic, P_n_L = update_order_data_func(orderID, init, orders_status_dic, update_order_status,traded_p,traded_qty)
            print(f"orders_status_dic:{orders_status_dic}")
            range_trade_list.append(orders_status_dic)
            next_action = "has_position"
            break

        else:
            next_action = "time_out"
            P_n_L = 0
            break

    return next_action ,update_order_status,orders_status_dic,range_trade_list, P_n_L

@retry(stop_max_attempt_number=100, wait_fixed=2000)
def CP_smaller_TBP(range_trade_list,init,orders_status_dic, coin_symbol,TBP,side,capital_ratio, p, order_type,start_time_str, end_time_str,update_order_status):
    print("CP_smaller_TBP\n")
    while True:
        within_time = is_within_time_range_func(start_time_str, end_time_str)
        CP = Non_trade().get_current_coin_price(coin_symbol)
        time.sleep(5)
        if CP < TBP and within_time == True:

            print(f"現價：{CP}小於觸發價：{TBP},等待建倉：等待升穿{TBP}")

        elif CP >= TBP and within_time == True:
            print(f"現價：{CP}升穿觸發價：{TBP}，建倉！！")

            flat_order = False
            trade_list = run_func(trade_session,coin_symbol, flat_order, side, order_type, p, capital_ratio)
            orderID = [trade['orderID'] for trade in trade_list if 'orderID' in trade]
            orderID = orderID[0]
            print(f"orderID:{orderID}")
            update_order_status = "open_position"
            traded_p = [trade['p'] for trade in trade_list if 'p' in trade]
            traded_p = traded_p[0]
            traded_qty = [trade['qty'] for trade in trade_list if 'qty' in trade]
            traded_qty = traded_qty[0]
            orders_status_dic, P_n_L = update_order_data_func(orderID, init, orders_status_dic, update_order_status, traded_p,traded_qty)
            print(f"orders_status_dic:{orders_status_dic}")
            range_trade_list.append(orders_status_dic)
            next_action = "has_position"
            break

        else:
            next_action = "time_out"
            P_n_L = 0
            break

    return next_action ,update_order_status,orders_status_dic,range_trade_list, P_n_L

@retry(stop_max_attempt_number=100, wait_fixed=2000)
def no_stock_func(range_trade_list,init,orders_status_dic,coin_symbol,TBP,side, capital_ratio, p, order_type,start_time_str, end_time_str,update_order_status):
    print("no_stock_func\n")

    CP = Non_trade().get_current_coin_price(coin_symbol)
    time.sleep(5)

    if CP >= TBP:

        next_action ,update_order_status,orders_status_dic,range_trade_list, P_n_L = CP_greater_TBP_func(range_trade_list,init,orders_status_dic, coin_symbol,
                                                                                                  TBP,side,capital_ratio, p, order_type,start_time_str, end_time_str,update_order_status)

    else:

        next_action ,update_order_status,orders_status_dic,range_trade_list, P_n_L = CP_smaller_TBP(range_trade_list,init,orders_status_dic, coin_symbol,
                                                                                             TBP,side,capital_ratio, p, order_type,start_time_str, end_time_str,update_order_status)

    return next_action ,update_order_status,orders_status_dic,range_trade_list, P_n_L

def flat_order_set(flat_p):

    flat_order = True
    capital_ratio = 100
    order_type = "Limit"

    return flat_order,capital_ratio,order_type,flat_p

@retry(stop_max_attempt_number=5, wait_fixed=2000)
def flat_position_func(range_trade_list,break_button,init,CP,coin_symbol,side,order_type,flat_p,orders_status_dic,next_action):
    print("flat_position_func\n")
    print(f"flat_p:{flat_p},order_type:{order_type}")
    open_posit_orderID = orders_status_dic["open_position_order"]['orderID']
    close_posit_orderID = orders_status_dic["close_position_order"]['orderID']
    open_posit_p = orders_status_dic["open_position_order"]['traded_p']
    close_posit_p = orders_status_dic["close_position_order"]['traded_p']
    open_posit_qty = orders_status_dic["open_position_order"]['qty']
    close_posit_qty = orders_status_dic["close_position_order"]['qty']
    P_n_L = None

    print(f"orders_status_dic:{orders_status_dic}")
    if orders_status_dic["open_position_order"]["order_status"] == "Filled" \
            and orders_status_dic["close_position_order"]["order_status"] == None \
            and orders_status_dic["cut_loss_order"]["order_status"] == None:

        print("flat1")
        range_trade_list.append(orders_status_dic)
        print(f"range_trade_list:{range_trade_list}")
        flat_order,capital_ratio,order_type,flat_p = flat_order_set(flat_p)
        trade_list = run_func(trade_session,coin_symbol, flat_order, side, order_type, flat_p, capital_ratio)
        orderID = [trade['orderID'] for trade in trade_list if 'orderID' in trade]
        orderID = orderID[0]
        close_posit_orderID = orderID
        traded_p = [trade['p'] for trade in trade_list if 'p' in trade]
        traded_p = traded_p[0]
        update_order_status = "close_position"
        traded_qty = [trade['qty'] for trade in trade_list if 'qty' in trade]
        traded_qty = traded_qty[0]
        orders_status_dic, P_n_L = update_order_data_func(orderID, init, orders_status_dic, update_order_status, traded_p,
                                                   traded_qty)
        range_trade_list.append(orders_status_dic)
        print(f"range_trade_list:{range_trade_list}")
        print(f"開倉盤已成交，投放結倉盤{close_posit_orderID}")

    elif orders_status_dic["open_position_order"]["order_status"] == "New" \
            and orders_status_dic["close_position_order"]["order_status"] == None \
            and orders_status_dic["cut_loss_order"]["order_status"] == None:

        print("flat2")
        update_order_status = "open_position"
        orders_status_dic, P_n_L = update_order_data_func(open_posit_orderID, init, orders_status_dic, update_order_status,open_posit_p,open_posit_qty)
        print(f"現價是{CP}，等待到買盤：{open_posit_orderID}成交")

    elif orders_status_dic["open_position_order"]["order_status"] == "Filled" \
            and orders_status_dic["close_position_order"]["order_status"] == "Filled" \
            and orders_status_dic["cut_loss_order"]["order_status"] == None:
        print("flat3")
        print(f"已經成功完成一個交易")
        range_trade_list.append(orders_status_dic)
        print(f"range_trade_list:{range_trade_list}")
        next_action = "no_position"
        break_button = True

    elif orders_status_dic["open_position_order"]["order_status"] == "Filled" \
            and orders_status_dic["close_position_order"]["order_status"] == "New" \
            and orders_status_dic["cut_loss_order"]["order_status"] == None:

        print("flat4")
        update_order_status = "close_position"
        orders_status_dic, P_n_L = update_order_data_func(close_posit_orderID, init, orders_status_dic, update_order_status,close_posit_p,close_posit_qty)
        print(f"現價是{CP}，等待到賣盤：{close_posit_orderID},成交")

    return break_button, next_action , orders_status_dic,range_trade_list, P_n_L

@retry(stop_max_attempt_number=100, wait_fixed=2000)
def cut_lose_order_set_func():
    flat_order = True
    capital_ratio = 100
    order_type = "Market"

    return flat_order,capital_ratio,order_type

def cut_lose_func(range_trade_list,init,orders_status_dic ,coin_symbol, side , p,CL,CP,next_action):
    print("cut_lose_func\n")
    print(f"orders_status_dic:{orders_status_dic}")
    open_posit_p = orders_status_dic["open_position_order"]["traded_p"]
    close_posit_p = orders_status_dic["close_position_order"]["traded_p"]
    open_posit_qty = orders_status_dic["open_position_order"]['qty']
    close_posit_qty = orders_status_dic["close_position_order"]['qty']
    P_n_L = 0

    if orders_status_dic["open_position_order"]["order_status"]== "New" \
            and orders_status_dic["close_position_order"]["order_status"] == None \
            and orders_status_dic["cut_loss_order"]["order_status"] == None:

        print("cut1")
        trade_data = trade_session.cancel_order(coin_symbol, orders_status_dic["open_position_order"]["orderID"])

        open_posit_orderID =  trade_data["orderId"]
        update_order_status = "open_position"
        orders_status_dic, P_n_L = update_order_data_func(open_posit_orderID, init, orders_status_dic, update_order_status,open_posit_p,open_posit_qty)
        range_trade_list.append(orders_status_dic)
        print(f"range_trade_list:{range_trade_list}")
        next_action = "no_position"
        print(f"止蝕價{CL}>現價是{CP}，還沒成交：取消買單",trade_data["orderId"])


    elif orders_status_dic["open_position_order"]["order_status"]== "Filled" \
            and orders_status_dic["close_position_order"]["order_status"] == "New" \
            and orders_status_dic["cut_loss_order"]["order_status"] == None:

        print("cut2")
        flat_order, capital_ratio, order_type = cut_lose_order_set_func()
        trade_list = run_func(trade_session,coin_symbol, flat_order, side, order_type, p, capital_ratio)
        orderID = [trade['orderID'] for trade in trade_list if 'orderID' in trade]
        orderID = orderID[0]
        cut_posit_orderID = orderID
        update_order_status = "cut_loss"
        traded_qty = [trade['qty'] for trade in trade_list if 'qty' in trade]
        traded_qty = traded_qty[0]
        orders_status_dic, P_n_L = update_order_data_func(cut_posit_orderID, init, orders_status_dic, update_order_status, CP,
                                                   traded_qty)

        range_trade_list.append(orders_status_dic)
        print(f"range_trade_list:{range_trade_list}")

        trade_data = trade_session.cancel_order(coin_symbol, orders_status_dic["close_position_order"]["orderID"])
        print(f"trade_data:{trade_data}")
        close_posit_orderID = trade_data["orderId"]
        update_order_status = "close_position"
        orders_status_dic, P_n_L = update_order_data_func(close_posit_orderID, init, orders_status_dic, update_order_status,close_posit_p,close_posit_qty)
        range_trade_list.append(orders_status_dic)
        print(f"range_trade_list:{range_trade_list}")
        next_action = "no_position"
        print(f"止蝕價{CL}>現價是{CP}，立即止蝕：及取消賣單",trade_data["orderId"],"止蝕價{}成交")

    elif orders_status_dic["open_position_order"]["order_status"]== "Filled" \
            and orders_status_dic["close_position_order"]["order_status"] == None \
            and orders_status_dic["cut_loss_order"]["order_status"] == None:

        print("cut3")
        flat_order, capital_ratio, order_type = cut_lose_order_set_func()
        trade_list = run_func(trade_session,coin_symbol, flat_order, side, order_type, p, capital_ratio)
        orderID = [trade['orderID'] for trade in trade_list if 'orderID' in trade]
        cut_posit_orderID = orderID[0]
        update_order_status = "cut_loss"
        traded_qty = [trade['qty'] for trade in trade_list if 'qty' in trade]
        traded_qty = traded_qty[0]
        orders_status_dic, P_n_L = update_order_data_func(cut_posit_orderID, init, orders_status_dic, update_order_status,CP,traded_qty)
        print(f"orders_status_dic:{orders_status_dic}")
        range_trade_list.append(orders_status_dic)
        next_action = "no_position"
        print(f"止蝕價{CL}>現價是{CP}，立即止蝕：",orderID,"止蝕價{}成交")

    return next_action,orders_status_dic,range_trade_list, P_n_L

@retry(stop_max_attempt_number=100, wait_fixed=2000)
def has_stock_func(range_trade_list,init,orders_status_dic ,coin_symbol, side , p, order_type,CL,update_order_status,next_action,start_time_str, end_time_str):
    print("has_stock_func\n")
    break_button = False
    P_n_L = None

    while True:
        print(f"bug4:orders_status_dic:{orders_status_dic}")
        within_time = is_within_time_range_func(start_time_str, end_time_str)
        CP = Non_trade().get_current_coin_price(coin_symbol)
        time.sleep(5)
        if CP > CL and break_button == False and within_time == True:
            print('CP > CL')
            print(f"break_button{break_button}, next_action{next_action} , orders_status_dic{orders_status_dic},range_trade_list{range_trade_list}, P_n_L{P_n_L}")
            break_button, next_action , orders_status_dic,range_trade_list, P_n_L = flat_position_func(range_trade_list,break_button,init,CP,coin_symbol,side,order_type,flat_p,orders_status_dic,
                                                                               next_action)
        elif CP <= CL and within_time == True:
            print('CP < CL')
            next_action, orders_status_dic,range_trade_list, P_n_L = cut_lose_func(range_trade_list,init,orders_status_dic ,coin_symbol,
                                                           side , p,CL,CP,next_action)
            break

        elif break_button ==  True:
            print("finish one trade")
            break

        elif within_time == False:
            next_action = "time_out"
            break

    return next_action ,update_order_status, orders_status_dic,range_trade_list, P_n_L

@retry(stop_max_attempt_number=100, wait_fixed=2000)
def main_func(coin_symbol,TBP,side, capital_ratio, p, order_type,CL,start_time_str, end_time_str):
    print("main_func\n")
    init , update_order_status , next_action= init_func()
    orders_status_dic = init
    range_trade_list = []
    P_n_L_list = []

    print(f'flat_p:{flat_p}')
    while True:

        if next_action == "no_position":
            print("next_action = no_position")
            print(f'flat_p:{flat_p}')
            init, update_order_status, next_action = init_func()
            orders_status_dic = init
            range_trade_list.append(orders_status_dic)
            next_action ,update_order_status,orders_status_dic,range_trade_list, P_n_L = no_stock_func(range_trade_list,init,orders_status_dic,coin_symbol,TBP,side, capital_ratio, p, order_type,start_time_str, end_time_str,update_order_status)
            P_n_L_list.append(P_n_L)

        elif next_action == "has_position":
            print("next_action = has_position")
            print(f'flat_p:{flat_p}')
            next_action ,update_order_status, orders_status_dic,range_trade_list, P_n_L = has_stock_func(range_trade_list,init,orders_status_dic ,coin_symbol, side , p, order_type,CL,update_order_status,next_action,start_time_str, end_time_str)
            P_n_L_list.append(P_n_L)

        elif next_action == "time_out":
            print("next_action = time_out")
            CP = Non_trade().get_current_coin_price(coin_symbol)
            next_action,orders_status_dic,range_trade_list, P_n_L = cut_lose_func(range_trade_list, init, orders_status_dic, coin_symbol, side, p, CL, CP, next_action)
            P_n_L_list.append(P_n_L)
            break

    return P_n_L_list

if __name__ == "__main__":
    test_real, coin_symbol, flat_order, \
    side, order_type, p, \
    capital_ratio, TBP, CL, \
    flat_p, Accs = Range_trade().execute_all()
    accs_info = read_data(test_real, Accs)
    print(f"test_real:{test_real},coin_symbol:{coin_symbol},flat_order:{flat_order}"
          f"side:{side},order_type:{order_type},p:{p},"
          f"capital_ratio:{capital_ratio},TBP:{TBP},CL:{CL},flat_p:{flat_p},Accs:{Accs}")

    start_time_str = "21/06/2024, 23:47"
    end_time_str = "26/06/2024, 14:51"

    for acc_name, info in accs_info.items():
        trade_session  , order_session = trading_session(acc_name, info)
        print(f"order_session:{order_session}")

        P_n_L_list = main_func(coin_symbol,TBP,side, capital_ratio, p, order_type,CL,start_time_str, end_time_str)
        print(f"P_n_L_list:{P_n_L_list}")