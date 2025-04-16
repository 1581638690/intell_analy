import os
import ast
import copy
import time
import ujson
import pickle
import pandas as pd
from collections import defaultdict
import configparser

# 读取配置文件
# path_config = configparser.ConfigParser()
# path_config.read('./config.ini')
# path_config.read('config_window.ini')
# 获取字符信息# 获取 start_chars 和 end_chars
path_config = {
    'start_chars': "&,;",
    'end_chars': "&,;"
}
start_chars_str = path_config.get('start_chars')
end_chars_str = path_config.get('end_chars')
start_chars = [char.strip() for char in start_chars_str.split(',')]
end_chars = [char.strip() for char in end_chars_str.split(',')]


def classify_data1(condition, datas):
    """
    :param condition: 这几条数据的上下文规则信息
    :param datas: 分类数据
    :return:
    """
    # 获取http日志数据信息
    classified_groups = defaultdict(dict)
    # 获取json日志信息
    json_class_groups = defaultdict(dict)
    # 对原始数据进行上下文分类处理信息
    # 他只有一个信息 一个key值
    for key, value in condition.items():
        for o_data in datas:
            json_entry_data = {"imps": []}
            current_entry_data = {"imps": []}
            idx = o_data.get("idx")
            http_data = o_data["data"]
            imps_lst = o_data["imps"]
            # 获取原始数据中需要的字段信息

            # 获取标识数据信息
            for imp in imps_lst:
                imp_pos = imp.get("imp_pos")  # 标注名称
                imp_name = imp.get("imp_name")  # 标注内容信息
                # 新增识别方法，JSON或者TEXT
                imp_type = imp.get("imp_type")  # 标注的内容信息
                if "JSON" in imp_type:
                    # 如果 JSON存在与imp中，就将JSON 存入json_class_groups中，如果不存在则直接存入字符串识别中
                    if imp_pos in http_data:
                        json_entry_data[imp_pos] = http_data[imp_pos]
                    imp["annotated_index"] = imps_lst.index(imp)
                    json_entry_data["imps"].append(imp)
                    json_class_groups[key].setdefault(idx, json_entry_data)
                else:
                    # if imp_pos in http_data:
                    #     current_entry_data[imp_pos] = http_data[imp_pos]
                    # imp["annotated_index"] = imps_lst.index(imp)
                    # current_entry_data["imps"].append(imp)
                    # # 更新分类数据字典
                    # classified_groups[key].setdefault(idx,
                    #                                   current_entry_data)  # {“测试7”:{"1":{"imps":[],"parameter":""}}}
                    pass
    return classified_groups, json_class_groups


def data_merge(con, o_data):
    # 调用函数
    classified_groups, json_class_groups = classify_data1(con, o_data)
    cls = {}
    for key, datas in classified_groups.items():  # key:测试7  datas:{"0":{"imps":[],"parameter":""}

        unique_imp_lst = []
        for idx, id_dic in datas.items():  # [data,data]
            # 获取标识信息的详细内容
            imps_list = id_dic["imps"]

            # 判断标识数据是否为空 为空 则表示用户只传递了几组数据进行测试
            if imps_list:
                # 需要对详细内容进行处理，提取imp_name 作为主键，进行分类
                unique_imp = {}
                for imps_dic in imps_list:
                    imp_name = imps_dic["imp_name"]
                    imp_data = imps_dic["imp_data"]
                    imp_pos = imps_dic["imp_pos"]
                    ann_index = imps_dic["annotated_index"]
                    imp_uid = imps_dic["imp_uid"]
                    # 注释改内容
                    # char_limit = imps_dic["char_limit"]
                    unique_imp.setdefault(imp_name, {}).setdefault('imp_data', []).append(imp_data)
                    unique_imp.setdefault(imp_name, {}).setdefault('imp_pos', []).append(imp_pos)
                    # 注释改内容 前端不传char_limit
                    # unique_imp.setdefault(imp_name, {}).setdefault("char_limit", []).append(char_limit)
                    unique_imp.setdefault(imp_name, {}).setdefault("idx", idx)
                    unique_imp.setdefault(imp_name, {}).setdefault("ann_index", []).append(ann_index)
                    unique_imp.setdefault(imp_name, {}).setdefault("imp_uid", []).append(imp_uid)
                unique_imp_lst.append(unique_imp)
        cls[key] = unique_imp_lst
    return cls, classified_groups, json_class_groups


def analy_data(con, o_data):
    cls, classified_groups, json_class_groups = data_merge(con, o_data)
    cls_data = {}
    for key, data in cls.items():
        result = {}
        for item in data:
            for imp_name, value in item.items():
                if imp_name not in result:
                    result[imp_name] = {}
                imp_data = value["imp_data"]
                idx = value["idx"]
                imp_pos = value["imp_pos"]
                ann_index = value["ann_index"]
                imp_uid = value["imp_uid"]
                # 注释限制字符长度
                # char_limit_list = value["char_limit"]
                for i, data in enumerate(imp_data):
                    if i not in result[imp_name]:
                        result[imp_name][i] = {}
                    # result[imp_name][i][data] = {"idx": idx, "pos": imp_pos[i],"char_limit":char_limit_list[i]}
                    result[imp_name][i][data] = {"idx": idx, "pos": imp_pos[i], "ann_index": ann_index[i],
                                                 "imp_uid": imp_uid[i]}
        cls_data[key] = result
    return cls_data, classified_groups, json_class_groups


def analyze_handle(con, o_data):
    """
    :param o_data: 分析数据，对标识的数据信息进行准确的位置信息 ，并给出标识的数据信息中所对应日志信息的下标索引，这样可以避免一些不存在的信息位置
    :return:
    """
    cls_data, classified_groups, json_class_groups = analy_data(con, o_data)

    # 请求体
    project_body = {}
    for key, data in cls_data.items():  # key : method app datatype
        project_body[key] = {}  # key为子模型名称
        # 获取属于当前key 的原始日志信息
        http_data = classified_groups[key]

        for imp_name, value in data.items():  # imp_name :账户、密码
            project_body[key][imp_name] = {}  # {”模型三“:{"账户":{}}}
            for inx, imd_pos in value.items():  # inx表示标注信息在日志信息的位置
                # 给出存储容器信息
                imp_pos = {}
                ht_dic = {}
                # char_limit_list = {}
                ann_index_lst = []
                imp_uid_lst = []

                for imd, idx_pos in imd_pos.items():  # imd 为标识的数据，idx_pos为标识数据所在的位置，索引
                    # 找出数据的索引 信息
                    idx = idx_pos["idx"]  # 表示日志信息的位置
                    pos = idx_pos["pos"]  # 表示所在日志信息的字段
                    imp_uid = idx_pos["imp_uid"]  # 表示标注文本的唯一ID
                    imp_uid_lst.append(imp_uid)
                    ann_index = idx_pos["ann_index"]  # 表示第几个标注文本
                    ann_index_lst.append(ann_index)
                    # 获取http当前信息
                    http_info = http_data.get(idx)  # 获取到日志信息的数据

                    # 添加函数 去除掉imps之后 留下识别的字段信息，请求体跟响应体除外
                    ht_dic, imp_pos = data_search(http_info, imd, imp_pos, ht_dic, pos)  # 日志信息，标识数据，标注位置，

                    # url_dic[imd] = http_info["url"]
                    imp_pos.setdefault(imd, pos)
                    # 注释 后续有需要再开
                    # char_limit_list.setdefault(imd,char_limit)

                project_body[key][imp_name][inx] = {
                    "imp_uid": imp_uid_lst,
                    "imp_pos": imp_pos,
                    # "char_limit_list":char_limit_list
                    "ann_index": list(set(ann_index_lst))
                }
                for h_pos, data in ht_dic.items():
                    project_body.setdefault(key, {}).setdefault(imp_name, {}).setdefault(inx, {}).setdefault(h_pos,
                                                                                                             data)
    return project_body, json_class_groups


def data_search_old(http_info, imd, imp_pos, ht_dic, pos):
    """
    :param http_info: 源数据信息
    :param imd:  标识数据信息
    :param imp_pos: 数据位置存储
    :param ht_dic: {“request_body”:{}}
    :return:
    """
    for http_key, data in http_info.items():

        if http_key == "imps":
            continue
        else:
            if header_judge(data) and http_key == pos:
                data = ujson.loads(data)
                data, index_lst = headers_search(data, imd)
                if index_lst:
                    ht_dic.setdefault(http_key, {}).setdefault(imd, data)
                    imp_pos.setdefault(imd, index_lst)
            else:
                if http_key == pos:
                    index_lst = body_par_search(data, imd)
                    if index_lst:
                        ht_dic.setdefault(http_key, {}).setdefault(imd, data)
                        imp_pos.setdefault(imd, index_lst)
    return ht_dic, imp_pos


def header_judge_old(info):
    """
    :param info: 请求头 响应头 的字符串值
    :return:
    """
    if isinstance(info, str):
        if info.startswith("[{") and info.endswith("}]"):
            return True
    return False


def body_par_search_old(data, imd):
    """
    对请求体 响应体，参数
    :param data:
    :param imd:
    :return:
    """
    # 需要判断数据是否存在与当前字符串中
    if imd in data:
        # 找到字符串的起始位置
        start_index = data.find(imd)

        # 计算结束位置
        end_index = start_index + len(imd)
        return [start_index, end_index]
    return []


def headers_search_old(data, imd):
    """对 请求头 响应头"""
    for item in data:
        ii = {}
        if "name" in item:
            key = item["name"]
            value = item["value"]
            res = body_par_search(value, imd)
            if res:
                ii[key] = value
                return ii, res
    return {}, []


def start_end_df_handle(data_source, imp_pos):
    """
    :param data_source: 经过分类的数据源消息 {'13501048148': 'account=13501048148', '13508810307': 'account=13508810307','13503007701': 'account=13503007701'}
    :param imp_pos: 分类消息中标识消息的起始位置和结束位置  {'13501048148': [8, 19], '13508810307': [8, 19], '13503007701': [8, 19]}
    :return:
    continuous_start_df ；起始位置之前相同字符串的索引数组
    continuous_end_df ： 结束位置连续相同字符串的索引数组
    result_df ： 起始位置之前字符串df表
    end_df : 结束位置之后字符串df表
    """

    df = pd.DataFrame.from_dict(data_source, orient='index', columns=['data'])
    df.index.name = 'index'
    # 将 imp_pos1 转换成 DataFrame
    imp_df = pd.DataFrame.from_dict(imp_pos, orient='index', columns=['start_index', 'end_index'])
    imp_df.index.name = 'index'

    # 将 char_limit转化为 DataFrame
    # char_limit_df = pd.DataFrame.from_dict(char_limit_list,orient='index', columns=['char_limit'])
    # char_limit_df.index.name = 'index'
    # 合并两个 DataFrame
    result_df = pd.merge(df, imp_df, left_index=True, right_index=True)
    # result_df = pd.merge(result_df, char_limit_df, left_index=True, right_index=True)
    end_df = result_df.copy()
    # 设置字符提取限制

    # 更新 df - 从起始位置向前提取最多20个字符
    for idx, row in result_df.iterrows():
        # char_limit = row["char_limit"]
        char_limit = 20
        start_index, _ = imp_pos[idx]
        # 判断初始消息
        if start_index > 20:
            ss_index = start_index - 20
        for offset in range(1, min(char_limit, start_index) + 1):
            col_name = str(offset)
            extracted_char = row["data"][start_index - offset] if start_index - offset >= 0 else ""
            result_df.at[idx, col_name] = extracted_char

    # 更新 end_df - 从结束位置向后提取最多20个字符
    for idx, row in end_df.iterrows():
        # char_limit = row["char_limit"]
        char_limit = 15
        _, end_index = imp_pos[idx]
        # 需要确定实际可用的字符数据量
        available_chars = len(row["data"]) - end_index  # 如果大于20 就取20，如果 两个相等 就是0 ，如果小于20就取char_limit
        # 调整提取字符的数量，如果可用字符少于chat_limit,则使用可用字符
        num_chars_to_extract = min(available_chars, char_limit)
        for offset in range(1, num_chars_to_extract + 1):
            col_name = str(offset)
            current_index = end_index - 1 + offset
            extracted_char = row["data"][current_index] if current_index < len(row["data"]) else ""
            end_df.at[idx, col_name] = extracted_char
    # 调用函数返回 连续数组字符串数组
    continuous_start_df = find_continuous_same_columns(result_df, start_chars)
    continuous_end_df = find_continuous_same_columns(end_df, end_chars)
    return continuous_start_df, continuous_end_df, result_df, end_df


def find_continuous_same_columns(df, stop_chars):
    """
    找出连续相同的列，也是经过分析得出的数组，用来之后遍历
    :param df:
    :return:
    """
    continuous_streaks = []
    current_streak = []
    previous_col_number = -1  # Initialize to an invalid column number

    # 循环所有列值，跳过 col='data'的数据
    for col in [col for col in df.columns if
                (col != 'data' and col != 'start_index' and col != 'end_index' and col != 'char_limit')]:
        col_number = int(col)

        # 检查 if当前列所有数据都相同
        if len(df[col].unique()) == 1:
            if previous_col_number == -1 or col_number - previous_col_number == 1:
                current_streak.append(col)
            else:
                # 进行新的连续数据进行比对
                if len(current_streak) > 1:
                    continuous_streaks.append(current_streak)
                current_streak = [col]
        else:

            # 如果当前列 不存在相同的数据，就将之前的存储的数据存储 列表中
            if len(current_streak) > 1:
                continuous_streaks.append(current_streak)
            current_streak = []

        previous_col_number = col_number  # 更新值previous_col_number

    # 检查如果最后队列完成将其添加到列表中
    if len(current_streak) > 1:
        continuous_streaks.append(current_streak)

    if stop_chars:
        continuous_streaks_copy = []
        for streak in continuous_streaks:
            filtered_streaks = []
            # streak 获取到连续字符串的子列表，因为会有从字符串中间取值的问题
            for index in streak:
                if df[index].iloc[0] not in stop_chars:  # 获取当前列是否存在与
                    filtered_streaks.append(index)
                else:
                    filtered_streaks.append(index)
                    break
            continuous_streaks_copy.append(filtered_streaks)
        continuous_streaks = continuous_streaks_copy
    return continuous_streaks


def continuous_df(result_df, end_df, continuous_start_df, continuous_end_df):
    """
    :param result_df: start df表
    :param end_df:   end  df表
    :param continuous_start_df:  起始位置连续索引的数组
    :param continuous_end_df:   结束位置连续索引的数组
    :return: {'start': {'str': '&username=', 's_index': 21},'end': {'str': '&password=', 'e_index': 57}}

    """
    tol_info = {"start": {}, "end": {}}
    # 针对起始字符串
    extracted_start_values = []
    ss_values = []  # 用来找最小起始位置信息
    if continuous_start_df:
        first_lst = continuous_start_df[0]
        for col in first_lst:
            extracted_start_values.append(result_df[col].iloc[0])  # 获取字符串
        # 起始位置 寻找字符串最初位置
        ss_index = first_lst[-1]
        # 需要判断获取的数组中，数组第一位是否为 “1”
        equal_index = first_lst[0]

        # 先将该段注释 （后续如果需要就将其加上）
        # for index, col_data in result_df.iterrows():
        #     idx = col_data["start_index"] - int(ss_index)
        #     ss_values.append(idx)

        tol_info["start"].setdefault("str", "".join(extracted_start_values[::-1]))  # 表示我们的规则字符串

        # 跟上面一段关联
        # tol_info["start"].setdefault("s_index", min(ss_values))  # 表示我们规则字符串的起始位置在哪
        if equal_index != "1":
            tol_info["start"].setdefault("offset_pos", int(equal_index) - 1)  # 直接截取规则字符串后字符串从该下标取到最后

    # 针对 结束字符串
    extracted_end_values = []
    ee_values = []  # 用来找最小结束位置信息
    if continuous_end_df:
        first_lst = continuous_end_df[0]
        for col in first_lst:
            extracted_end_values.append(end_df[col].iloc[0])
        # 结束位置，寻找字符串最初位置
        ee_index = first_lst[-1]
        # 需要判断获取的数组中，数组第一位是否为 “1”
        equal_index = first_lst[0]

        # 将该段注释了因为下标位置在新数据中没什么用 先将该段注释 （后续如果需要就将其加上）
        # for index, col_data in end_df.iterrows():
        #     idx = col_data["end_index"] + int(ee_index)
        #     ee_values.append(idx)
        tol_info["end"].setdefault("str", "".join(extracted_end_values))  # 表示我们的规则字符串

        # 跟上面一段关联
        # tol_info["end"].setdefault("e_index", max(ee_values))  # 表示我们规则字符串的起始位置在哪
        if equal_index != "1":
            tol_info["end"].setdefault("offset_pos", int(equal_index) - 1)  # 直接截取规则字符串后字符串从该下标取到最后
    return tol_info


def rule_info(data_source, imp_pos):
    """
    :param data_source:数据源
    :param imp_pos:
    :param http_pos:
    :return:  根据http日志的位置去进行不同的数据提取
    """
    if all(isinstance(value, str) for value in data_source.values()):
        continuous_start_df, continuous_end_df, result_df, end_df = start_end_df_handle(data_source, imp_pos)
        print(continuous_start_df)
        print(continuous_end_df)
        print(result_df)
        print(end_df)
        tol_info = continuous_df(result_df, end_df, continuous_start_df, continuous_end_df)
        # result["default"] = tol_info

        return tol_info

    # elif http_pos == "request_headers" or http_pos == "response_headers":
    elif all(isinstance(value, dict) for value in data_source.values()):
        result = {}
        # 由于 我们获取的key 不知道是
        head_dic = {}
        for imp_name, headers in data_source.items():
            for key, value in headers.items():
                head_dic.setdefault(key, {}).setdefault(imp_name, value)
        for key, data_source in head_dic.items():
            continuous_start_df, continuous_end_df, result_df, end_df = start_end_df_handle(data_source, imp_pos)
            tol_info = continuous_df(result_df, end_df, continuous_start_df, continuous_end_df)
            # 为结果添加key值信息
            result[key] = tol_info

        return result
    else:
        return {}

def annotation_process(con: dict, datas: list) -> dict:
    cls_groups = defaultdict(dict)
    for key in con.keys():
        cls_groups[key] = {}
        for ann_data in datas:
            http_data = ann_data["data"]
            imps_data = ann_data["imps"]
            log_index = ann_data["idx"]
            info_pos_match(http_data, imps_data, log_index, cls_groups[key])
    cls_groups = merge_accounts(cls_groups)
    return cls_groups


def data_search(data: str, imd: str, imp_pos: dict,imp_decode:str) -> dict:
    headers_data={}
    if header_judge(data):
        data = ujson.loads(data)
        if imp_decode == "bytes":
            imd = ast.literal_eval(f'"{imd}"')
        headers_data, index_lst = headers_search(data, imd)
    else:
        index_lst = body_par_search(data, imd)
    if index_lst:
        imp_pos.setdefault(imd, index_lst)
    
    return imp_pos,headers_data


def header_judge(info: str) -> bool:
    return isinstance(info, str) and info.startswith("[{") and info.endswith("}]")


def body_par_search(data: str, imd: str) -> list:
    if imd in data:
        start_index = data.find(imd)
        return [start_index, start_index + len(imd)]
    return []


def headers_search(data: list, imd: str) -> tuple:
    for item in data:
        if "name" in item:
            key = item["name"]
            value = item["value"]
            res = body_par_search(value, imd)
            if res:
                return {key:value}, res
    return {}, []


def info_pos_match(http_data: dict, imps_data: list, log_index: int, annotated_info: dict) -> dict:
    for imp_index, imps in enumerate(imps_data):
        imp_name = imps.get("imp_name") 
        imp_data = imps.get("imp_data")
        imp_pos = imps.get("imp_pos")
        imp_uid = imps.get("imp_uid")
        imp_type = imps.get("imp_type")
        imp_decode = imps.get("imp_decode","")
        if "JSON" not in imp_type:
            ann_pos = http_data.get(imp_pos)
            entry = annotated_info.setdefault(imp_name, {}).setdefault(log_index, {})
            entry.setdefault("imp_uid", []).append(imp_uid) # 保存标注文本的唯一ID
            entry.setdefault("ann_index", []).append(imp_index) # 标注信息的索引
            #entry.setdefault(imp_pos, {}).setdefault(imp_data, ann_pos)
            entry.setdefault("http_pos", []).append(imp_pos) # 获取标注信息的位置
            entry.setdefault("imp_decode",[]).append(imp_decode) # 获取数据需要进行解码的数据
            entry.setdefault("imp_type",[]).append(imp_type)#获取数据是否单多选
            ht_dic,headers_data = data_search(ann_pos, imp_data, {},imp_decode)
            if headers_data:
                entry.setdefault(imp_pos, {}).setdefault(imp_data, headers_data)
            else:
                entry.setdefault(imp_pos, {}).setdefault(imp_data, ann_pos)
            entry.setdefault("imp_pos",ht_dic)
        else:
            pass
    return annotated_info

def merge_accounts_old(cls_groups:dict) -> dict:
    merged = {
        'imp_uid': [],
        'ann_index': [],

        'imp_pos': {}
    }
    # 记录日志信息的数据
    log_index=[]
    for model_key,ch_data in cls_groups.items():
        for ch_name,data in ch_data.items():
            for idx,entry in data.items():
                log_index.append(idx)
                merged['imp_uid'].extend(entry['imp_uid'])
                merged['ann_index'].extend(entry['ann_index'])
                http_pos_lst = entry.get("http_pos")
                for http_pos in http_pos_lst:
                    merged.setdefault(http_pos, {})  # 确保该位置存在
                    merged[http_pos].update(entry.get(http_pos))
                for key, pos in entry['imp_pos'].items():
                    merged['imp_pos'].setdefault(key, []).extend(pos)
            for idx in log_index:
                cls_groups[model_key][ch_name][idx] = merged
    return cls_groups
def merge_accounts(cls_groups: dict) -> dict:
    for model_key, ch_data in cls_groups.items():
        for ch_name, data in ch_data.items():
            # 初始化合并结构
            merged = {
                'imp_uid': [],
                'ann_index': [],
                'imp_decode':[],
                "imp_type":[],
                'imp_pos': {}
            }
            
            # 合并数据
            for idx, entry in data.items():
                merged['imp_uid'].extend(entry['imp_uid'])
                merged['ann_index'].extend(entry['ann_index'])
                merged['imp_decode'].extend(entry.get("imp_decode",""))
                merged['imp_type'].extend(entry['imp_type'])
                #merged['imp_pos'].extend(entry['imp_pos'])
                # 合并 http_pos
                http_pos_lst = entry.get("http_pos", [])
                for http_pos in http_pos_lst:
                    merged.setdefault(http_pos, {}).update(entry.get(http_pos, {}))
                
                # 合并 imp_pos
                for key, pos in entry['imp_pos'].items():
                    merged['imp_pos'].setdefault(key, []).extend(pos)

            # 更新所有 idx 的数据为合并后的结果
            for idx in data:
                cls_groups[model_key][ch_name][idx] = merged
    
    return cls_groups
def handle_project(con, o_data):
    """
    :param o_data: 经过分类之后的数据信息。{key:{"账户":{0:{"request_body":""}}}
    :return:
    """
    # project_body, json_class_groups = analyze_handle(con, o_data)
    project_body = annotation_process(con, o_data) # 使用新逻辑信处理 获取字符串规则信息
    _, json_class_groups = classify_data1(con, o_data) # 获取json格式数据
    print(project_body)
    str_rules = {}
    # 添加临时存储的规则数据
    temp_rules = {}
    for model_key, pro_dic in project_body.items():  # project_body: key:{"账户":{0:{"request_body":""}}}

        # imp_name 为用户提供的标识信息，pos_data则是 每个数据索引内标识信息存在的位置及索引位置
        for imp_name, pos_data in pro_dic.items():
            #  pos_data ： {0:{"request_body":}}
            for id, data in pos_data.items():  # id表示http数据的id索引，例如（0，1，2),data :
                imp_pos = data["imp_pos"]  # 从data中获取详情信息
                ann_index = data.get("ann_index", [])  # 获取标识信息的下标
                a_index = ann_index
                imp_uid = data.get("imp_uid")
                imp_decode = data.get("imp_decode","") # 获取编码信息
                imp_type = data.get("imp_type") # 获取数据类型
                # 需要对 data进行循环 这样才能动态的识别字段信息
                str_rules,temp_rules= dynamic_data(data, str_rules, imp_pos, imp_name, a_index, model_key, imp_uid,temp_rules,imp_decode,imp_type)
                print(str_rules)
    # print(json_class_groups)
    json_rules = fodr_rules(json_class_groups) # json格式数据规则获取
    temp_json_rules = copy.deepcopy(json_rules) # 深拷贝，用作界面识别的规则
    json_rules = merge_rules(str_rules, json_rules) # 合并 json格式和字符串格式规则用作存储
    temp_json_rules = merge_rules(temp_rules, temp_json_rules) # 合并 json格式和字符串格式规则用作界面识别
    return json_rules,temp_json_rules

def merge_rules(str_rules,json_rules):

    for model_key, model_value in str_rules.items():
        # 获取当前值信息
        j_rules = json_rules.get(model_key, {})
        for name, id_value in model_value.items():
            # 判断字符串模型下面的数据信息
            if name not in j_rules:
                # 如果不存在，就直接添加
                j_rules[name] = {**id_value}  # 创建一个新的字典
            else:
                # 存在 需要将值进行添加
                j_rules[name].update(id_value)

        # 将合并后的值更新回json_rules
        json_rules[model_key] = j_rules
    return json_rules

def dynamic_data(http_data, rules, imp_pos, imp_name, a_index, model_key, imp_uid,temp_rules,imp_decode,imp_type):
    """
    :param http_data: 请求数据 ，需要动态获取数据信息 并进行识别，判断走那个识别
    :return:
    """
    for key, data_source in http_data.items():
        if key != "ann_index" and key != "imp_pos" and key != "imp_uid" and key != "imp_decode" and key!= "imp_type":
            if imp_decode == ["bytes"]:
                # 进行解码处理
                data_source_temp = {}
                for b_data,value  in data_source.items():
                    b_data = ast.literal_eval(f'"{b_data}"')
                    data_source_temp[b_data] = value
                data_source = data_source_temp
            tol_info = rule_info(data_source, imp_pos)
            if tol_info:
                if "TEXT_mutil" in imp_type[0]:
                    rules.setdefault(model_key, {}).setdefault(imp_name, {}).setdefault("多选" + imp_uid[0] + f"_{str(a_index[0])}",
                                                                                    {key: tol_info,"imp_decode":imp_decode[0]})
                else:
                    rules.setdefault(model_key, {}).setdefault(imp_name, {}).setdefault(imp_uid[0] + f"_{str(a_index[0])}",
                                                                                    {key: tol_info,"imp_decode":imp_decode[0]})# 添加编码规则信息
                
                
                for a_idx,i_uid in zip(a_index,imp_uid):
                    temp_rules.setdefault(model_key, {}).setdefault(imp_name, {}).setdefault(i_uid + f"_{str(a_idx)}",
                                                                                    {key: tol_info})
    return rules,temp_rules


#                                                   ######保存规则信息######
def save_all_data(rules, con, model_key, linfo, file_str):
    """
    保存规则、条件、标签信息到同一个文件中
    :param rules: 规则数据
    :param condition: 条件数据
    :param label_info: 标签信息数据
    :param file_str: 文件名字符串
    :return: 操作结果信息
    """
    # 拼接文件路径
    # base_dir = "/data/xlink/models_paths/"
    base_dir = "../../"
    source_file = os.path.join(base_dir, f"{file_str}_rcl_bak.pkl")
    destination_file = os.path.join(base_dir, f"{file_str}_rcl.pkl")

    # 尝试读取已有的数据
    existing_data = {}
    if os.path.exists(destination_file):
        try:
            with open(destination_file, "rb") as fp:
                existing_data = pickle.load(fp)
        except Exception as e:
            return {"code":500,"status": "Error", "message": str(e)}
        # 获取现有数据

        # 获取子模型的历史值
        if model_key in existing_data:
            old_model = existing_data.get(model_key, {})
            # 更新现有数据
            old_model["rules"] = rules
            old_model["condition"] = con
            old_model["label_info"] = linfo
        else:
            # 不存在 直接添加
            existing_data[model_key] = {
                "rules": rules,
                "condition": con,
                "label_info": linfo
            }
        # 将更新后的数据写入文件
        try:
            with open(source_file, "wb") as fp:
                pickle.dump(existing_data, fp)

        except OSError as e:
            return {"code":500,"status": "Error", "message": f"模型存储错误：{str(e)}"}
        # 写入之后 将其移动置我们原文件中，这样做避免出现报错问题
        try:
            os.replace(source_file, destination_file)
            return {"code":200,"status": "Success", "message": "模型存储成功！"}
        except OSError as e:
            return {"code":500,"status": "Error", "message": f"模型数据移动出错：{str(e)}"}

    else:
        # 文件不存在
        existing_data[model_key] = {
            "rules": rules,
            "condition": con,
            "label_info": linfo
        }
        res = dump_rules_pkl(existing_data, destination_file)
        return res

#                                                   ######增加规则信息######
def add_all_data(rules, con, model_key, linfo, map_field, MapField, dict_assoc, existing_data):
    """
    保存规则、条件、标签信息到同一个文件中
    :param rules: 规则数据
    :param condition: 条件数据
    :param label_info: 标签信息数据
    :param file_str: 文件名字符串
    :return: 操作结果信息
    """
    # 拼接文件路径
    # base_dir = "/data/xlink/models_paths/"

    # 尝试读取已有的数据
    if existing_data:
        # 获取现有数据
        # 获取子模型的历史值
        # 就是 纯新增
        existing_data[model_key] = {
            "rules": rules,
            "condition": con,
            "label_info": linfo,
            "map_dic": map_field,
            "MapField": MapField,
            "dict_assoc": dict_assoc
        }
    else:
        # 数据为空 直接添加
        existing_data[model_key] = {
            "rules": rules,
            "condition": con,
            "label_info": linfo,
            "map_dic": map_field,
            "MapField": MapField,
            "dict_assoc": dict_assoc
        }

    return existing_data


#                                                   ######修改规则信息######
def alter_all_data(rules, con, model_key, linfo, old_key, map_field, MapField, dict_assoc, existing_data):
    """
    :param rules: 规则信息
    :param con: con信息
    :param model_key: 修改的新模型名称
    :param linfo:
    :param file_str:
    :param old_key:
    :return:
    """

    datas = {
        "rules": rules,
        "condition": con,
        "label_info": linfo,
        "map_dic": map_field,
        "MapField": MapField,
        "dict_assoc": dict_assoc
    }
    # 尝试读取已有的数据
    if existing_data:
        # 需要先找出旧 key的值,将旧的key与新的key进行替换
        if old_key in existing_data:
            existing_data[old_key] = datas  # 让旧的key 的值替换成最新的
            existing_data[model_key] = existing_data.pop(old_key)  # 然后 删除旧的key pop旧key让值等于新key
        else:
            existing_data[model_key] = datas  # 如果旧key不存在 直接新增

    else:
        existing_data[model_key] = datas  # 不存在 直接新增

    return existing_data


def dump_rules_pkl(existing_data, path):
    try:
        with open(path, 'wb') as fp:
            pickle.dump(existing_data, fp)
        return {"code":200,"status": "Success", "message": "模型存储成功！"}
    except Exception as e:
        return {"code":500,"status": "Error", "message": str(e)}


#                                                    ######根据结果识别发来的数据结果 ######

def an_data(datass, intell_rules, con):
    """
    :param datass: 标识数据
    :param intell_rules:  形成规则信息
    :param con: 我们的上下文规则信息
    :return:
    """
    # 返回结果JSON对象
    res_data = defaultdict(dict)
    # 对原始数据进行上下文分类处理信息
    for key, condition in con.items():  # 条件查询的名称
        # condition = ujson.loads(condition)  # 将上下文规则转化为字典信息
        for o_data in datass:
            # 获取当前数据信息
            idx = o_data.get("idx")  # 获取当前消息的索引信息
            # 获取HTTP审计日志信息
            http_data = o_data["data"]  #

            # 给出当前需要匹配的详细信息

            if intell_rules:
                res_data = accord_rules(intell_rules, key, http_data, idx, res_data, condition)
            else:
                res_data = {}
    return res_data


def accord_rules(intell_rules, key, http_data, idx, res_data, condition):
    """
    根据获取到的规则进行识别
    :return:
    """
    # 循环condition 的信息
    found = True
    # 循环 只要有一个不符合 那就直接将found设置为False

    found = con_found(condition, http_data, found)
    if found:
        # 判断key是否存在于
        rules_data = intell_rules[key]

        data_storage = {}
        # 循环rules_data 获取到具体的规则
        for ch_name, t_rules in rules_data.items():  # ch_name 标识名称: t_rules {"uuid":{"imp_pos":rules}}
            for uid, rulers in t_rules.items():
                if "JSON" in uid:
                    data_storage = json_identify(data_storage, http_data, rulers, ch_name, uid)
                else:
                    # uid 为改值的唯一标识
                    an_index = uid.split("_")[-1]
                    imp_uid = uid.split("_")[0]
                    for http_pos, pos_rules in rulers.items():
                        current_data = http_data.get(http_pos, "")
                        if header_judge(current_data):
                            data_storage = headers_exract(ch_name, pos_rules, current_data, data_storage, http_pos,
                                                          an_index, imp_uid)
                        else:
                            data_storage = par_body(ch_name, pos_rules, current_data, data_storage, http_pos, an_index,
                                                    imp_uid)

        res_data.setdefault(idx, data_storage)
        # print(res_data)
    return res_data


def con_found(conditions, http_data, found):
    for o_key, con_msg in conditions.items():
        # http_data =o_data["data"]
        val = http_data.get(o_key, "")  # 获取当前键在o里面的值  val相当于我们前台数据信息
        judge = con_msg.get("judge")
        msg = con_msg.get("msg")  # 这相当于 我们在前端界面写的值
        if judge == "=":
            if val != msg:
                found = False  # 表示 该条件不符合 直接跳出该规则
                break
        elif judge == "!=":
            if val == msg:
                found = False
                break
        elif judge == "in":
            if val not in msg:
                found = False
                break
        elif judge == "not in":
            if val in msg:  # 不存在msg中
                found = False
                break
        elif judge == "like":
            if msg not in val:
                found = False
                break
        elif judge == "not like":
            if msg in val:  # 不存在msg中
                found = False
                break
        elif judge == ">":
            if val < msg:
                found = False
                break
        elif judge == "<":
            if val > msg:
                found = False
                break
        elif judge == "<=":
            if val >= msg:
                found = False
                break
        elif judge == ">=":
            if val <= msg:
                found = False
                break
    return found


def par_body(ch_name, pos_rules, data_source, data_storage, pos, an_index, imp_uid):
    """
    处理体部
    :param ch_name:
    :param pos_rules:
    :param data_source:
    :param data_storage:
    :param pos:
    :return:
    """
    # 获取偏移量
    start_offset = pos_rules["start"].get("offset_pos", 0)
    end_offset = pos_rules["end"].get("offset_pos", 0)
    # pos_rules 为 {start:{},end:{}}
    start_str = pos_rules["start"].get("str", "")
    end_str = pos_rules["end"].get("str", "")
    # 根据两者信息 从数据中提取出重要信息
    start_pos, end_pos = s_e_str(start_str, end_str, data_source)

    if start_pos != -1 and end_pos != -1:
        current_start = start_pos + start_offset
        current_end = end_pos - end_offset
        res = data_source[current_start:current_end].strip()

        if res != "":
            for end in end_chars:
                if end in res:
                    res = res[:res.index(end)]
            # data_storage.setdefault(an_index, {}).setdefault(pos, {}).setdefault(ch_name, res)
            data_storage.setdefault(imp_uid, {}).setdefault("identifyResults", []).append(res)
    return data_storage


def headers_exract(ch_name, pos_rules, current_data, data_storage, pos, an_index, imp_uid):
    """
    处理头部的识别信息
    :param ch_name:
    :param pos_rules:
    :param request_headers:
    :param data_storage:
    :param pos:
    :return:
    """
    try:
        current_data = ujson.loads(current_data)
    except:
        current_data = []
    for key, rule in pos_rules.items():
        for item in current_data:
            if item["name"].lower() == key.lower():
                start_rule = rule["start"]
                end_rule = rule["end"]
                # 获取偏移量

                start_offset = start_rule.get("offset_pos", 0)
                start_str = start_rule.get("str", "")

                end_offset = end_rule.get("offset_pos", 0)
                end_str = end_rule.get("str", "")
                # 如果相等，就开始让规则从该数据中取出重要信息
                # 如果存在空值怎么办
                # 根据两者信息 从数据中提取出重要信息
                values = item.get("value", "")
                if values:  # 如果存在该值则进行查找
                    start_pos, end_pos = s_e_str(start_str, end_str, values)
                    # 如果找到了起始字符串和结束字符串
                    if start_pos != -1 and end_pos != -1:
                        current_start = start_pos + start_offset
                        current_end = end_pos - end_offset
                        res = item["value"][current_start:current_end].strip()

                        if res != "":
                            for end in end_chars:
                                if end in res:
                                    res = res[:res.index(end)]
                            data_storage.setdefault(imp_uid, {}).setdefault("identifyResults", []).append(res)
                            # data_storage.setdefault(imp_uid, {}).setdefault("fewLogs",an_index)
                            # data_storage.append({imp_uid,{}}.setdefault("identifyResults",[]).append(res).setdefault("fewLogs", an_index))
                            # data_storage.setdefault(an_index, {}).setdefault(pos, {}).setdefault(ch_name, res)
                            break
                else:
                    continue
    return data_storage


def s_e_str(start_str, end_str, data_source):
    """
    根据起始字符串 结束字符串 数据 获取到当前识别信息
    :param start_str:
    :param end_str:
    :param data_source:
    :return:
    """
    if start_str and end_str:
        start_pos = data_source.find(start_str)
        if start_pos != -1:
            start_pos += len(start_str)  # 从获取到起始的最后面 再去寻找结束字符串
            end_pos = data_source.find(end_str, start_pos)
        else:
            start_pos = -1
            end_pos = -1

    elif start_str:
        # 如果 start_pos存在
        start_pos = data_source.find(start_str)
        if start_pos != -1:
            # 证明存在 该字符串
            start_pos += len(start_str)
            end_pos = len(data_source)
        else:
            start_pos = -1
            end_pos = -1
    elif end_str:
        # 如果只有结尾字符串
        start_pos = 0
        end_pos = data_source.find(end_str, start_pos)
    else:
        start_pos = 0
        end_pos = len(data_source)
    return start_pos, end_pos
#                                                ######识别文本多条数据######
def s_e_str_more(start_str, end_str, data_source):
    """
    获取多个匹配项的起始和结束位置
    :param start_str: 起始字符串
    :param end_str: 结束字符串
    :param data_source: 数据源
    :return: 匹配项的开始和结束位置的列表
    """
    start_pos = 0
    results = []
    while True:
        # 查找起始字符串
        start_pos = data_source.find(start_str, start_pos)
        if start_pos == -1:
            break
        start_pos += len(start_str)  # 向后移动到数据的实际开始位置

        # 查找结束字符串
        end_pos = data_source.find(end_str, start_pos)
        if end_pos == -1:
            break

        results.append((start_pos, end_pos))
        start_pos = end_pos  # 移动到下一个搜索位置

    return results
#                                                       ######配置信息代码######

def x_uuids(x):
    return str(time.perf_counter())


#                                           ######模型名称判断代码######
def found_path(path_name):
    """判断字符串是否存在了"""
    x_p = "/data/xlink/x_t_p.pkl"

    if os.path.exists(x_p):
        with open(x_p, 'rb') as fp:
            n_lst = pickle.load(fp)  # 模型名称列表
        if path_name not in n_lst:
            n_lst.append(path_name)
            return {"code":200,"status": "Success", "msg": f"模型名-{path_name}-创建成功！"}
        else:
            return {"code":500,"status": "Error", "msg": f"模型名-{path_name}-已经存在！"}
    else:
        # 不存在 x_p_bak这个文件，
        path_lst = [path_name]
        with open(x_p, "wb") as fp:
            pickle.dump(path_lst, fp)
        return {"code":200,"status": "Success", "msg": f"模型名-{path_name}-创建成功！"}


#                                           ######读取模型文件并识别结果######
def read_model_identify(models_data, o, dict_tree=None):
    data_storage = {}
    label_info = {}
    label_dic = {}
    # dict_tree = {}
    if models_data:
        for model_key, data in models_data.items():  # model_key :测试7 ,{}
            # 第一条信息
            # print(data)
            # 先进行筛选条件的判断
            conditions = data.get("condition", {})
            rulers = data.get("rules", {})
            l_info = data.get("label_info", {})
            map_dic = data.get("map_dic", {})
            MapField = data.get("MapField", {})
            dict_assoc = data.get("dict_assoc", "")
            # 身处 同一 子模型名称下面，需要判断上下文规则是否满足，如果满足则进行规则识别
            try:
                found = con_judge(conditions, o)
            except Exception as e:
                return f"上下文规则数据出错：{e.__str__()}"

            if found:
                # 对字典映射数据进行处理
                try:
                    if map_dic:
                        dict_tree = map_field_identify(map_dic, o, dict_tree)
                        print(dict_tree)
                except Exception as e:
                    return f"模型映射数据出错：{e.__str__()}"
                # 如果上下文规则成立，那就对规则进行读取
                try:

                    data_storage, l_info = rule_judge(rulers, o, data_storage, l_info, dict_tree, MapField, dict_assoc)
                except Exception as e:
                    return f"模型识别数据出错：{e.__str__()}"
                for label, value in l_info.items():
                    if value != "" and value not in label_info.setdefault(label, []):
                        label_info[label].append(value)
            else:
                continue
        for label, val_lst in label_info.items():
            if len(val_lst) >= 1:
                label_dic[label] = val_lst[0]
        if data_storage or label_dic:
            return {"data": data_storage, "label_info": label_dic, "map_tree": dict_tree}
        else:
            return {}
    return {}


def con_judge(condition, o):
    """
    :param condition: 上下文规则条件
    :param o: 数据源
    :return:
    """

    found = True
    found = con_found(condition, o, found)
    return found


def rule_judge(rulers, o, data_storage, l_info, dict_tree=None, MapField=None, assoc_str=""):
    """
    对规则进行识别
    """
    # ch_name中包含着数据信息 返回 操作
    for ch_name, ch_data in rulers.items():
        for uid, imp_data in ch_data.items():
            if "JSON" in uid:
                data_storage, l_info = model_data_extract(ch_name, o, data_storage, imp_data, l_info, dict_tree,
                                                          MapField, assoc_str)  # 组织名 o,
            else:
                imp_decode = imp_data.get("imp_decode")
                imp_datas = {i:item for i,item in imp_data.items() if i!="imp_decode"}
                for http_pos, rle in imp_datas.items():
                    current_data = o.get(http_pos, "")
                    if header_judge(current_data):

                        data_storage, l_info = headers_models(current_data, rle, http_pos, ch_name, data_storage,
                                                              l_info,imp_decode,uid, dict_tree, MapField, assoc_str)

                    elif isinstance(current_data, list):
                        data_storage, l_info = headers_models(current_data, rle, http_pos, ch_name, data_storage,
                                                              l_info,imp_decode,uid, dict_tree, MapField, assoc_str)
                    else:
                        data_storage, l_info = body_models(current_data, rle, http_pos, ch_name, data_storage, l_info,imp_decode,uid,
                                                           dict_tree, MapField, assoc_str)

    return data_storage, l_info


def headers_models(current_data, pos_rules, http_pos, ch_name, data_storage, l_info, imp_decode,uid,dict_tree=None, MapField=None,
                   assoc_str=""):
    try:
        current_data = ujson.loads(current_data)
    except:
        current_data = current_data
    for key, rule in pos_rules.items():
        for item in current_data:
            if item["name"].lower() == key.lower():
                start_rule = rule["start"]
                end_rule = rule["end"]
                # 获取偏移量

                start_offset = start_rule.get("offset_pos", 0)
                start_str = start_rule.get("str", "")

                end_offset = end_rule.get("offset_pos", 0)
                end_str = end_rule.get("str", "")
                # 如果相等，就开始让规则从该数据中取出重要信息
                # 如果存在空值怎么办

                # 根据两者信息 从数据中提取出重要信息
                values = item.get("value", "")
                if values:  # 如果存在该值则进行查找
                    # add rzc 2025/2/27
                    if "多选" in uid:
                        pos_list = s_e_str_more(start_str,end_str,values)
                    else:
                        # 单条识别
                        pos_list = s_e_str(start_str, end_str, values)
                    if isinstance(pos_list, tuple):
                        pos_list = [pos_list]
                    for i in pos_list:
                        start_pos, end_pos = i
                    # add end
                    #start_pos, end_pos = s_e_str(start_str, end_str, values)
                    # 如果找到了起始字符串和结束字符串
                        if start_pos != -1 and end_pos != -1:
                            current_start = start_pos + start_offset
                            current_end = end_pos - end_offset
                            res = item["value"][current_start:current_end].strip()
                            res = decode_value(imp_decode,res)  # 进行编码转化操作
                            ch_name_lst = ch_name.split(">>")  # 取0索引，但是我还是要判断一下>>存不存在，如果不想存在，就直接返回当前字符串了
                            if len(ch_name_lst) > 1:
                                ch_names = ch_name_lst[1]
                                type_name = ch_name_lst[0]
                            else:
                                type_name = ""
                            if res == "":
                                res = field_ch(MapField, ch_names, res)
                            if res != "" and res not in data_storage.setdefault(http_pos, {}).setdefault(type_name,
                                                                                                        {}).setdefault(
                                ch_names, []):
                                for end in end_chars:
                                    if end in res:
                                        res = res[:res.index(end)]
                                res = field_ch(MapField, ch_names, res)  # 中文字段映射
                                res, l_info = dic_ass(ch_names, dict_tree, assoc_str, res, l_info)  # 字典映射
                                data_storage[http_pos][type_name][ch_names].append(res)
                else:
                    continue
    return data_storage, l_info


def body_models(data_source, pos_rules, http_pos, ch_name, data_storage, l_info,imp_decode,uid, dict_tree=None, MapField=None,
                assoc_str=""):
    """
    处理体部
    :param ch_name:
    :param pos_rules:
    :param data_source:
    :param data_storage:
    :param pos:
    :return:
    """
    # 获取偏移量
    start_offset = pos_rules["start"].get("offset_pos", 0)
    end_offset = pos_rules["end"].get("offset_pos", 0)
    # pos_rules 为 {start:{},end:{}}
    start_str = pos_rules["start"].get("str", "")
    end_str = pos_rules["end"].get("str", "")
    # 根据两者信息 从数据中提取出重要信息
    # 多条识别
    if "多选" in uid:
        pos_list = s_e_str_more(start_str,end_str,data_source)
    else:
        # 单条识别
        pos_list = s_e_str(start_str, end_str, data_source)
    if isinstance(pos_list, tuple):
        pos_list = [pos_list]
    for i in pos_list:
        start_pos, end_pos = i
        if start_pos != -1 and end_pos != -1:
            current_start = start_pos + start_offset
            current_end = end_pos - end_offset
            res = data_source[current_start:current_end].strip()
            # 进行编码转化操作
            res = decode_value(imp_decode,res)

            # 根据空值会有搜索为空的信息，所以这里空值也进行存储
            # 对 ch_name 进行分割
            ch_name_lst = ch_name.split(">>")  # 取0索引，但是我还是要判断一下>>存不存在，如果不想存在，就直接返回当前字符串了
            if len(ch_name_lst) > 1:
                ch_names = ch_name_lst[1]
                type_name = ch_name_lst[0]
            else:
                type_name = ""
            if res == "":
                res = field_ch(MapField, ch_names, res)
            if res != "" and res not in data_storage.setdefault(http_pos, {}).setdefault(type_name, {}).setdefault(ch_names,
                                                                                                                []):
                for end in end_chars:
                    if end in res:
                        res = res[:res.index(end)]
                res = field_ch(MapField, ch_names, res)  # 中文字段映射
                res, l_info = dic_ass(ch_names, dict_tree, assoc_str, res, l_info)  # 字典映射信息
                data_storage[http_pos][type_name][ch_names].append(res)

    return data_storage, l_info


#                   ##########删除子模型数据##########
def delete_rules_data(model_key, file_str):
    # 拼接文件路径
    base_dir = "/data/xlink/models_paths/"
    # base_dir = "./"
    source_file = os.path.join(base_dir, f"{file_str}_rcl_bak.pkl")
    destination_file = os.path.join(base_dir, f"{file_str}_rcl.pkl")
    try:
        with open(destination_file, "rb") as fp:
            tol_rulers = pickle.load(fp)
    except Exception as e:
        return {"code":500,"status": "Error", "msg": f"模型数据读取错误：{e.__str__()}"}

    # 删除模型名称
    new_tol_rulers = {}
    if model_key in tol_rulers:
        try:
            del tol_rulers[model_key]
            # 将模型数据写入副本文件 中

            res = write_replace(source_file, destination_file, tol_rulers)
            if res.get("status") == "Success":
                return {"code":200,"status": "Success", "msg": f"子模型-{model_key}-删除成功！"}
            else:
                return res
        except:
            try:
                # 循环 tol_rules 数据，
                for current_key, data in tol_rulers.items():
                    if current_key != model_key:
                        new_tol_rulers[current_key] = data
                res = write_replace(source_file, destination_file, new_tol_rulers)
                if res.get("status") == "Success":
                    return {"code":200,"status": "Success", "msg": f"子模型-{model_key}-删除成功！"}
                else:
                    return res
            except:
                return {"code":500,"status": "Error", "msg": f"子模型-{model_key}-删除错误"}

    else:
        return {"code":500,"status": "Error", "msg": f"子模型-{model_key}-模型数据不存在！"}


def write_replace(source_file, destination_file, tol_rulers):
    # 将模型数据写入副本文件 中
    try:
        with open(source_file, "wb") as fp:
            pickle.dump(tol_rulers, fp)
    except OSError as e:
        return {"code":500,"status": "Error", "message": f"模型存储错误：{str(e)}"}
    # 写入之后 将其移动置我们原文件中，这样做避免出现报错问题
    try:
        os.replace(source_file, destination_file)
        return {"code":200,"status": "Success", "message": "模型存储成功！"}
    except OSError as e:
        return {"code":500,"status": "Error", "message": f"模型数据移动出错：{str(e)}"}


def load_data(destination_file):
    # 拼接文件路径
    # base_dir = "/data/xlink/models_paths/"
    if os.path.exists(destination_file):
        with open(destination_file, "rb") as fp:
            return pickle.load(fp)
    return {}


def load_model_data(file_str):
    # 需要放入xlink中进行判断，拼接字符串
    base_dir = "/data/xlink/models_paths/"

    source_file = os.path.join(base_dir, f"{file_str}_rcl.pkl")
    if os.path.exists(source_file):
        with open(source_file, "rb") as fp:
            return pickle.load(fp)
    return {}


#                                 #########add rzc 2024/4/28 ##############
def up_file_model(upload_file, file_str, base_dir):
    """
    :param new_file: 上传的文件
    :param file_str: 当前界面模型文件名称
    :return:
    """
    source_file = os.path.join(base_dir, f"{file_str}_rcl_bak1.pkl")
    old_model_file = os.path.join(base_dir, f"{file_str}_rcl.pkl")
    if os.path.exists(old_model_file):
        try:
            with open(upload_file, "rb") as fp:
                loaded_data = pickle.load(fp)

        except pickle.UnpicklingError as e:
            return {"code":500,"status": "Error", "message": f"模型文件格式错误：{e.__str__()}"}

        # 现在需要读取最新文件信息
        try:
            with open(old_model_file, "rb") as fp:
                old_data = pickle.load(fp)
        except Exception as e:
            return {"code":500,"status": "Error", "message": f"读取当前模型失败：{e.__str__()}"}

        # 需要将两个文件合并到一起，如果模型名称相同怎么办,分为 覆盖，保留原始值，或者合并，将三种情况全部写出来吧
        # ① 保留当前模型的值，祛除导入模型的值
        try:
            for current_key, current_value in loaded_data.items():
                if current_key not in old_data:
                    old_data[current_key] = current_value
        except Exception as e:
            return {"code":500,"status": "Error", "message": f"模型覆盖错误：{e.__str__()}"}
        res = write_replace(source_file, old_model_file, old_data)
        # ② 覆盖原值,将导入的值作为新值覆盖掉旧值
        # old_data.update(loaded_data)

        # ③ 合并模型，保留两个模型中相同的key，将两个模型中不同的key合并到一起，这个是将模型转化为列表存储了
        return res
    else:
        try:
            os.replace(upload_file, old_model_file)
            return {"code":200,"status": "Success", "message": "模型存储成功！"}
        except OSError as e:
            return {"code":500,"status": "Error", "message": f"模型数据移动出错{str(e)}"}


#                ################处理json格式的数据信息###############
def fodr_rules(json_class_groups):
    """
    :param classified_groups:{
                    "key":[
                        {
                            "data":{"request_body":"","response_body":""},
                            "imps":[{},{}]
                        },
                        {
                        "data":{"request_body":"","response_body":""},
                            "imps":[{},{}]
                        }
                          ],
                    }
    key:标识上下文相同数据信息
    data:表示日志信息
    imps:表示人工标识数据信息
    :return:
    """
    # condition就是我们的上下文规则 {“美创”:""}
    # classified_groups, json_class_groups = classify_data1(condition, datas)
    rules = {}

    for key, data_imps in json_class_groups.items():
        rules[key] = {}
        for idx, id_dic in data_imps.items():
            # 一个key值存在多个键值，就比如在一条消息内我们要标识说多种信息 所以data_imps是列表
            imps_list = id_dic["imps"]
            # 这里要获取 位置信息 存在的位置 目前只有两个 json情况下 只有有两个分析他的位置信息

            set_imp = list(set([imps["imp_pos"] for imps in imps_list]))
            for http_pos, h_data in id_dic.items():
                if http_pos == "imps":
                    # 获取单条数据信息及标识信息
                    continue
                else:
                    # http_pos是位置信息,字符串信息数据
                    pos_data = h_data
                    if http_pos in set_imp:
                        try:
                            pos_data = ujson.loads(pos_data)
                        except:
                            pos_data = pos_data
                    if pos_data:
                        rules = cification(key, pos_data, imps_list, rules)

    return rules


def cification(key, data_soure, imps, rules):
    for imp in imps:
        # 对每个记录找到的路径都进行单独的查找和记录,这个不做对比
        imp_data = imp["imp_data"]
        imp_pos = imp["imp_pos"]
        imp_name = imp["imp_name"]
        imp_type = imp["imp_type"]
        imp_uid = imp["imp_uid"]
        a_index = imp["annotated_index"]
        imp_decode = imp["imp_decode"]
        target = preprocess_target(imp_data)
        # 进行递归查找，这个是做了全局的查找了

        paths_dict = find_values_in_dict_little(data_soure, target, imp_type)
        # 添加编码识别规则信息
        rules[key].setdefault(imp_name, {}).setdefault("JSON" + imp_uid + f"_{str(a_index)}", {}).setdefault("imp_decode",imp_decode)
        for target, paths in paths_dict.items():

            if paths:
                # rules[key].setdefault()
                rules[key].setdefault(imp_name, {}).setdefault("JSON" + imp_uid + f"_{str(a_index)}", {}).setdefault(
                    imp_pos,
                    []).extend(
                    list(set(paths)))
    return rules


def find_values_in_dict_little(data, target, imp_type, path='', found_paths=None):
    if found_paths is None:
        found_paths = {str(target): []}

    if isinstance(data, dict):
        # 判断递归的data是否等于target
        if data == target:
            found_paths[str(target)].append(path)
        for key, value in data.items():
            current_path = f'{path}.{key}' if path else key

            if value == target or str(key) == str(target):
                found_paths[str(target)].append(current_path)

            if isinstance(value, str) and is_json_string(value):
                try:
                    json_value = ujson.loads(value)
                    if json_value == target:
                        found_paths[str(target)].append(current_path + "-JSON")
                    find_values_in_dict_little(json_value, target, imp_type, current_path + "-JSON",
                                               found_paths)
                except ValueError:
                    pass
            elif isinstance(value, (dict, list)):
                find_values_in_dict_little(value, target, imp_type, current_path, found_paths)
    elif isinstance(data, list):

        if data == target:
            found_paths[str(target)].append(path)
        # 判断是否第一次进来就是list,path就是空
        for index, item in enumerate(data):
            # if isinstance(item,list):
            if isinstance(item, str):
                if item == target:
                    if imp_type != "JSON":
                        current_path = f"{path}" + "." + f"-LIST[{index}]"
                    else:
                        current_path = f"{path}" + "." + f"-[{index}]"
                    found_paths[str(target)].append(current_path)
                else:
                    continue
            else:
                if imp_type != "JSON":
                    current_path = f"{path}-LIST"
                elif imp_type == "JSON" and path:
                    # 判断target是否是列表中最后一个
                    if target == item and data[-1] == target:
                        current_path = f"{path}-[-1]"
                    else:
                        current_path = f"{path}-[0]"
                else:
                    current_path = f"{path}-[{index}]"
                find_values_in_dict_little(item, target, imp_type, current_path, found_paths)

    return found_paths


def find_values_in_dict_little1(data, target, imp_type, path='', found_paths=None):
    if found_paths is None:
        found_paths = {str(target): []}

    if isinstance(data, dict):
        # 判断递归的data是否等于target
        if data == target:
            found_paths[str(target)].append(path)
        for key, value in data.items():
            current_path = f'{path}.{key}' if path else key

            if value == target or str(key) == str(target):
                found_paths[str(target)].append(current_path)

            if isinstance(value, str) and is_json_string(value):
                try:
                    json_value = ujson.loads(value)
                    if json_value == target:
                        found_paths[str(target)].append(current_path + "-JSON")
                    find_values_in_dict_little(json_value, target, imp_type, current_path + "-JSON",
                                               found_paths)
                except ValueError:
                    pass
            elif isinstance(value, (dict, list)):
                find_values_in_dict_little(value, target, imp_type, current_path, found_paths)
    elif isinstance(data, list):
        if data == target:
            found_paths[str(target)].append(path)
        for index, item in enumerate(data):
            # if isinstance(item,list):
            if isinstance(item, str):
                if item == target:
                    if imp_type != "JSON":
                        current_path = f"{path}-LIST[{index}]"
                    else:
                        current_path = f"{path}-[{index}]"
            else:
                if imp_type != "JSON":
                    current_path = f"{path}-LIST"
                else:
                    # current_path = f"{path}-[{index}]"
                    current_path = f"{path}-[0]"
            find_values_in_dict_little(item, target, imp_type, current_path, found_paths)

    return found_paths


def is_json_string(s):
    return (s.strip().startswith('{') and s.strip().endswith('}')) or (
            s.strip().startswith('[') and s.strip().endswith(']'))


def preprocess_target(target):
    if isinstance(target, str) and is_json_string(target):
        try:
            # 尝试将JSON字符串的target解析为字典
            preprocess = ujson.loads(target)
        except:
            preprocess = target
    else:
        preprocess = target
    return preprocess


# 对json数据进行识别
def json_identify(data_storage, http_data, rule, ch_name, uid):
    """
    :param rules: 生成的规则信息
    :param data_tol: 需要进行识别的数据信息
    :param condition: 上下文条件
    :return: 返回识别的结果信息
    """
    # 获取规则中的key值
    imp_uuid = uid.split("_")[1]
    imp_uid = uid.split("_")[0].replace("JSON", "")
    for http_pos, r_lst in rule.items():

        # 在前端调用的时候保存的是单个上下文规则
        # 获取相应的规则信息
        data_source = http_data.get(http_pos, "")
        if data_source:
            # 循环 req_rule 获取请求体中的响应数据
            # request_body = ujson.loads(request_body)
            for t_rule in r_lst:  # t_rule {"发票物品":[]}
                # ch_name:发票物品，rls:['bwxx-JSON.dataMap.dzfpKpywFpmxxxbVOList-[0].xmmc']
                value_lst = []
                # 'bwxx-JSON.dataMap.dzfpKpywFpmxxxbVOList-[0].xmmc'
                value_lst = get_value_by_path(data_source, t_rule, value_lst)
                if value_lst:
                    data_storage.setdefault(imp_uid, {}).setdefault("identifyResults", []).append(value_lst[0])
                    # data_storage.setdefault(imp_uuid, {}).setdefault(http_pos, {}).setdefault(ch_name, value_lst[0])

    return data_storage


def get_value_by_path1(data_source, path, value_lst):
    """
    根据给定路径获取数据源中的值并添加到value_lst中
    :param data_source: 数据源，可以是JSON字符串、字典或列表
    :param path: 访问路径，使用"."分隔
    :param value_lst: 存储结果值的列表
    :return: value_lst
    """
    try:
        current = ujson.loads(data_source) if isinstance(data_source, str) else data_source
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return value_lst

    path_list = path.split(".")

    idx_in_lst = 0  # 当前路径在列表中的索引，用于最后的值判断

    def traverse_path(temp_current, path_list, value_lst, idx_in_lst):
        found = True
        for index, p in enumerate(path_list):
            if p.endswith("-JSON"):
                key = p.split("-")[0]
                temp_current = temp_current.get(key)
                idx_in_lst = index
                if not temp_current:
                    found = False
                    break
                try:
                    temp_current = ujson.loads(temp_current)
                except Exception as e:
                    print(f"Error loading JSON from key '{key}': {e}")
                    found = False
                    break

            elif "-LIST" in p:
                key, _ = p.split("-LIST")
                key = key.strip()
                temp_current = temp_current.get(key, [])
                idx_in_lst = index
                if not temp_current:
                    found = False
                    break
                if p != path_list[-1]:  # 如果路径还未结束，则需要继续处理列表中的元素
                    for item in temp_current:
                        value_lst = traverse_path(item, path_list[index + 1:], value_lst, idx_in_lst)
                    break
            elif "-[" in p and p.endswith("]"):
                key, index = p.split("-[")
                key = key.strip()
                try:
                    index = int(index[:-1])
                except ValueError:
                    print(f"Invalid index in path: {p}")
                    found = False
                    break
                temp_current = temp_current.get(key, [])
                if not temp_current or index >= len(temp_current):
                    found = False
                    break
                temp_current = temp_current[index]

            else:
                temp_current = temp_current.get(p)
                idx_in_lst = index
            if not temp_current:
                found = False
                break

        if found and ((not isinstance(temp_current, list)) or (
                isinstance(temp_current, list) and idx_in_lst == len(path_list) - 1)):
            if temp_current not in value_lst:
                value_lst.append(temp_current)
        return value_lst

    # 如果数据源是列表，遍历每个元素
    if isinstance(current, list):
        # 如果刚开始就是list 那么第一个path  不是 -LIST 就是 -[0]

        if path_list[0] == "-LIST":
            # 如果是第一个
            for item in current:
                value_lst = traverse_path(item, path_list[1:], value_lst, idx_in_lst)
        else:
            item = current[0]
            value_lst = traverse_path(item, path_list[1:], value_lst, idx_in_lst)
    else:
        value_lst = traverse_path(current, path_list, value_lst, idx_in_lst)

    return value_lst


def get_value_by_path(data_source, path, value_lst):
    """
    根据给定路径获取数据源中的值并添加到value_lst中
    :param data_source: 数据源，可以是JSON字符串、字典或列表
    :param path: 访问路径，使用"."分隔
    :param value_lst: 存储结果值的列表
    :return: value_lst
    """
    try:
        current = ujson.loads(data_source) if isinstance(data_source, str) else data_source
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return value_lst

    path_list = path.split(".")

    idx_in_lst = 0  # 当前路径在列表中的索引，用于最后的值判断

    def traverse_path(temp_current, path_list, value_lst, idx_in_lst):
        found = True
        for index, p in enumerate(path_list):
            if p.endswith("-JSON"):
                key = p.split("-")[0]
                temp_current = temp_current.get(key)
                idx_in_lst = index
                if not temp_current:
                    found = False
                    break
                try:
                    temp_current = ujson.loads(temp_current)
                except Exception as e:
                    print(f"Error loading JSON from key '{key}': {e}")
                    found = False
                    break

            elif "-LIST" in p:
                key, l_index = p.split("-LIST")
                key = key.strip()
                # 判断是否是空如果是空就是列表嵌套
                if not key:
                    if l_index:
                        idx_in_lst = int(l_index.replace("[", "").replace("]", ""))
                        temp_current = temp_current[idx_in_lst]
                else:
                    temp_current = temp_current.get(key, [])
                    idx_in_lst = index
                if not temp_current:
                    found = False
                    break
                if p != path_list[-1]:  # 如果路径还未结束，则需要继续处理列表中的元素
                    for item in temp_current:
                        value_lst = traverse_path(item, path_list[index + 1:], value_lst, idx_in_lst)
                    break
            elif "-[" in p and p.endswith("]"):
                key, index = p.split("-[")
                key = key.strip()
                try:
                    index = int(index[:-1])
                except ValueError:
                    print(f"Invalid index in path: {p}")
                    found = False
                    break
                temp_current = temp_current.get(key, [])
                if not temp_current or index >= len(temp_current):
                    found = False
                    break
                temp_current = temp_current[index]

            else:
                temp_current = temp_current.get(p)
                idx_in_lst = index
            if not temp_current:
                found = False
                break

        if found and ((not isinstance(temp_current, list)) or (
                isinstance(temp_current, list) and idx_in_lst == len(path_list) - 1)):
            if temp_current not in value_lst:
                value_lst.append(temp_current)
        return value_lst

    # 如果数据源是列表，遍历每个元素
    if isinstance(current, list):
        # 如果刚开始就是list 那么第一个path  不是 -LIST 就是 -[index]

        if path_list[0] == "-LIST":
            # 如果是第一个
            for item in current:
                value_lst = traverse_path(item, path_list[1:], value_lst, idx_in_lst)
        else:

            c_index = int(path_list[0].replace("-[", "").replace("]", ""))
            # 直接执行index值
            item = current[c_index]
            if isinstance(item, list):

                get_value_by_path(item, ".".join(path_list[1:]).lstrip("."), value_lst)
            else:
                value_lst = traverse_path(item, path_list[1:], value_lst, idx_in_lst)
    else:
        value_lst = traverse_path(current, path_list, value_lst, idx_in_lst)

    return value_lst


def model_data_extract(ch_name, o, data_storage, imp_data, l_info, dict_tree=None, MapField=None, assoc_str=""):
    """
    用于xlink中处理
    :param ch_name:
    :param o:
    :param ch_data:
    :param data_storage:
    :return:
    """
    # 读取规则信息 将编码规则提取出来
    imp_decode = imp_data.get("imp_decode", "")
    imp_datas = {i:item for i,item in imp_data.items() if i!="imp_decode"}
    for http_pos, rle_lst in imp_datas.items():
        # 添加编码规则识别
       
        current_data = o.get(http_pos, "")
        if current_data:
            for t_rule in rle_lst:
                value_lst = []
                value_lst = get_value_by_path(current_data, t_rule, value_lst)
                
                #根据编码进行识别 add rzc 2025/2/27
                value_lst = decode_value(imp_decode,value_lst)
                # 对 ch_name 进行分割
                ch_name_lst = ch_name.split(">>")  # 取0索引，但是我还是要判断一下>>存不存在，如果不想存在，就直接返回当前字符串了
                if len(ch_name_lst) > 1:
                    ch_name = ch_name_lst[1]
                    type_name = ch_name_lst[0]
                else:
                    type_name = ""
                value_lst = field_ch(MapField, ch_name, value_lst)
                value_lst, l_info = dic_ass(ch_name, dict_tree, assoc_str, value_lst, l_info)
                if value_lst:
                    data_storage.setdefault(http_pos, {}).setdefault(type_name, {}).setdefault(ch_name, []).extend(
                        value_lst)

    return data_storage, l_info

from typing import List,Dict,Union
# add rzc on 2024/7/17 针对子模型标签信息进行判断 modify rzc on 2025/1/10 以获取多个日志类型的模型信息
def label_judge(model_data:Dict, label_key:str, label_name_list:Union[List,str]) -> Dict:
    model_file_data = {}
    if isinstance(label_name_list, str):
        label_name_list = [label_name_list]
    for model_key, rule_data in model_data.items():
        label_info = rule_data.get("label_info", {})
        if label_info.get(label_key) in label_name_list:
            model_file_data[model_key] = rule_data
    return model_file_data


def DiscrModel(model_data, value_list, key):
    """
    :param model_data: 模型信息
    :param value_list: 筛选模型信息
    :return:
    """
    data = {}
    for log in value_list:
        data.setdefault(log, {})
    for model_key, rule_data in model_data.items():
        label_info = rule_data.get("label_info", {})
        if key == "源日志信息":
            # 获取日志类型的值
            type_value = label_info.get("源日志信息", "")
        elif key == "日志类型":
            # 获取输出日志信息
            type_value = label_info.get("日志类型", "")
        else:
            type_value = ""

        if type_value and type_value in value_list:
            data[type_value][model_key] = rule_data
    return data


# add run on 2024/9/2 针对多源数据的文本识别
def MoreSourceModel(model_data, label_name_list=None, log_type_list=None):
    """
    :param model_data: 总模型文件
    :param label_list: 日志类型
    :return:
    """
    label_found, log_found = True, True
    # 先判断输出日志有无信息
    if not label_name_list:
        label_found = False
    if not log_type_list:
        log_found = False
    # 如果二者都无值，就将全部模型输出
    if not label_found and not log_found:  # 不存在源信息 不存在日志信息
        return model_data
    elif label_found and not log_found:  # 存在日志类型 没多源日志信息
        data = DiscrModel(model_data, label_name_list, "日志类型")
        return data
    elif not label_found and log_found:  # 存在源日志信息 不存在日志信息
        data = DiscrModel(model_data, log_type_list, "源日志信息")
        return data
    else:
        data = {}

        for model_key, rule_data in model_data.items():
            label_info = rule_data.get("label_info", {})
            # 获取日志类型的值
            type_value = label_info.get("源日志信息", "")
            # 获取输出日志信息
            label_value = label_info.get("日志类型", "")

            if type_value and type_value in log_type_list and (label_value and label_value in label_name_list):
                data.setdefault(type_value, {}).setdefault(label_value, {}).setdefault(model_key, rule_data)
        return data


def merge_dicts(d1, d2):
    for key in d2:
        if key in d1:
            if isinstance(d1[key], dict) and isinstance(d2[key], dict):
                merge_dicts(d1[key], d2[key])
            elif isinstance(d1[key], list) and isinstance(d2[key], list):
                # 将d2[key]的内容追加到d1[key]，并去重
                d1[key] = list(set(d1[key] + d2[key]))
            elif isinstance(d1[key], int) and isinstance(d2[key], int):
                # 如果是整数，则相加
                d1[key] += d2[key]
            else:
                d1[key] = d2[key]
        else:
            d1[key] = d2[key]
    return d1


def intell_sen1(model_file_data, monitor, sen_level):
    key_ch = {"response_body": "响应体", "request_body": "请求体", "parameter": "参数"}
    total_info = {}
    total_count = {}
    info = {}
    level_lst = []
    cls_lst = []
    counts = {}
    max_level = 0
    analy_data = read_model_identify(model_file_data, monitor)
    if isinstance(analy_data, dict):
        imp_data = analy_data.get("data")
        if imp_data:
            for pos, rule_data in imp_data.items():
                ch_pos = key_ch.get(pos, pos)
                sens = {}
                for cls_level, sen_data in rule_data.items():
                    cls, level = cls_level.split("-")
                    # level_lst.append(sen_level.get(level_ch))
                    level_lst.append(int(level))
                    level_ch = sen_level.get(int(level))
                    cls_lst.append(cls)
                    for k, v in sen_data.items():
                        sens.setdefault(k, []).extend(v)
                        total_info.setdefault(ch_pos, {}).setdefault(cls, {}).setdefault(level_ch, {}).setdefault(k,
                                                                                                                  list(
                                                                                                                      set(v)))
                        total_count.setdefault(ch_pos, {}).setdefault(cls, {}).setdefault(level_ch, {}).setdefault(k,
                                                                                                                   len(list(
                                                                                                                       set(v))))
                        info.setdefault(ch_pos, {}).setdefault(cls, {}).setdefault(level_ch, {}).setdefault(k, {
                            "数量": len(list(set(v))), "内容": list(set(v))})
                counts.setdefault(ch_pos, {k: len(list(set(v))) for k, v in sens.items()})

            if level_lst:
                max_level = max(level_lst)
            else:
                max_level = 0
            cls_lst = list(set(cls_lst))
    return total_info, total_count, max_level, info, cls_lst, counts


# 针对相同接口，根据接口参数的不同来变换接口事件的名称
def QueryApiName(url_name, label_info, parameter, parameter_json=None):
    """
    :return: 例如 /dataasset/api/core/dataSourceMgt/queryDataSourceInfo
    参数：keyword=&page=1&sourceType=JDBC%&size=10&dbType=MYSQL&dataType=CDB  数据归集-数据源管理-中心库
         keyword=&page=1&sourceType=JDBC&size=10&dbType=   数据归集-数据源管理
         page=9&size=10&keyword=启信宝&dataWarehouse=ODS  数据目录-数据目录-数仓分层-访问_搜索
        label_info = {"参数分类":"dataType>>中心库/数据源"}

    """
    # 先判断参数分类是否存在label_info
    if "参数分类" not in label_info:
        return url_name
    par_name = label_info.get("参数分类", "")
    keyword, cls = par_name.split(">>")
    key_true, key_false = cls.split("/")
    target = parameter_json or parameter
    result = key_true if target and keyword in target else key_false

    if url_name:
        url_name += f"-{result}"
    else:
        url_name = result

    return url_name


def QueryMultApiName(url_name, label_info, parameter, parameter_json=None):
    for key in label_info:
        if "参数分类" not in key:
            continue
        par_name = label_info.get(key, "")
        keyword, cls = par_name.split(">>")
        # target = parameter_json or parameter
        target = parameter_json or {}
        if (keyword in target or keyword in target.values()) or keyword in parameter:
            url_name = cls
    return url_name


def map_tree(map_dic, datas):
    """
    :param map_dic: 字典映射数据
    :return:
    """
    map_filed = {}
    id_path, id_pos = filed_path(map_dic, "id_field", datas)
    print(id_path, id_pos)
    fullname_path, name_pos = filed_path(map_dic, "fullname", datas)
    parentuuid_path, par_pos = filed_path(map_dic, "parentuuid", datas)
    map_filed.setdefault(id_pos, {}).setdefault("id_field", id_path)
    map_filed.setdefault(name_pos, {}).setdefault("fullname", fullname_path)
    map_filed.setdefault(par_pos, {}).setdefault("parentuuid", parentuuid_path)

    return map_filed


def filed_path(map_dic, filed, datas):
    # new_path = {}
    path = []
    id_field = map_dic.get(filed, {})

    imp_type = id_field.get("imp_type")
    # 获取当前日志信息
    data_id = int(id_field.get("data_id"))
    # 循环获取日志序号的日志信息
    current_data = next((d.get("data") for d in datas if d.get("idx") == data_id), None)

    id_pos = id_field.get("imp_pos")
    imp_data = id_field.get("imp_data")
    http_data = current_data.get(id_pos)
    http_data = ujson.loads(http_data)
    id_path = find_values_in_dict_little(http_data, imp_data, imp_type)

    if id_path:
        path = id_path.get(imp_data)

    return list(set(path)), id_pos


def map_field_identify(map_field, o, dict_tree):
    # dict_tree = {}

    for http_pos, res_lst in map_field.items():
        current_data = o.get(http_pos, "")
        if current_data:
            id_lst = []
            fullname_lst = []
            parentuuid_lst = []
            id_rule = res_lst.get("id_field", [])
            fullname_rule = res_lst.get("fullname", [])
            parentuuid_rule = res_lst.get("parentuuid", [])

            for t_rule in id_rule:
                id_lst = get_tree_value(current_data, t_rule, id_lst)

            for t_rule in fullname_rule:
                fullname_lst = get_tree_value(current_data, t_rule, fullname_lst)

            for t_rule in parentuuid_rule:
                parentuuid_lst = get_tree_value(current_data, t_rule, parentuuid_lst)
            # 获取最小长度
            min_length = min(len(id_lst), len(fullname_lst), len(parentuuid_lst))
            for id, fullname, parentuuid in zip(id_lst[:min_length], fullname_lst[:min_length],
                                                parentuuid_lst[:min_length]):
                dict_tree.setdefault(id, {}).setdefault("fullname", fullname)
                dict_tree.setdefault(id, {}).setdefault("parentuuid", parentuuid)
    return dict_tree


def get_tree_value(data_source, path, value_lst):
    """
    根据给定路径获取数据源中的值并添加到value_lst中
    :param data_source: 数据源，可以是JSON字符串、字典或列表
    :param path: 访问路径，使用"."分隔
    :param value_lst: 存储结果值的列表
    :return: value_lst
    """
    try:
        current = ujson.loads(data_source) if isinstance(data_source, str) else data_source
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return value_lst

    path_list = path.split(".")

    idx_in_lst = 0  # 当前路径在列表中的索引，用于最后的值判断

    def traverse_path(temp_current, path_list, value_lst, idx_in_lst):
        found = True
        for index, p in enumerate(path_list):
            if p.endswith("-JSON"):
                key = p.split("-")[0]
                temp_current = temp_current.get(key)
                idx_in_lst = index
                if not temp_current:
                    found = False
                    break
                try:
                    temp_current = ujson.loads(temp_current)
                except Exception as e:
                    print(f"Error loading JSON from key '{key}': {e}")
                    found = False
                    break

            elif "-LIST" in p:
                key, _ = p.split("-LIST")
                key = key.strip()
                temp_current = temp_current.get(key, [])
                idx_in_lst = index
                if not temp_current:
                    found = False
                    break
                if p != path_list[-1]:  # 如果路径还未结束，则需要继续处理列表中的元素
                    for item in temp_current:
                        value_lst = traverse_path(item, path_list[index + 1:], value_lst, idx_in_lst)
                    break
            elif "-[" in p and p.endswith("]"):
                key, index = p.split("-[")
                key = key.strip()
                try:
                    index = int(index[:-1])
                except ValueError:
                    print(f"Invalid index in path: {p}")
                    found = False
                    break
                temp_current = temp_current.get(key, [])
                if not temp_current or index >= len(temp_current):
                    found = False
                    break
                temp_current = temp_current[index]

            else:
                temp_current = temp_current.get(p)
                idx_in_lst = index
            if not temp_current:
                found = False
                break

        if found and ((not isinstance(temp_current, list)) or (
                isinstance(temp_current, list) and idx_in_lst == len(path_list) - 1)):
            value_lst.append(temp_current)
        return value_lst

    # 如果数据源是列表，遍历每个元素
    if isinstance(current, list):
        # 如果刚开始就是list 那么第一个path  不是 -LIST 就是 -[0]

        if path_list[0] == "-LIST":
            # 如果是第一个
            for item in current:
                value_lst = traverse_path(item, path_list[1:], value_lst, idx_in_lst)
        else:
            item = current[0]
            value_lst = traverse_path(item, path_list[1:], value_lst, idx_in_lst)
    else:
        value_lst = traverse_path(current, path_list, value_lst, idx_in_lst)

    return value_lst


def dic_ass(ch_name, dict_tree, assoc_str, value, l_info):
    """
    :param ch_name: 中文名
    :param dict_tree: 字典数据
    :param assoc_str: 需关联字段信息
    :return:
    """
    name = l_info.get("name", "")
    if assoc_str == ch_name:
        if isinstance(value, list):
            v_lst = []
            for org_uuid in value:
                if org_uuid in dict_tree:
                    path = []
                    ID_name = dict_tree[org_uuid].get("fullname", "")
                    v_lst.append(ID_name)
                    current_uuid = org_uuid
                    while current_uuid:
                        org_info = dict_tree.get(current_uuid)
                        if not org_info:
                            break
                        path.append(org_info["fullname"])
                        current_uuid = org_info["parentuuid"]
                    name += "-" + "-> ".join(reversed(path))
                    l_info["name"] = name
                else:
                    v_lst.append(org_uuid)
            return v_lst, l_info
        elif isinstance(value, str):
            if value in dict_tree:
                path = []
                ID_name = dict_tree[value].get("fullname", "")
                current_uuid = value
                while current_uuid:
                    org_info = dict_tree.get(current_uuid)
                    if not org_info:
                        break
                    path.append(org_info["fullname"])
                    current_uuid = org_info["parentuuid"]
                name += "-" + "-> ".join(reversed(path))
                l_info["name"] = name
                return ID_name, l_info
            else:
                return value, l_info
    else:
        return value, l_info


def field_ch(MapField, ch_name, res):
    """
    :param MapField: 映射字段
    :param ch_name: 中文名
    :param res: 返回结果
    :return:
    """
    if ch_name in MapField:
        if isinstance(res, list):
            res_lst = []
            for v in res:
                ch_map = MapField[ch_name]
                if isinstance(v, bool):
                    if v:
                        v = "true"
                    else:
                        v = "false"
                if str(v) in ch_map:
                    res_lst.append(ch_map[str(v)])
            return res_lst
        elif isinstance(res, str):

            ch_map = MapField[ch_name]
            if str(res) in ch_map:
                res = ch_map[str(res)]
            return res
        elif isinstance(res, bool):
            if res:
                res = "true"
            else:
                res = "false"
            return res
    else:
        return res


########################### 账户识别 ###########################
# 账户首先是需要进行获取 通过识别标注账户信息，提取token，来进行对照其他接口中的token进行关联账户信息

# 账户名 尽量中文标签尽量是账户名

def session_retrieval(user_dic, account_model, acc_o):
    """
    :param user_dic: 由Token作为键，账户信息作为值的字典
    :param result: 识别的标注数据
    :return:
    """
    sessid = ""
    account = ""
    result = read_model_identify(account_model, acc_o)
    label_info = result.get("label_info", {})
    if label_info.get("日志类型") == "账号登录":
        data = result.get("data", {})
        user_infos = {}
        token_container = []

        if not data:
            return user_dic, account

        for http_pos, action_value in data.items():
            for action, value_lst in action_value.items():
                for name, value in value_lst.items():
                    if name != "会话ID":
                        if len(value) >= 1:
                            user_infos[name] = value[0]
                    else:
                        token_container = value
        user_infos["date"] = r_datetime.datetime.now()
        if token_container:
            for jsessionid in token_container:
                user_dic.setdefault(jsessionid, user_infos)
                account = user_infos.get("账户名")
    else:
        # 获取到的是请求体中的 session_ID

        data = result.get("data", {})
        if data:
            for pos, pos_data in data.items():
                for action, action_data in pos_data.items():
                    for ch_name, value_list in action_data.items():
                        if ch_name == "会话ID" and value_list:
                            sessid = value_list[0]
    if sessid and sessid in user_dic:
        user_info = user_dic.get(sessid, {})
        account = user_info.get("账户名", "")
    return user_dic, account


# 定时删除文件中所包含超过时间段的会话信息
def sched_dele(user_dic):
    user_info = copy.deepcopy(user_dic)
    remove_key = []
    new_date = r_datetime.datetime.now()
    for key, value in user_info.items():
        if (new_date - value.get("date")).total_seconds() // 3600 >= 25:
            remove_key.append(key)
        # del user_info[key]
    for key in remove_key:
        del user_info[key]
        del user_dic[key]
    # dump_pkl("/data/xlink/user_info.pkl", user_info)


# 新增过滤标签模型信息
def filter_label(model_data, label_key, label_list):
    model_file_data = {}
    for model_key, rule_data in model_data.items():
        label_info = rule_data.get("label_info", {})
        if label_info.get(label_key) not in label_list:
            model_file_data[model_key] = rule_data
    return model_file_data

########################### 接口合并操作行为 ###########################
import datetime as r_datetime
from datetime import timedelta
from typing import Dict,Tuple,Any
# 首先要获取合并类型的数量
def more_count(model_data:Dict[str, Dict])->Dict[str, int]:
    label = "多接口事件"
    # 生成字典信息
    merge_dic:Dict[str, int] = {}
    for model_key,rule_data in model_data.items():
        label_info = rule_data.get("label_info",{})
        # 获取指定标签的类型信息
        types = label_info.get(label, "")
        
        # 更新计数
        if types:
            merge_dic[types] = merge_dic.get(types, 0) + 1
    return merge_dic

def session_action_relation(sessionid:str, 
                            action_dict: Dict[str,Any], 
                            o: Dict[str,Any],
                            label_info: Dict[str, Any],
                            e_cot:Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
        sessionid:用户的唯一标识
        action_dict:存储stream的行为链条
        o:当前的流处理数据
        e_cot:模型多接口事件的统计数据
        
    """
    label = "多接口事件"
    current_time = r_datetime.datetime.now()

    # 清理超过24小时的sessionid
    to_delete = []
    for sid, value in action_dict.items():
        if "timestamp" in value and current_time - value["timestamp"] > timedelta(hours=12):
            to_delete.append(sid)

    for sid in to_delete:
        del action_dict[sid]

    founds = False

    update_action = False

    # 判断多接口事件是否存在且存在于e_cot,如果存在获取到他的数量信息，然后根据入库统计数量信息，返回最终结果
    if label in label_info and sessionid:
        url = o.get("url")
        if sessionid not in action_dict: # 判断sessionid不存在与行为链条字典中,表示行为动作第一次添加
            action_dict[sessionid]={label:{"bhr_chain":[o],"timestamp":current_time}}

            # founds = True
        else:
            # 当前sessionid存在于行为链条中，判断标签是否存在
            if label not in action_dict[sessionid]:
                action_dict[sessionid]={label:{"bhr_chain":[o],"timestamp":current_time}}
            else:
                # 存在于行为链条中,获取当前得label标签值
                label_value = label_info.get(label)
                # 获取标签模型统计数量
                event_count = e_cot.get(label_value)
                if  len(action_dict[sessionid][label]["bhr_chain"])<event_count:
                    # 进行判断是否存在于链条中,只判断接口，参数，请求体 三者
                    url = o.get("url")
                    parameter =o.get("parameter")
                    request_body = o.get("request_body")
                    bhr_chain_set = {(item.get("url"), item.get("parameter"), item.get("request_body")) 
                     for item in action_dict[sessionid][label]["bhr_chain"]}
                    
                    if (url,parameter,request_body) in bhr_chain_set: # 如果已经存在，就无需存入，直接返回founds,和行为链条
                        founds= True
                    else:
                        # 将数据存入 并计算数量 如果达到数量则合并后的行为链条的信息
                        action_dict[sessionid][label]["bhr_chain"].append(o)
                        current_count = len(action_dict[sessionid][label]["bhr_chain"])
                        if current_count == event_count: # 判断数量相同
                            # 循环列表取出识别的值信息
                            all_data= [item.get("all_data",{}) for item in action_dict[sessionid][label]["bhr_chain"]]
                            merged_data = merge_data_dicts(all_data)
                            o["all_data"] = ujson.dumps(merged_data,ensure_ascii=False)
                            founds = True
                            return action_dict,founds,o
    else:
        founds = True
    return action_dict,founds,None

def merge_data_dicts(data_dicts):
    merged_data = {}
    for data in data_dicts:
        for http_pos, action_value in data.items():
            if http_pos not in merged_data:
                merged_data[http_pos] = {}
            for action, value_lst in action_value.items():
                if action not in merged_data[http_pos]:
                    merged_data[http_pos][action] = {}
                for name, value in value_lst.items():
                    # 如果 `name` 已经存在，则处理合并逻辑
                    if name in merged_data[http_pos][action]:
                        # 假设要合并的是列表或数值，可以调整逻辑
                        if isinstance(merged_data[http_pos][action][name], list):
                            merged_data[http_pos][action][name] += value
                        elif isinstance(merged_data[http_pos][action][name], (int, float)):
                            merged_data[http_pos][action][name] += value
                        else:
                            merged_data[http_pos][action][name] = value
                    else:
                        merged_data[http_pos][action][name] = value
    return merged_data
import base64
def decode_value(imp_decode:str,val_lst:Union[str,List[str]])->Union[str,List[str]]:
    """
    :param imp_decode: 解码规则
    :param val_lst: 解码数据
    :return:
    """
    # 如果解码规则为空，直接返回原数据
    if not imp_decode:
        return val_lst
    else:
        if imp_decode == "unicode":
            if  isinstance(val_lst, list):
                return [v.encode("utf-8").decode("unicode_escape") for v in val_lst]
            elif isinstance(val_lst, str):
                return val_lst.encode("utf-8").decode("unicode_escape")
        elif imp_decode == "base64":

            if  isinstance(val_lst, list):
                return [base64.b64decode(v).decode("utf-8") for v in val_lst]
            elif isinstance(val_lst, str):
                return base64.b64decode(val_lst).decode("utf-8")
        elif imp_decode == "bytes":
            lists= []
            if  isinstance(val_lst, list):
                # 第一次解析，把多层转义还原成 "b'\xe9\x92\x89\xe9\x92\x89'"
                for v in val_lst:
                    layer1 = ast.literal_eval(v)

                    # 第二次解析，把字符串变成真正的 bytes 对象
                    layer2 = ast.literal_eval(layer1)

                    # 然后 decode 成 utf-8 字符串
                    decoded_str = layer2.decode('utf-8')
                    lists.append(decoded_str)
                return lists

            elif isinstance(val_lst, str):
                layer1 = ast.literal_eval(val_lst)

                # 第二次解析，把字符串变成真正的 bytes 对象
                layer2 = ast.literal_eval(layer1)

                # 然后 decode 成 utf-8 字符串
                decoded_str = layer2.decode('utf-8')
                return decoded_str



if __name__ == '__main__':
    # company_list = [
    #     {'url': 'searchForHitList', '多接口事件': '详情', 'sessionid': 'c7318a9eaa425684db4052edca008c1b',"parameter":"page=1&pagesize=2","all_data":{"response_body":{"操作":{"会话ID":["abcfghd0000"]}}}},
    #     {"url": "selectListForPg", "多接口事件": "详情", "sessionid": "c7318a9eaa425684db4052edca008c1b",
    #      "request_body": '{"tableName":"gj_qxb_qyjbxxb","codition":{"eid":""},"page":2,"limit":10}',
    #      "response_body": '{"code":"请求成功！","这是第二个"}',"all_data":{"response_body":{"操作":{"会话ID2":["abcfghd000012121"]}}}},
    #      {"url": "selectListForPg", "多接口事件": "详情", "sessionid": "c7318a9eaa425684db4052edca008c1b",
    #      "request_body": '{"tableName":"gj_qxb_qyrizhixinxi","codition":{"eid":""},"page":2,"limit":10}',
    #      "response_body": '{"code":"请求成功！","这是第二个"}',"all_data":{"response_body":{"操作":{"会话ID3":["abcfghd0000131313"]}}}},
    # ]
    # action_dict = {}
    
    # e_cot = {"详情":3}
    
    # for o in company_list:
    #     sessionid = o.get("sessionid")
    #     label_info = {"多接口事件":"详情"}
    #     action_dict , founds,event_dic= session_action_relation(sessionid,action_dict,o,label_info,e_cot)
    #     print(event_dic)
    models = {"":{ "rules": {
            "操作>>问答": {
                "JSONid-m7lksmwx-uecgc3sj0_0": {
                    "imp_decode": "",
                    "request_body": [
                        "messages-[-1]"
                    ]
                }
            },
            "返回结果>>回答": {
                "多选id-m7lkt416-mol77zpdo_1": {
                    "response_body": {
                        "start": {
                            "str": "\"delta\":{\"content\":\""
                        },
                        "end": {
                            "str": "\"}}],\"created\":17405"
                        }
                    },
                    "imp_decode": ""
                }
            }
        }, 'label_info': {'app_name': '大数据智能开发平台', '日志类型': '操作事件'}, 'map_dic': {}, 'MapField': {}, 'dict_assoc': ''}}
    #model  = {'操作>>问答': {'JSONid-m7lksmwx-uecgc3sj0_0': {'imp_decode': '', 'request_body': ['messages-[-1]']}}, '返回结果>>回答': {'id-m7lkt416-mol77zpdo_1': {'response_body': {'start': {'str': '"delta":{"content":"'}, 'end': {'str': '"}}],"created":17405'}}, 'imp_decode': 'unicode'}}}
    models_acc = {"":
    {'rules': {
        '返回结果>>会话ID': {
            'id-m7twfh05-jej7iy5sg_0': {
                'response_headers': {
                    'Set-Cookie': {
                        'start': {
                            'str': 'fbi_session='
                        },
                        'end': {
                            'str': ';'
                        }
                    }
                },
                'imp_decode': ''
            }
        },
        '操作>>账户名': {
            'id-m7twfrs5-0vq0gg0yk_1': {
                'request_body': {
                    'start': {
                        'str': 'data={\"name\":\"'
                    },
                    'end': {
                        'str': '\",\"token\":0,\"au'
                    }
                },
                'imp_decode': ''
            }
        }
    },
    'condition': {
        'url': {
            'judge': '=',
            'msg': 'http://192.168.124.247:9999/auth'
        }
    },
    'label_info': {
        '日志类型': '账号登录'
    },
    'map_dic': {},
    'MapField': {},
    'dict_assoc': ''
}}

    o = {
                "time": "2025-03-04T09:57:38",
                "app": "192.168.124.247:9999",
                "app_name": "大数据智能开发平台",
                "flow_id": "2011742784883333",
                "urld": "http://192.168.124.247:9999/auth",
                "name": "用户登录",
                "account": "",
                "url": "http://192.168.124.247:9999/auth",
                "auth_type": 5,
                "cls": "[]",
                "levels": "",
                "srcip": "192.168.125.2",
                "real_ip": "192.168.125.2",
                "dstip": "192.168.124.247",
                "dstport": 9999,
                "http_method": "POST",
                "status": 200,
                "api_type": "0",
                "risk_level": "0",
                "qlength": 99,
                "yw_count": 0,
                "length": "68",
                "age": 4392,
                "srcport": 44854,
                "parameter": "",
                "content_length": 68,
                "id": "1741053458710549554",
                "content_type": "HTML",
                "key": "\"\"",
                "info": "{}",
                "request_headers": "[{\"name\":\"Host\",\"value\":\"192.168.124.247\"},{\"name\":\"X-Real-IP\",\"value\":\"192.168.125.2\"},{\"name\":\"X-Forwarded-For\",\"value\":\"192.168.125.2\"},{\"name\":\"X-Forwarded-Host\",\"value\":\"localhost\"},{\"name\":\"Connection\",\"value\":\"close\"},{\"name\":\"Content-Length\",\"value\":\"99\"},{\"name\":\"sec-ch-ua\",\"value\":\"\\\"Microsoft Edge\\\";v=\\\"117\\\", \\\"Not;A=Brand\\\";v=\\\"8\\\", \\\"Chromium\\\";v=\\\"117\\\"\"},{\"name\":\"Accept\",\"value\":\"*\\/*\"},{\"name\":\"Content-Type\",\"value\":\"application\\/x-www-form-urlencoded; charset=UTF-8\"},{\"name\":\"X-Requested-With\",\"value\":\"XMLHttpRequest\"},{\"name\":\"sec-ch-ua-mobile\",\"value\":\"?0\"},{\"name\":\"User-Agent\",\"value\":\"Mozilla\\/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit\\/537.36 (KHTML, like Gecko) Chrome\\/117.0.0.0 Safari\\/537.36 Edg\\/117.0.2045.31\"},{\"name\":\"sec-ch-ua-platform\",\"value\":\"\\\"Windows\\\"\"},{\"name\":\"Origin\",\"value\":\"https:\\/\\/192.168.124.247:4434\"},{\"name\":\"Sec-Fetch-Site\",\"value\":\"same-origin\"},{\"name\":\"Sec-Fetch-Mode\",\"value\":\"cors\"},{\"name\":\"Sec-Fetch-Dest\",\"value\":\"empty\"},{\"name\":\"Referer\",\"value\":\"https:\\/\\/192.168.124.247:4434\\/fbi\\/login.h5\"},{\"name\":\"Accept-Encoding\",\"value\":\"gzip, deflate, br\"},{\"name\":\"Accept-Language\",\"value\":\"zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6\"},{\"name\":\"Cookie\",\"value\":\"eng=9002; work_space=public; userName=superFBI\"}]",
                "response_headers": "[{\"name\":\"Server\",\"value\":\"gunicorn\"},{\"name\":\"Date\",\"value\":\"Tue, 04 Mar 2025 01:57:38 GMT\"},{\"name\":\"Connection\",\"value\":\"close\"},{\"name\":\"Content-Length\",\"value\":\"68\"},{\"name\":\"Content-Type\",\"value\":\"text\\/html; charset=UTF-8\"},{\"name\":\"Set-Cookie\",\"value\":\"fbi_session=f376adbfb64f9ea8df8f44c7ebfab993; HttpOnly; Max-Age=3600; Path=\\/; SameSite=None; Secure, eng=9001; Max-Age=3600; Path=\\/; SameSite=None; Secure, work_space=public; Max-Age=3600; Path=\\/; SameSite=None; Secure\"}]",
                "request_body": "data={\"name\":\"superFBI\",\"token\":0,\"auth_key\":\"RmJpQDMwNTA=\"}",
                "response_body": ""
            }
    
    res = read_model_identify(models_acc,o)
    print(res)


    #parameter = "page=0&size=10&queryCondition={"rules":[{"field":"noticeTitle","op":"like","value":"关于"},{"field":"publishOrmName","op":"like","value":"李"}],"groups":[],"op":"and"}&sort=updatedTime,desc"