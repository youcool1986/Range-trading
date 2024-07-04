import trade_tools as t_tool
import trade_api as t_api
import non_trade_api as n_t_api
import pandas as pd
import math
from input import active_orders
from retrying import retry

trade_api = t_api.Trade
trade_order_api = t_api.Order_type_class
trade_adjust = n_t_api.Trade_adjustments
trade_tools = t_tool.Trade_tool

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
    return trade_session

@retry(stop_max_attempt_number=5, wait_fixed=2000)
def checking_in_out_data(trade_session, coin_symbol, capital_ratio, side):
    non_trade_api = n_t_api.Non_trade
    cur_price = non_trade_api().get_current_coin_price(coin_symbol)
    df_position_val = trade_session.get_position_value(coin_symbol)
    total_position_val, total_equity = trade_session.wallet_balance()

    position_val = float(df_position_val.loc[0, 'total_val'])
    position_size = float(df_position_val.loc[0, 'qty'])
    position_side = df_position_val.loc[0, 'side']

    trade_size = position_size * (capital_ratio / 100)
    trade_equity = total_equity * (capital_ratio / 100)

    pd_data = non_trade_api().get_instruments_info(coin_symbol)
    trade_adjustment = trade_adjust(pd_data)
    minOrderQty = float(pd_data.loc[0, 'minOrderQty'])
    maxMktOrderQty = float(pd_data.loc[0, 'maxMktOrderQty'])
    min_pos_val = 6

    return cur_price, trade_equity, position_side, trade_size, side, trade_adjustment, minOrderQty, maxMktOrderQty, min_pos_val

def redefine_p_trade_capital(p, cur_price, flat_order, trade_size, trade_equity, order_type):
    if order_type == "Market":
        p = cur_price

    if flat_order:
        trade_capital = trade_size
    else:
        trade_capital = trade_equity

    return p, trade_capital

def particule_define(p, minOrderQty, min_pos_val, maxMktOrderQty, trade_capital):
    if min_pos_val < (minOrderQty * p):
        min_amount = (minOrderQty * p)
    else:
        min_amount = min_pos_val

    max_amount = math.floor((maxMktOrderQty * p) / min_amount)
    if trade_capital < min_amount:
        trade_capital = min_amount

    particule_val = min_amount
    min_amount = 1

    return max_amount, min_amount, particule_val, trade_capital

def re_split_no(trade_capital, particule_val, maxMktOrderQty, p, split_no):
    max_split_no = math.floor(trade_capital / particule_val)

    if split_no > max_split_no:
        split_no = max_split_no
    elif trade_capital > (maxMktOrderQty * p):
        split_no = trade_capital / (maxMktOrderQty * p)

    return split_no

def re_define_bit(trade_capital, split_no, trade_size, flat_order):
    bit = trade_capital / split_no
    if flat_order:
        bit = trade_size / split_no
    return bit

@retry(stop_max_attempt_number=5, wait_fixed=2000)
def active_trade(trade_session, coin_symbol, side, qty, p, order_type, trade_adjustment, trade_capital, bit, particule_val):
    qty = trade_adjustment.qty_decimel_adjust(qty)
    print(f"coin_symbol:{coin_symbol}, side:{side}, qty:{qty}, p:{p}, order_type:{order_type}")
    order_data = trade_session.active_order(coin_symbol, side, qty, p, order_type)
    trade_capital -= bit

    trade_dic = {
        "coin_symbol": coin_symbol,
        "side": side,
        "qty": qty,
        "p": p,
        "order_type_input": order_type,
        "orderID":order_data["orderId"]
    }

    trade_dic_2 = {}
    if bit > trade_capital and trade_capital > particule_val:
        print("trade_remain")
        qty = trade_capital / p
        qty = trade_adjustment.qty_decimel_adjust(qty)
        p = trade_adjustment.prices_adjust_range(p)
        print(f"coin_symbol:{coin_symbol}, side:{side}, qty:{qty}, p:{p}, order_type:{order_type}")
        order_data = trade_session.active_order(coin_symbol, side, qty, p, order_type)
        trade_dic_2 = {
            "coin_symbol": coin_symbol,
            "side": side,
            "qty": qty,
            "p": p,
            "order_type_input": order_type,
            "orderID":order_data["orderId"]
        }
        break_pt = True
    elif bit > trade_capital and trade_capital < particule_val:
        break_pt = True
    else:
        break_pt = False

    return break_pt, trade_dic, trade_capital, trade_dic_2

def flat_order_side(position_side,side):
    if position_side == "Buy":
        side = "Sell"
    elif position_side == "Sell":
        side = "Buy"
    return side

@retry(stop_max_attempt_number=5, wait_fixed=2000)
def flat_trade(trade_session,trade_capital, coin_symbol, p, qty, side, order_type, trade_adjustment, trade_size, bit,minOrderQty):
    qty = trade_adjustment.qty_decimel_adjust(qty)
    print(f"coin_symbol:{coin_symbol}, side:{side}, qty:{qty}, p:{p}, order_type:{order_type}")
    order_data = trade_session.active_order(coin_symbol, side, qty, p, order_type)

    trade_dic = {
        "coin_symbol": coin_symbol,
        "side": side,
        "qty": qty,
        "p": p,
        "order_type_input": order_type,
        "orderID":order_data["orderId"]
    }

    trade_capital = trade_capital - qty
    print(f"trade_capital:{trade_capital}")

    trade_dic_2 = {}
    if bit > trade_capital and trade_capital > minOrderQty:
        print("trade_remain")
        qty = trade_capital
        qty = trade_adjustment.qty_decimel_adjust(qty)
        print(f"coin_symbol:{coin_symbol}, side:{side}, qty:{qty}, p:{p}, order_type:{order_type}")

        order_data = trade_session.active_order(coin_symbol, side, qty, p, order_type)
        trade_dic_2 = {
            "coin_symbol": coin_symbol,
            "side": side,
            "qty": qty,
            "p": p,
            "order_type_input": order_type,
            "orderID":order_data["orderId"]
        }
        break_pt = True
    else:
        break_pt = False

    return break_pt, trade_dic, trade_capital, trade_dic_2

def trade_list_func(trade_list, trade_dic, trade_dic_2):
    trade_list.append(trade_dic)
    if trade_dic_2:
        trade_list.append(trade_dic_2)
    return trade_list

def trade_start(trade_session, coin_symbol, side, order_type, p, cur_price, trade_capital, bit, flat_order, position_side, trade_adjustment, particule_val, minOrderQty):
    print("trade_start_func")
    trade_list = []
    while trade_capital > 0:
        print(f"trade_capital:{trade_capital}")
        p = trade_adjustment.prices_adjust_range(p)
        if order_type == "Limit":
            if not flat_order:
                qty = bit / p
                break_pt, trade_dic, trade_capital, trade_dic_2 = active_trade(trade_session, coin_symbol, side, qty, p, order_type, trade_adjustment, trade_capital, bit, particule_val)
            else:
                side = flat_order_side(position_side,side)
                qty = bit
                break_pt, trade_dic, trade_capital, trade_dic_2 = flat_trade(trade_session,trade_capital, coin_symbol, p, qty, side, order_type, trade_adjustment, trade_capital, bit,minOrderQty)
        else:
            if not flat_order:
                qty = bit / cur_price
                break_pt, trade_dic, trade_capital, trade_dic_2= active_trade(trade_session, coin_symbol, side, qty, cur_price, order_type, trade_adjustment, trade_capital, bit, particule_val)
            else:
                print("market_flat")
                side = flat_order_side(position_side,side)
                qty = bit
                break_pt, trade_dic, trade_capital, trade_dic_2 = flat_trade(trade_session,trade_capital, coin_symbol, cur_price, qty, side, order_type, trade_adjustment, trade_capital, bit,minOrderQty)

        trade_list = trade_list_func(trade_list, trade_dic, trade_dic_2)
        if break_pt:
            break

    return trade_list


def run_func(trade_session,coin_symbol, flat_order, side, order_type, p, capital_ratio):
    cur_price, trade_equity, position_side, trade_size, side, trade_adjustment, minOrderQty, maxMktOrderQty, min_pos_val = checking_in_out_data(trade_session, coin_symbol, capital_ratio, side)
    print(f"cur_price:{cur_price}, trade_equity:{trade_equity}, position_side:{position_side}, trade_size:{trade_size}, side:{side}, minOrderQty:{minOrderQty}, maxMktOrderQty:{maxMktOrderQty}, min_pos_val:{min_pos_val}")
    p, trade_capital = redefine_p_trade_capital(p, cur_price, flat_order, trade_size, trade_equity, order_type)
    max_amount, min_amount, particule_val, trade_capital = particule_define(p, minOrderQty, min_pos_val, maxMktOrderQty, trade_capital)
    if trade_capital > 0:
        split_no = 1
        split_no = re_split_no(trade_capital, particule_val, maxMktOrderQty, p, split_no)
        bit = re_define_bit(trade_capital, split_no, trade_size, flat_order)
        print(f"bit:{bit}")
        trade_list = trade_start(trade_session, coin_symbol, side, order_type, p, cur_price, trade_capital, bit, flat_order, position_side, trade_adjustment, particule_val, minOrderQty)
        total_qty = sum(trade_dic['qty'] for trade_dic in trade_list)
        print(f"total_qty:{total_qty}")

        #for test
        if order_type == "Limit":
            qty = trade_capital / p
        else:
            p = cur_price
            qty = trade_capital / p

        if flat_order == True:
            qty = trade_capital

        trade_input_result = {
            "coin_symbol": coin_symbol,
            "side_input": side,
            "qty": qty,
            "price": p,
            "order_type_input": order_type,
        }
        print(f"trade_input_result:{trade_input_result}")

        return trade_list

    else:
        print("(1)no_position to flat\n"
              "(2)no usdt to trade ")



if __name__ == "__main__":
    test_real, coin_symbol, flat_order, side, order_type, p, capital_ratio, Accs = active_orders().execute_all()

    accs_info = read_data(test_real, Accs)
    for acc_name, info in accs_info.items():
        trade_session = trading_session(acc_name, info)

        trade_list = run_func(trade_session,coin_symbol, flat_order, side, order_type, p, capital_ratio)
        print(f"trade_list:{trade_list}")
