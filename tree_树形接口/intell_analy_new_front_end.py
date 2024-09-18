import os
import copy
import time
import ujson
import pickle
import pandas as pd
from collections import defaultdict
import configparser

# 读取配置文件
path_config = configparser.ConfigParser()
path_config.read('./config.ini')
# path_config.read('config_window.ini')
# 获取字符信息# 获取 start_chars 和 end_chars
start_chars_str = path_config.get('Characters', 'start_chars')
end_chars_str = path_config.get('Characters', 'end_chars')
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
                    if imp_pos in http_data:
                        current_entry_data[imp_pos] = http_data[imp_pos]
                    imp["annotated_index"] = imps_lst.index(imp)
                    current_entry_data["imps"].append(imp)
                    # 更新分类数据字典
                    classified_groups[key].setdefault(idx,
                                                      current_entry_data)  # {“测试7”:{"1":{"imps":[],"parameter":""}}}

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
            for inx, imd_pos in value.items():
                # 给出存储容器信息
                imp_pos = {}
                ht_dic = {}
                # char_limit_list = {}
                ann_index_lst = []
                imp_uid_lst = []

                for imd, idx_pos in imd_pos.items():  # imd 为标识的数据，idx_pos为标识数据所在的位置，索引
                    # 找出数据的索引 信息
                    idx = idx_pos["idx"]
                    pos = idx_pos["pos"]
                    imp_uid = idx_pos["imp_uid"]
                    imp_uid_lst.append(imp_uid)
                    ann_index = idx_pos["ann_index"]
                    ann_index_lst.append(ann_index)
                    # 获取http当前信息
                    http_info = http_data.get(idx)

                    # 添加函数 去除掉imps之后 留下识别的字段信息，请求体跟响应体除外
                    ht_dic, imp_pos = data_search(http_info, imd, imp_pos, ht_dic)

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


def data_search(http_info, imd, imp_pos, ht_dic):
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
            if header_judge(data):
                data = ujson.loads(data)
                data, index_lst = headers_search(data, imd)
                if index_lst:
                    ht_dic.setdefault(http_key, {}).setdefault(imd, data)
                    imp_pos.setdefault(imd, index_lst)
            else:
                index_lst = body_par_search(data, imd)
                if index_lst:
                    ht_dic.setdefault(http_key, {}).setdefault(imd, data)
                    imp_pos.setdefault(imd, index_lst)
    return ht_dic, imp_pos


def header_judge(info):
    """
    :param info: 请求头 响应头 的字符串值
    :return:
    """
    if isinstance(info, str):
        if info.startswith("[{") and info.endswith("}]"):
            return True
    return False


def body_par_search(data, imd):
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


def headers_search(data, imd):
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
        char_limit = 20
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


def handle_project(con, o_data):
    """
    :param o_data: 经过分类之后的数据信息。{key:{"账户":{0:{"request_body":""}}}
    :return:
    """
    project_body, json_class_groups = analyze_handle(con, o_data)

    str_rules = {}
    for model_key, pro_dic in project_body.items():  # project_body: key:{"账户":{0:{"request_body":""}}}

        # imp_name 为用户提供的标识信息，pos_data则是 每个数据索引内标识信息存在的位置及索引位置
        for imp_name, pos_data in pro_dic.items():
            #  pos_data ： {0:{"request_body":}}
            for id, data in pos_data.items():  # id表示http数据的id索引，例如（0，1，2),data :
                imp_pos = data["imp_pos"]  # 从data中获取详情信息
                ann_index = data.get("ann_index", [])  # 获取标识信息的下标
                a_index = ann_index[0]
                imp_uid = data.get("imp_uid")
                # 需要对 data进行循环 这样才能动态的识别字段信息
                str_rules = dynamic_data(data, str_rules, imp_pos, imp_name, a_index, model_key, imp_uid)
    # print(json_class_groups)
    json_rules = fodr_rules(json_class_groups)
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


def dynamic_data(http_data, rules, imp_pos, imp_name, a_index, model_key, imp_uid):
    """
    :param http_data: 请求数据 ，需要动态获取数据信息 并进行识别，判断走那个识别
    :return:
    """
    for key, value in http_data.items():
        if key != "ann_index" and key != "imp_pos" and key != "imp_uid":
            tol_info = rule_info(value, imp_pos)
            if tol_info:
                rules.setdefault(model_key, {}).setdefault(imp_name, {}).setdefault(imp_uid[0] + f"_{str(a_index)}",
                                                                                    {key: tol_info})
    return rules


#                                                   ######保存规则信息######
# 增加规则数据信息
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
            return {"status": "Error", "message": str(e)}
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
            return {"status": "Error", "message": f"模型存储错误：{str(e)}"}
        # 写入之后 将其移动置我们原文件中，这样做避免出现报错问题
        try:
            os.replace(source_file, destination_file)
            return {"status": "Success", "message": "模型存储成功！"}
        except OSError as e:
            return {"status": "Error", "message": f"模型数据移动出错：{str(e)}"}

    else:
        # 文件不存在
        existing_data[model_key] = {
            "rules": rules,
            "condition": con,
            "label_info": linfo
        }
        res = dump_rules_pkl(existing_data, destination_file)
        return res


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
        return {"status": "Success", "message": "模型存储成功！"}
    except Exception as e:
        return {"status": "Error", "message": str(e)}


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
            return {"status": "Success", "msg": f"模型名-{path_name}-创建成功！"}
        else:
            return {"status": "Error", "msg": f"模型名-{path_name}-已经存在！"}
    else:
        # 不存在 x_p_bak这个文件，
        path_lst = [path_name]
        with open(x_p, "wb") as fp:
            pickle.dump(path_lst, fp)
        return {"status": "Success", "msg": f"模型名-{path_name}-创建成功！"}


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
                for http_pos, rle in imp_data.items():
                    current_data = o.get(http_pos, "")
                    if header_judge(current_data):

                        data_storage, l_info = headers_models(current_data, rle, http_pos, ch_name, data_storage,
                                                              l_info, dict_tree, MapField, assoc_str)

                    elif isinstance(current_data, list):
                        data_storage, l_info = headers_models(current_data, rle, http_pos, ch_name, data_storage,
                                                              l_info, dict_tree, MapField, assoc_str)
                    else:
                        data_storage, l_info = body_models(current_data, rle, http_pos, ch_name, data_storage, l_info,
                                                           dict_tree, MapField, assoc_str)

    return data_storage, l_info


def headers_models(current_data, pos_rules, http_pos, ch_name, data_storage, l_info, dict_tree=None, MapField=None,
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
                    start_pos, end_pos = s_e_str(start_str, end_str, values)
                    # 如果找到了起始字符串和结束字符串
                    if start_pos != -1 and end_pos != -1:
                        current_start = start_pos + start_offset
                        current_end = end_pos - end_offset
                        res = item["value"][current_start:current_end].strip()
                        ch_name_lst = ch_name.split(">>")  # 取0索引，但是我还是要判断一下>>存不存在，如果不想存在，就直接返回当前字符串了
                        if len(ch_name_lst) > 1:
                            ch_name = ch_name_lst[1]
                            type_name = ch_name_lst[0]
                        else:
                            type_name = ""
                        if res == "":
                            res = field_ch(MapField, ch_name, res)
                        if res != "" and res not in data_storage.setdefault(http_pos, {}).setdefault(type_name,
                                                                                                     {}).setdefault(
                            ch_name, []):
                            for end in end_chars:
                                if end in res:
                                    res = res[:res.index(end)]
                            res = field_ch(MapField, ch_name, res)  # 中文字段映射
                            res, l_info = dic_ass(ch_name, dict_tree, assoc_str, res, l_info)  # 字典映射
                            data_storage[http_pos][type_name][ch_name].append(res)
                else:
                    continue
    return data_storage, l_info


def body_models(data_source, pos_rules, http_pos, ch_name, data_storage, l_info, dict_tree=None, MapField=None,
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
    start_pos, end_pos = s_e_str(start_str, end_str, data_source)

    if start_pos != -1 and end_pos != -1:
        current_start = start_pos + start_offset
        current_end = end_pos - end_offset
        res = data_source[current_start:current_end].strip()
        # 根据空值会有搜索为空的信息，所以这里空值也进行存储
        # 对 ch_name 进行分割
        ch_name_lst = ch_name.split(">>")  # 取0索引，但是我还是要判断一下>>存不存在，如果不想存在，就直接返回当前字符串了
        if len(ch_name_lst) > 1:
            ch_name = ch_name_lst[1]
            type_name = ch_name_lst[0]
        else:
            type_name = ""
        if res == "":
            res = field_ch(MapField, ch_name, res)
        if res != "" and res not in data_storage.setdefault(http_pos, {}).setdefault(type_name, {}).setdefault(ch_name,
                                                                                                               []):
            for end in end_chars:
                if end in res:
                    res = res[:res.index(end)]
            res = field_ch(MapField, ch_name, res)  # 中文字段映射
            res, l_info = dic_ass(ch_name, dict_tree, assoc_str, res, l_info)  # 字典映射信息
            data_storage[http_pos][type_name][ch_name].append(res)

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
        return {"status": "Error", "msg": f"模型数据读取错误：{e.__str__()}"}

    # 删除模型名称
    new_tol_rulers = {}
    if model_key in tol_rulers:
        try:
            del tol_rulers[model_key]
            # 将模型数据写入副本文件 中

            res = write_replace(source_file, destination_file, tol_rulers)
            if res.get("status") == "Success":
                return {"status": "Success", "msg": f"子模型-{model_key}-删除成功！"}
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
                    return {"status": "Success", "msg": f"子模型-{model_key}-删除成功！"}
                else:
                    return res
            except:
                return {"status": "Error", "msg": f"子模型-{model_key}-删除错误"}

    else:
        return {"status": "Error", "msg": f"子模型-{model_key}-模型数据不存在！"}


def write_replace(source_file, destination_file, tol_rulers):
    # 将模型数据写入副本文件 中
    try:
        with open(source_file, "wb") as fp:
            pickle.dump(tol_rulers, fp)
    except OSError as e:
        return {"status": "Error", "message": f"模型存储错误：{str(e)}"}
    # 写入之后 将其移动置我们原文件中，这样做避免出现报错问题
    try:
        os.replace(source_file, destination_file)
        return {"status": "Success", "message": "模型存储成功！"}
    except OSError as e:
        return {"status": "Error", "message": f"模型数据移动出错：{str(e)}"}


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
            return {"status": "Error", "message": f"模型文件格式错误：{e.__str__()}"}

        # 现在需要读取最新文件信息
        try:
            with open(old_model_file, "rb") as fp:
                old_data = pickle.load(fp)
        except Exception as e:
            return {"status": "Error", "message": f"读取当前模型失败：{e.__str__()}"}

        # 需要将两个文件合并到一起，如果模型名称相同怎么办,分为 覆盖，保留原始值，或者合并，将三种情况全部写出来吧
        # ① 保留当前模型的值，祛除导入模型的值
        try:
            for current_key, current_value in loaded_data.items():
                if current_key not in old_data:
                    old_data[current_key] = current_value
        except Exception as e:
            return {"status": "Error", "message": f"模型覆盖错误：{e.__str__()}"}
        res = write_replace(source_file, old_model_file, old_data)
        # ② 覆盖原值,将导入的值作为新值覆盖掉旧值
        # old_data.update(loaded_data)

        # ③ 合并模型，保留两个模型中相同的key，将两个模型中不同的key合并到一起，这个是将模型转化为列表存储了
        return res
    else:
        try:
            os.replace(upload_file, old_model_file)
            return {"status": "Success", "message": "模型存储成功！"}
        except OSError as e:
            return {"status": "Error", "message": f"模型数据移动出错{str(e)}"}


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
        target = preprocess_target(imp_data)
        # 进行递归查找，这个是做了全局的查找了

        paths_dict = find_values_in_dict_little(data_soure, target, imp_type)

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
        for index, item in enumerate(data):
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
    最老版本 嵌套不能用
    :param data_source:
    :param path:
    :param value_lst:
    :return:
    """
    # 先将请求响应体进行转化为dict对象
    try:
        current = ujson.loads(data_source)

    except:
        current = data_source

    # 从给定的数据中进行识别
    if isinstance(current, dict):
        temp_current = current
        found = True
        path_list = path.split(".")
        for p in path_list:
            # 循环当前path 每段路径，先判断JSON数据
            if p.endswith("-JSON"):
                key = p.split("-")[0]
                temp_current = temp_current.get(key)
                if not current:
                    found = False
                    break
                temp_current = ujson.loads(temp_current)
            # 判断是否为列表数据
            elif "-[" in p:
                key, index = p.split("-[")
                key = key.strip()
                index = int(index[:-1])
                temp_current = temp_current.get(key, [])  # 获取到该key值 下面的列表
                if not temp_current or index >= len(temp_current):
                    found = False
                    break
                # 已经判断是列表，进行循环查询数据

                # temp_current = temp_current[index]
                # 新增代码 判断循环列表数据
                if isinstance(temp_current, list) and path_list.index(p) < len(path_list) - 1 and (
                        "-[" not in path_list[
                    path_list.index(p) + 1]):
                    for item in temp_current:
                        value = item.get(path_list[path_list.index(p) + 1])
                        if value:
                            found = True
                            value_lst.append(value)
                temp_current = temp_current[index]
            else:

                temp_current = temp_current.get(p)
            if not temp_current:
                found = False
                break
        if found and not isinstance(temp_current, list):
            if temp_current not in value_lst:
                value_lst.append(temp_current)
            return value_lst
    return []


def get_value_by_path2(data_source, path, value_lst):
    """
    最新修改完列表值获取的操作
    :param data_source:
    :param path:
    :param value_lst:
    :return:
    """
    try:
        current = ujson.loads(data_source) if isinstance(data_source, str) else data_source
    except:
        current = data_source
    # 加一个条件当前路径在列表中的索引,用作最后的值判断啊
    idx_in_lst = 0  # 默认为0
    if isinstance(current, dict):
        temp_current = current
        found = True
        path_list = path.split(".")
        for index, p in enumerate(path_list):
            if p.endswith("-JSON"):
                key = p.split("-")[0]
                temp_current = temp_current.get(key)
                idx_in_lst = index
                if not temp_current:
                    found = False
                    break
                temp_current = ujson.loads(temp_current)
            elif "-LIST" in p:
                key, _ = p.split("-LIST")
                key = key.strip()

                temp_current = temp_current.get(key, [])  # 循环到这里就是一个列表信息
                idx_in_lst = index
                if not temp_current:
                    found = False
                    break
                if p != path_list[-1]:  # 如果路径还未结束，则需要继续处理列表中的元素

                    for item in temp_current:  # 循环该列表信息
                        value_lst = get_value_by_path(item, ".".join(path_list[index + 1:]), value_lst)
                    break
                # 不再需要这个else，因为已经在循环中添加了列表中的每个元素
            else:
                temp_current = temp_current.get(p)
                idx_in_lst = index
            if not temp_current:
                found = False
                break

        # if found and not isinstance(temp_current, list):
        # 判断 当前值不为列表值，如果是列表值则当前的路径必须是最后段
        if found and ((not isinstance(temp_current, list)) or (
                (isinstance(temp_current, list)) and idx_in_lst == len(path_list) - 1)):
            if temp_current not in value_lst:
                value_lst.append(temp_current)

    return value_lst


def get_value_by_path3(data_source, path, value_lst):
    """
    最新修改完列表值上添加索引操作
    :param data_source:
    :param path:
    :param value_lst:
    :return:
    """
    try:
        current = ujson.loads(data_source) if isinstance(data_source, str) else data_source
    except:
        current = data_source
    # 加一个条件当前路径在列表中的索引,用作最后的值判断啊
    idx_in_lst = 0  # 默认为0
    if isinstance(current, dict):
        temp_current = current
        found = True
        path_list = path.split(".")
        for index, p in enumerate(path_list):
            if p.endswith("-JSON"):
                key = p.split("-")[0]
                temp_current = temp_current.get(key)
                idx_in_lst = index
                if not temp_current:
                    found = False
                    break
                temp_current = ujson.loads(temp_current)
            elif "-LIST" in p:
                key, _ = p.split("-LIST")
                key = key.strip()

                temp_current = temp_current.get(key, [])  # 循环到这里就是一个列表信息
                idx_in_lst = index
                if not temp_current:
                    found = False
                    break
                if p != path_list[-1]:  # 如果路径还未结束，则需要继续处理列表中的元素

                    for item in temp_current:  # 循环该列表信息
                        value_lst = get_value_by_path(item, ".".join(path_list[index + 1:]), value_lst)
                    break
                # 不再需要这个else，因为已经在循环中添加了列表中的每个元素
            elif "-[" in p and p.endswith("]"):
                key, index = p.split("-[")
                key = key.strip()
                index = int(index[:-1])
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

        # if found and not isinstance(temp_current, list):
        # 判断 当前值不为列表值，如果是列表值则当前的路径必须是最后段
        if found and ((not isinstance(temp_current, list)) or (
                (isinstance(temp_current, list)) and idx_in_lst == len(path_list) - 1)):
            if temp_current not in value_lst:
                value_lst.append(temp_current)

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


def model_data_extract(ch_name, o, data_storage, imp_data, l_info, dict_tree=None, MapField=None, assoc_str=""):
    """
    用于xlink中处理
    :param ch_name:
    :param o:
    :param ch_data:
    :param data_storage:
    :return:
    """

    for http_pos, rle_lst in imp_data.items():
        current_data = o.get(http_pos, "")
        if current_data:
            for t_rule in rle_lst:
                value_lst = []
                value_lst = get_value_by_path(current_data, t_rule, value_lst)
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


# add rzc on 2024/7/17 针对子模型标签信息进行判断
def label_judge(model_data, label_key, label_name):
    model_file_data = {}
    for model_key, rule_data in model_data.items():
        label_info = rule_data.get("label_info", {})
        if label_info.get(label_key) == label_name:
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


def intell_sen1(model_file_data, monitor):
    key_ch = {"response_body": "响应体", "request_body": "请求体", "parameter": "参数"}
    total_info = {}
    total_count = {}
    info = {}
    level_lst = []
    cls_lst = []
    count = {}
    max_level = 0
    # sen_level = {"1":"L1","2":"L2","3":"L3","4":"L4"}
    sen_level = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
    analy_data = read_model_identify(model_file_data, monitor)
    if isinstance(analy_data, dict):
        imp_data = analy_data.get("data")
        if imp_data:
            for pos, rule_data in imp_data.items():
                ch_pos = key_ch.get(pos, pos)
                sens = {}
                for cls_level, sen_data in rule_data.items():
                    cls, level_ch = cls_level.split("-")
                    level_lst.append(int(sen_level.get(level_ch)))
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
                count.setdefault(ch_pos, {k: len(list(set(v))) for k, v in sens.items()})

            if level_lst:
                max_level = max(level_lst)
            else:
                max_level = 0
            cls_lst = list(set(cls_lst))
    return total_info, total_count, max_level, info, cls_lst, count


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
                if str(v) in ch_map:
                    res_lst.append(ch_map[str(v)])
            return res_lst
        elif isinstance(res, str):

            ch_map = MapField[ch_name]
            if str(res) in ch_map:
                res = ch_map[str(res)]
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
    if label_info.get("接口详情") == "登录":
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
        user_infos["date"] = datetime.datetime.now()
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
    new_date = datetime.datetime.now()
    for key, value in user_info.items():
        if (new_date - value.get("date")).total_seconds() // 3600 >= 25:
            remove_key.append(key)
        # del user_info[key]
    for key in remove_key:
        del user_info[key]
        del user_dic[key]
    # dump_pkl("/data/xlink/user_info.pkl", user_info)


if __name__ == '__main__':
    model_data = {

        "地址解析": {'rules': {'地址信息-L1>>详细地址': {
            'JSON1118690.892120725_0': {'response_body': ['result.addressComponent.address']}}, '地址信息-L1>>城市': {
            'JSON1118690.89217796_1': {'response_body': ['result.addressComponent.city']}}, '地址信息-L1>>国家': {
            'JSON1118690.892217229_2': {'response_body': ['result.addressComponent.nation']}}, '地址信息-L1>>城区': {
            'JSON1118690.892250598_3': {'response_body': ['result.addressComponent.county']}}, '省份': {
            'JSON1118690.892289247_4': {'response_body': ['result.addressComponent.province']}}},
            'condition': {'app': {'judge': '=', 'msg': '100.12.66.55'},
                          'url': {'judge': '=', 'msg': 'http://100.12.66.55/api/geocoder'}},
            'label_info': {'日志类型': '敏感监测', "源日志信息": "HTTP"}},
        "测试1": {'rules': {'登录令牌>>令牌': {
            '1026762.157071206_0': {'request_headers': {'Authorization': {'start': {}, 'end': {}}}}}},
            'condition': {'app': {'judge': 'in', 'msg': ['192.168.229.156', '192.168.23.202']}},
            'label_info': {'name': '测试', '日志类型': '业务访问', "源日志信息": "DBMS"}},
        "账号登录": {'rules': {'返回结果>>账户': {
            '1027799.015130446_0': {'request_body': {'start': {'str': '&username='}, 'end': {'str': '&'}}}},
            '操作>>密码': {'1027799.082829513_1': {
                'request_body': {'start': {'str': '&password='}, 'end': {'str': '&'}}}},
            '返回结果>>会话ID': {'1027799.10287347_2': {
                'request_headers': {'Cookie': {'start': {'str': 'JSESSIONID='}, 'end': {}}}}}},
            'condition': {'app': {'judge': '=', 'msg': '41.204.84.91:9090'},
                          'urld': {'judge': '=', 'msg': 'http://41.204.84.91:9090/login.jsp'}},
            'label_info': {'name': '', '日志类型': '业务访问', "源日志信息": "HTTP"}}
    }
    # label_key = "日志类型"
    # label_name = "敏感监测"
    # model_file_data = label_judge(model_data, label_key, label_name)
    # print(model_file_data)
    label_name_list = ["敏感监测", "业务访问"]
    log_type_list = ["HTTP", "DBMS"]
    # model_file_datas = MoreSourceModel(model_data, label_name_list, log_type_list)
    # print(model_file_datas)
    file_str = "operevent"
    base_dir = "./models_paths/"
    source_file = os.path.join(base_dir, f"{file_str}_rcl.pkl")
    if os.path.exists(source_file):
        with open(source_file, "rb") as fp:
            an = pickle.load(fp)
    print(an)
    olist = [{
        "time": "2024-08-29T10:37:37",
        "app": "59.202.68.95:8215",
        "app_name": "高质量数据中心",
        "flow_id": "78906584529497",
        "urld": "http://59.202.68.95:8215/dataasset/api/dataasset/other/queryOrgTree",
        "url": "http://59.202.68.95:8215/dataasset/api/dataasset/other/queryOrgTree",
        "name": "数据目录-目录管理-组织结构",
        "account": "徐君",
        "auth_type": 5,
        "dstport": 8215,
        "srcip": "10.18.80.10",
        "parameter": "uuid=ORG_21C028E1CF26409E80A270821D44AC4C",
        "real_ip": "",
        "http_method": "POST",
        "status": 200,
        "api_type": "5",
        "qlength": 0,
        "yw_count": 0,
        "length": "14604",
        "user_info": "{\"账户名\": \"徐君\", \"职位名称\": \"瑞成科技\", \"工作电话\": \"0571-0000000\"}",
        "srcport": 53759,
        "dstip": "59.202.68.95",
        "risk_level": "1",
        "content_length": 14604,
        "id": "1724899257612872868",
        "age": 27062,
        "content_type": "JSON",
        "key": "\"\"",
        "info": "{}",
        "request_headers": "[{\"name\":\"Host\",\"value\":\"59.202.68.95:8215\"},{\"name\":\"Connection\",\"value\":\"keep-alive\"},{\"name\":\"Content-Length\",\"value\":\"0\"},{\"name\":\"Accept\",\"value\":\"application\\/json, text\\/plain, *\\/*\"},{\"name\":\"Pragma\",\"value\":\"no-cache\"},{\"name\":\"Cache-Control\",\"value\":\"no-cache, no-store\"},{\"name\":\"X-Requested-With\",\"value\":\"XMLHttpRequest\"},{\"name\":\"access_token\",\"value\":\"f05856f2c95746e77cd220b231bffe12\"},{\"name\":\"User-Agent\",\"value\":\"Mozilla\\/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit\\/537.36 (KHTML, like Gecko) Chrome\\/120.0.0.0 Safari\\/537.36\"},{\"name\":\"Origin\",\"value\":\"http:\\/\\/59.202.68.95:8215\"},{\"name\":\"Referer\",\"value\":\"http:\\/\\/59.202.68.95:8215\\/dataSheet?activeId=302C64A00D6B458799DEEE96BDB442B1\"},{\"name\":\"Accept-Encoding\",\"value\":\"gzip, deflate\"},{\"name\":\"Accept-Language\",\"value\":\"zh-CN,zh;q=0.9\"},{\"name\":\"Cookie\",\"value\":\"JSESSIONID=46C46EF23678E74686464D2D3C3AC48C; wyhtml=\\/dataasset\\/_1918c9ecaa25735_1724641102498\"}]",
        "response_headers": "[{\"name\":\"Server\",\"value\":\"nginx\\/1.24.0\"},{\"name\":\"Date\",\"value\":\"Thu, 29 Aug 2024 02:37:37 GMT\"},{\"name\":\"Content-Type\",\"value\":\"text\\/json;charset=UTF-8\"},{\"name\":\"Content-Length\",\"value\":\"14604\"},{\"name\":\"Connection\",\"value\":\"keep-alive\"},{\"name\":\"Cache-Control\",\"value\":\"no-cache\"},{\"name\":\"Expires\",\"value\":\"0\"},{\"name\":\"Pragma\",\"value\":\"No-cache\"},{\"name\":\"Content-Language\",\"value\":\"zh-CN\"},{\"name\":\"Access-Control-Allow-Origin\",\"value\":\"*\"},{\"name\":\"Access-Control-Allow-Headers\",\"value\":\"X-Requested-With\"},{\"name\":\"Access-Control-Allow-Methods\",\"value\":\"GET,POST,OPTIONS\"}]",
        "request_body": "",
        "response_body": "{\"success\":true,\"fieldErrors\":{},\"actionErrors\":[],\"messages\":[\"操作成功\"],\"totalCount\":17,\"data\":[{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委领导\",\"crorgLevelCode\":\"060000\",\"crorgName\":\"拱墅区委领导\",\"crorgOrder\":597,\"crorgOuterUuid\":\"GO_17da9e84bad74f5abc4b7a0e327dfd73\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576455,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_F1B0DA8C766E48FB989B00AAA216DBC9\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":true,\"levelCode\":\"060000\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":597,\"parent\":false,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委领导\",\"type\":\"2\",\"unid\":5576455,\"uuid\":\"ORG_F1B0DA8C766E48FB989B00AAA216DBC9\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委办公室\",\"crorgLevelCode\":\"060001\",\"crorgName\":\"拱墅区委办公室\",\"crorgOrder\":991,\"crorgOuterUuid\":\"GO_caba3451996746278cb486da6d35153a\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576456,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_6F8BDFED24AE4DD6AFE00FC67D0E0BDF\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060001\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":991,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委办公室\",\"type\":\"2\",\"unid\":5576456,\"uuid\":\"ORG_6F8BDFED24AE4DD6AFE00FC67D0E0BDF\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区纪委区监委\",\"crorgLevelCode\":\"060002\",\"crorgName\":\"拱墅区纪委区监委\",\"crorgOrder\":1360,\"crorgOuterUuid\":\"GO_c4f4a71a902f4c9aa9f268be9197c219\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576457,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_359556E3BD8149C6AFD40E6650C668C7\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060002\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":1360,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区纪委区监委\",\"type\":\"2\",\"unid\":5576457,\"uuid\":\"ORG_359556E3BD8149C6AFD40E6650C668C7\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委组织部\",\"crorgLevelCode\":\"060003\",\"crorgName\":\"拱墅区委组织部\",\"crorgOrder\":1710,\"crorgOuterUuid\":\"GO_2d0a4ad40a3b40d9be5938865101d694\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576458,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_6757E6884D044C029A790095ED8D4AE4\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060003\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":1710,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委组织部\",\"type\":\"2\",\"unid\":5576458,\"uuid\":\"ORG_6757E6884D044C029A790095ED8D4AE4\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委宣传部\",\"crorgLevelCode\":\"060004\",\"crorgName\":\"拱墅区委宣传部\",\"crorgOrder\":2029,\"crorgOuterUuid\":\"GO_fe954d4f65db477498e50f6915140d32\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576459,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_E3F4DD397B2840088A71F1ED0DAEDE42\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060004\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":2029,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委宣传部\",\"type\":\"2\",\"unid\":5576459,\"uuid\":\"ORG_E3F4DD397B2840088A71F1ED0DAEDE42\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委统战部\",\"crorgLevelCode\":\"060005\",\"crorgName\":\"拱墅区委统战部\",\"crorgOrder\":2314,\"crorgOuterUuid\":\"GO_d2e5fd0d432d4182972d9bdc37421867\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576460,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_906A2B2D6F504A33BFB9CB67F8A078EE\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060005\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":2314,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委统战部\",\"type\":\"2\",\"unid\":5576460,\"uuid\":\"ORG_906A2B2D6F504A33BFB9CB67F8A078EE\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委政法委\",\"crorgLevelCode\":\"060006\",\"crorgName\":\"拱墅区委政法委\",\"crorgOrder\":2553,\"crorgOuterUuid\":\"GO_c5b087c3d895486d80e0982347c83fde\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576461,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_567B44AC197B4558A33FE470CA97A0A1\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060006\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":2553,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委政法委\",\"type\":\"2\",\"unid\":5576461,\"uuid\":\"ORG_567B44AC197B4558A33FE470CA97A0A1\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委改革办\",\"crorgLevelCode\":\"060007\",\"crorgName\":\"拱墅区委改革办\",\"crorgOrder\":2759,\"crorgOuterUuid\":\"GO_fc60d6e048204209ab092e401edcffaa\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576462,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_2FF96EDD1094407F965D518DB05528B5\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060007\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":2759,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委改革办\",\"type\":\"2\",\"unid\":5576462,\"uuid\":\"ORG_2FF96EDD1094407F965D518DB05528B5\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委政研室\",\"crorgLevelCode\":\"060008\",\"crorgName\":\"拱墅区委政研室\",\"crorgOrder\":2928,\"crorgOuterUuid\":\"GO_0d38034d9a3a4aaeb923f05b244cc6f5\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576463,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_42CCD11143684939AEA326121BE26850\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":true,\"levelCode\":\"060008\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":2928,\"parent\":false,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委政研室\",\"type\":\"2\",\"unid\":5576463,\"uuid\":\"ORG_42CCD11143684939AEA326121BE26850\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委编办\",\"crorgLevelCode\":\"060009\",\"crorgName\":\"拱墅区委编办\",\"crorgOrder\":3064,\"crorgOuterUuid\":\"GO_0f28be9f989443068bb06158e02e291e\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576464,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_F5CEC5DEC4374823BC35E03C58FB5E2B\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060009\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3064,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委编办\",\"type\":\"2\",\"unid\":5576464,\"uuid\":\"ORG_F5CEC5DEC4374823BC35E03C58FB5E2B\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委直属机关工委\",\"crorgLevelCode\":\"06000A\",\"crorgName\":\"拱墅区委直属机关工委\",\"crorgOrder\":3177,\"crorgOuterUuid\":\"GO_36d848d6dcda4af399a358555b398664\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576465,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_E8A7DEBE3DDF4410B34DED9F3CAB6B0E\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000A\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3177,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委直属机关工委\",\"type\":\"2\",\"unid\":5576465,\"uuid\":\"ORG_E8A7DEBE3DDF4410B34DED9F3CAB6B0E\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委巡察机构\",\"crorgLevelCode\":\"06000B\",\"crorgName\":\"拱墅区委巡察机构\",\"crorgOrder\":3270,\"crorgOuterUuid\":\"GO_e67d034429aa43378e5e63c6683eea11\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576466,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_878E9A6C79544938A6D649579E55F38B\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000B\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3270,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委巡察机构\",\"type\":\"2\",\"unid\":5576466,\"uuid\":\"ORG_878E9A6C79544938A6D649579E55F38B\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区信访局\",\"crorgLevelCode\":\"06000C\",\"crorgName\":\"拱墅区信访局\",\"crorgOrder\":3348,\"crorgOuterUuid\":\"GO_cb8637b3616640ac91464931bd3bbb91\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576467,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_E03D96311D7548468DA29F1C7441E040\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000C\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3348,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区信访局\",\"type\":\"2\",\"unid\":5576467,\"uuid\":\"ORG_E03D96311D7548468DA29F1C7441E040\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委老干部局\",\"crorgLevelCode\":\"06000D\",\"crorgName\":\"拱墅区委老干部局\",\"crorgOrder\":3421,\"crorgOuterUuid\":\"GO_55e6368393a14eae90b03b8da363982e\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576468,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_8C72187200B94178B0409D6B4FD70699\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000D\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3421,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委老干部局\",\"type\":\"2\",\"unid\":5576468,\"uuid\":\"ORG_8C72187200B94178B0409D6B4FD70699\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委党史研究室\",\"crorgLevelCode\":\"06000E\",\"crorgName\":\"拱墅区委党史研究室\",\"crorgOrder\":3484,\"crorgOuterUuid\":\"GO_afae709447654bfb97bffcfd66fc8f69\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576469,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_279EF9C45AD34C21B8F797A70A30C870\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000E\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3484,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委党史研究室\",\"type\":\"2\",\"unid\":5576469,\"uuid\":\"ORG_279EF9C45AD34C21B8F797A70A30C870\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区关工委\",\"crorgLevelCode\":\"06000F\",\"crorgName\":\"拱墅区关工委\",\"crorgOrder\":3541,\"crorgOuterUuid\":\"GO_b758a3f121ed4c48b09297e4477b471a\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576470,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_4606D946D5314C10BB053D9B2FBEC8C6\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000F\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3541,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区关工委\",\"type\":\"2\",\"unid\":5576470,\"uuid\":\"ORG_4606D946D5314C10BB053D9B2FBEC8C6\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区社会治理中心\",\"crorgLevelCode\":\"06000G\",\"crorgName\":\"拱墅区社会治理中心\",\"crorgOrder\":3588,\"crorgOuterUuid\":\"GO_3c9b0329f140443fbd042f75d7603cde\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576471,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_0DEDE216398C41E49206EB1B2A630F2E\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000G\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3588,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区社会治理中心\",\"type\":\"2\",\"unid\":5576471,\"uuid\":\"ORG_0DEDE216398C41E49206EB1B2A630F2E\"}]}",
        "request_body_json": "{}",
        "parameter_json": "{}"
    },
        {
            "time": "2024-08-29T11:30:47",
            "app": "59.202.68.95:8215",
            "app_name": "高质量数据中心",
            "flow_id": "1628337715433374",
            "urld": "http://59.202.68.95:8215/dataasset/api/dataasset/dataDictionary/likeTree",
            "url": "http://59.202.68.95:8215/dataasset/api/dataasset/dataDictionary/likeTree",
            "name": "标签/目录组",
            "account": "徐君",
            "auth_type": 5,
            "dstport": 8215,
            "srcip": "10.18.80.10",
            "parameter": "uuid=393D43AE73EB483DAC22040B128C936C",
            "real_ip": "",
            "http_method": "POST",
            "status": 200,
            "api_type": "5",
            "qlength": 0,
            "yw_count": 0,
            "length": "1959",
            "user_info": "{\"账户名\": \"徐君\", \"职位名称\": \"瑞成科技\", \"工作电话\": \"0571-0000000\"}",
            "srcport": 58597,
            "dstip": "59.202.68.95",
            "risk_level": "0",
            "content_length": 1959,
            "id": "1724902448006303782",
            "age": 63093,
            "content_type": "JSON",
            "key": "\"\"",
            "info": "{}",
            "request_headers": "[{\"name\":\"Host\",\"value\":\"59.202.68.95:8215\"},{\"name\":\"Connection\",\"value\":\"keep-alive\"},{\"name\":\"Content-Length\",\"value\":\"0\"},{\"name\":\"Accept\",\"value\":\"application\\/json, text\\/plain, *\\/*\"},{\"name\":\"Pragma\",\"value\":\"no-cache\"},{\"name\":\"Cache-Control\",\"value\":\"no-cache, no-store\"},{\"name\":\"X-Requested-With\",\"value\":\"XMLHttpRequest\"},{\"name\":\"access_token\",\"value\":\"f05856f2c95746e77cd220b231bffe12\"},{\"name\":\"User-Agent\",\"value\":\"Mozilla\\/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit\\/537.36 (KHTML, like Gecko) Chrome\\/120.0.0.0 Safari\\/537.36\"},{\"name\":\"Origin\",\"value\":\"http:\\/\\/59.202.68.95:8215\"},{\"name\":\"Referer\",\"value\":\"http:\\/\\/59.202.68.95:8215\\/dataDict?activeId=FE70463C68E146CAAC591A15250D4721\"},{\"name\":\"Accept-Encoding\",\"value\":\"gzip, deflate\"},{\"name\":\"Accept-Language\",\"value\":\"zh-CN,zh;q=0.9\"},{\"name\":\"Cookie\",\"value\":\"JSESSIONID=46C46EF23678E74686464D2D3C3AC48C; wyhtml=\\/dataasset\\/_1918c9ecaa25735_1724641102498\"}]",
            "response_headers": "[{\"name\":\"Server\",\"value\":\"nginx\\/1.24.0\"},{\"name\":\"Date\",\"value\":\"Thu, 29 Aug 2024 03:30:47 GMT\"},{\"name\":\"Content-Type\",\"value\":\"text\\/json;charset=UTF-8\"},{\"name\":\"Content-Length\",\"value\":\"1959\"},{\"name\":\"Connection\",\"value\":\"keep-alive\"},{\"name\":\"Cache-Control\",\"value\":\"no-cache\"},{\"name\":\"Expires\",\"value\":\"0\"},{\"name\":\"Pragma\",\"value\":\"No-cache\"},{\"name\":\"Content-Language\",\"value\":\"zh-CN\"},{\"name\":\"Access-Control-Allow-Origin\",\"value\":\"*\"},{\"name\":\"Access-Control-Allow-Headers\",\"value\":\"X-Requested-With\"},{\"name\":\"Access-Control-Allow-Methods\",\"value\":\"GET,POST,OPTIONS\"}]",
            "request_body": "",
            "response_body": "{\"success\":true,\"fieldErrors\":{},\"actionErrors\":[],\"messages\":[],\"totalCount\":2,\"data\":[{\"binType\":0,\"cmmNodeType\":\"1\",\"code\":\"database\",\"crdctCode\":\"database\",\"crdctCractUuid\":\"CRACT_UUID_1\",\"crdctCreateTime\":\"2022-11-10 17:26:57\",\"crdctLevelCode\":\"000H010000\",\"crdctName\":\"数据库\",\"crdctOrder\":1,\"crdctParentUuid\":\"393D43AE73EB483DAC22040B128C936C\",\"crdctPathCode\":\"/DICT/BIGDATA/RDMP/dataformat/database\",\"crdctRemarks\":\"\",\"crdctStatus\":\"1\",\"crdctType\":\"1\",\"crdctUnid\":2064302,\"crdctUpdateTime\":\"2022-11-10 17:26:57\",\"crdctUuid\":\"3B04511313724BB289E4F6B663B8FA58\",\"crdctValue\":\"\",\"depth\":5,\"ext\":{},\"fullType\":\"11\",\"iconSkin\":\"xtree-depth-5 xtree-type-1 \",\"intMap\":{},\"lastUpdateTime\":\"2022-11-10 17:26:57\",\"leaf\":false,\"levelCode\":\"000H010000\",\"majorType\":\"1\",\"minorType\":\"1\",\"order\":1,\"parent\":true,\"parentUuid\":\"393D43AE73EB483DAC22040B128C936C\",\"pathCode\":\"/DICT/BIGDATA/RDMP/dataformat/database\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"数据库\",\"unid\":2064302,\"uuid\":\"3B04511313724BB289E4F6B663B8FA58\"},{\"binType\":0,\"cmmNodeType\":\"1\",\"code\":\"picture\",\"crdctCode\":\"picture\",\"crdctCractUuid\":\"CRACT_UUID_1\",\"crdctCreateTime\":\"2022-11-10 17:27:07\",\"crdctLevelCode\":\"000H010001\",\"crdctName\":\"图形图像\",\"crdctOrder\":3,\"crdctParentUuid\":\"393D43AE73EB483DAC22040B128C936C\",\"crdctPathCode\":\"/DICT/BIGDATA/RDMP/dataformat/picture\",\"crdctRemarks\":\"\",\"crdctStatus\":\"1\",\"crdctType\":\"1\",\"crdctUnid\":2064303,\"crdctUpdateTime\":\"2022-11-10 17:27:07\",\"crdctUuid\":\"053E7EE50F6144728AF0BC5B6B7B4341\",\"crdctValue\":\"\",\"depth\":5,\"ext\":{},\"fullType\":\"11\",\"iconSkin\":\"xtree-depth-5 xtree-type-1 \",\"intMap\":{},\"lastUpdateTime\":\"2022-11-10 17:27:07\",\"leaf\":false,\"levelCode\":\"000H010001\",\"majorType\":\"1\",\"minorType\":\"1\",\"order\":3,\"parent\":true,\"parentUuid\":\"393D43AE73EB483DAC22040B128C936C\",\"pathCode\":\"/DICT/BIGDATA/RDMP/dataformat/picture\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"图形图像\",\"unid\":2064303,\"uuid\":\"053E7EE50F6144728AF0BC5B6B7B4341\"}]}",
            "request_body_json": "{}",
            "parameter_json": "{}"
        }
    ]
    dict_o = {
        "time": "2024-08-29T11:30:47",
        "app": "59.202.68.95:8215",
        "app_name": "高质量数据中心",
        "flow_id": "1628337715433374",
        "urld": "http://59.202.68.95:8215/dataasset/api/dataasset/dataDictionary/likeTree",
        "url": "http://59.202.68.95:8215/dataasset/api/dataasset/dataDictionary/likeTree",
        "name": "标签/目录组",
        "account": "徐君",
        "auth_type": 5,
        "dstport": 8215,
        "srcip": "10.18.80.10",
        "parameter": "uuid=393D43AE73EB483DAC22040B128C936C",
        "real_ip": "",
        "http_method": "POST",
        "status": 200,
        "api_type": "5",
        "qlength": 0,
        "yw_count": 0,
        "length": "1959",
        "user_info": "{\"账户名\": \"徐君\", \"职位名称\": \"瑞成科技\", \"工作电话\": \"0571-0000000\"}",
        "srcport": 58597,
        "dstip": "59.202.68.95",
        "risk_level": "0",
        "content_length": 1959,
        "id": "1724902448006303782",
        "age": 63093,
        "content_type": "JSON",
        "key": "\"\"",
        "info": "{}",
        "request_headers": "[{\"name\":\"Host\",\"value\":\"59.202.68.95:8215\"},{\"name\":\"Connection\",\"value\":\"keep-alive\"},{\"name\":\"Content-Length\",\"value\":\"0\"},{\"name\":\"Accept\",\"value\":\"application\\/json, text\\/plain, *\\/*\"},{\"name\":\"Pragma\",\"value\":\"no-cache\"},{\"name\":\"Cache-Control\",\"value\":\"no-cache, no-store\"},{\"name\":\"X-Requested-With\",\"value\":\"XMLHttpRequest\"},{\"name\":\"access_token\",\"value\":\"f05856f2c95746e77cd220b231bffe12\"},{\"name\":\"User-Agent\",\"value\":\"Mozilla\\/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit\\/537.36 (KHTML, like Gecko) Chrome\\/120.0.0.0 Safari\\/537.36\"},{\"name\":\"Origin\",\"value\":\"http:\\/\\/59.202.68.95:8215\"},{\"name\":\"Referer\",\"value\":\"http:\\/\\/59.202.68.95:8215\\/dataDict?activeId=FE70463C68E146CAAC591A15250D4721\"},{\"name\":\"Accept-Encoding\",\"value\":\"gzip, deflate\"},{\"name\":\"Accept-Language\",\"value\":\"zh-CN,zh;q=0.9\"},{\"name\":\"Cookie\",\"value\":\"JSESSIONID=46C46EF23678E74686464D2D3C3AC48C; wyhtml=\\/dataasset\\/_1918c9ecaa25735_1724641102498\"}]",
        "response_headers": "[{\"name\":\"Server\",\"value\":\"nginx\\/1.24.0\"},{\"name\":\"Date\",\"value\":\"Thu, 29 Aug 2024 03:30:47 GMT\"},{\"name\":\"Content-Type\",\"value\":\"text\\/json;charset=UTF-8\"},{\"name\":\"Content-Length\",\"value\":\"1959\"},{\"name\":\"Connection\",\"value\":\"keep-alive\"},{\"name\":\"Cache-Control\",\"value\":\"no-cache\"},{\"name\":\"Expires\",\"value\":\"0\"},{\"name\":\"Pragma\",\"value\":\"No-cache\"},{\"name\":\"Content-Language\",\"value\":\"zh-CN\"},{\"name\":\"Access-Control-Allow-Origin\",\"value\":\"*\"},{\"name\":\"Access-Control-Allow-Headers\",\"value\":\"X-Requested-With\"},{\"name\":\"Access-Control-Allow-Methods\",\"value\":\"GET,POST,OPTIONS\"}]",
        "request_body": "",
        "response_body": "{\"success\":true,\"fieldErrors\":{},\"actionErrors\":[],\"messages\":[],\"totalCount\":2,\"data\":[{\"binType\":0,\"cmmNodeType\":\"1\",\"code\":\"database\",\"crdctCode\":\"database\",\"crdctCractUuid\":\"CRACT_UUID_1\",\"crdctCreateTime\":\"2022-11-10 17:26:57\",\"crdctLevelCode\":\"000H010000\",\"crdctName\":\"数据库\",\"crdctOrder\":1,\"crdctParentUuid\":\"393D43AE73EB483DAC22040B128C936C\",\"crdctPathCode\":\"/DICT/BIGDATA/RDMP/dataformat/database\",\"crdctRemarks\":\"\",\"crdctStatus\":\"1\",\"crdctType\":\"1\",\"crdctUnid\":2064302,\"crdctUpdateTime\":\"2022-11-10 17:26:57\",\"crdctUuid\":\"3B04511313724BB289E4F6B663B8FA58\",\"crdctValue\":\"\",\"depth\":5,\"ext\":{},\"fullType\":\"11\",\"iconSkin\":\"xtree-depth-5 xtree-type-1 \",\"intMap\":{},\"lastUpdateTime\":\"2022-11-10 17:26:57\",\"leaf\":false,\"levelCode\":\"000H010000\",\"majorType\":\"1\",\"minorType\":\"1\",\"order\":1,\"parent\":true,\"parentUuid\":\"393D43AE73EB483DAC22040B128C936C\",\"pathCode\":\"/DICT/BIGDATA/RDMP/dataformat/database\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"数据库\",\"unid\":2064302,\"uuid\":\"3B04511313724BB289E4F6B663B8FA58\"},{\"binType\":0,\"cmmNodeType\":\"1\",\"code\":\"picture\",\"crdctCode\":\"picture\",\"crdctCractUuid\":\"CRACT_UUID_1\",\"crdctCreateTime\":\"2022-11-10 17:27:07\",\"crdctLevelCode\":\"000H010001\",\"crdctName\":\"图形图像\",\"crdctOrder\":3,\"crdctParentUuid\":\"393D43AE73EB483DAC22040B128C936C\",\"crdctPathCode\":\"/DICT/BIGDATA/RDMP/dataformat/picture\",\"crdctRemarks\":\"\",\"crdctStatus\":\"1\",\"crdctType\":\"1\",\"crdctUnid\":2064303,\"crdctUpdateTime\":\"2022-11-10 17:27:07\",\"crdctUuid\":\"053E7EE50F6144728AF0BC5B6B7B4341\",\"crdctValue\":\"\",\"depth\":5,\"ext\":{},\"fullType\":\"11\",\"iconSkin\":\"xtree-depth-5 xtree-type-1 \",\"intMap\":{},\"lastUpdateTime\":\"2022-11-10 17:27:07\",\"leaf\":false,\"levelCode\":\"000H010001\",\"majorType\":\"1\",\"minorType\":\"1\",\"order\":3,\"parent\":true,\"parentUuid\":\"393D43AE73EB483DAC22040B128C936C\",\"pathCode\":\"/DICT/BIGDATA/RDMP/dataformat/picture\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"图形图像\",\"unid\":2064303,\"uuid\":\"053E7EE50F6144728AF0BC5B6B7B4341\"}]}",
        "request_body_json": "{}",
        "parameter_json": "{}"
    }
    zuzhi_o = {
        "time": "2024-08-29T10:37:37",
        "app": "59.202.68.95:8215",
        "app_name": "高质量数据中心",
        "flow_id": "78906584529497",
        "urld": "http://59.202.68.95:8215/dataasset/api/dataasset/other/queryOrgTree",
        "url": "http://59.202.68.95:8215/dataasset/api/dataasset/other/queryOrgTree",
        "name": "数据目录-目录管理-组织结构",
        "account": "徐君",
        "auth_type": 5,
        "dstport": 8215,
        "srcip": "10.18.80.10",
        "parameter": "uuid=ORG_21C028E1CF26409E80A270821D44AC4C",
        "real_ip": "",
        "http_method": "POST",
        "status": 200,
        "api_type": "5",
        "qlength": 0,
        "yw_count": 0,
        "length": "14604",
        "user_info": "{\"账户名\": \"徐君\", \"职位名称\": \"瑞成科技\", \"工作电话\": \"0571-0000000\"}",
        "srcport": 53759,
        "dstip": "59.202.68.95",
        "risk_level": "1",
        "content_length": 14604,
        "id": "1724899257612872868",
        "age": 27062,
        "content_type": "JSON",
        "key": "\"\"",
        "info": "{}",
        "request_headers": "[{\"name\":\"Host\",\"value\":\"59.202.68.95:8215\"},{\"name\":\"Connection\",\"value\":\"keep-alive\"},{\"name\":\"Content-Length\",\"value\":\"0\"},{\"name\":\"Accept\",\"value\":\"application\\/json, text\\/plain, *\\/*\"},{\"name\":\"Pragma\",\"value\":\"no-cache\"},{\"name\":\"Cache-Control\",\"value\":\"no-cache, no-store\"},{\"name\":\"X-Requested-With\",\"value\":\"XMLHttpRequest\"},{\"name\":\"access_token\",\"value\":\"f05856f2c95746e77cd220b231bffe12\"},{\"name\":\"User-Agent\",\"value\":\"Mozilla\\/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit\\/537.36 (KHTML, like Gecko) Chrome\\/120.0.0.0 Safari\\/537.36\"},{\"name\":\"Origin\",\"value\":\"http:\\/\\/59.202.68.95:8215\"},{\"name\":\"Referer\",\"value\":\"http:\\/\\/59.202.68.95:8215\\/dataSheet?activeId=302C64A00D6B458799DEEE96BDB442B1\"},{\"name\":\"Accept-Encoding\",\"value\":\"gzip, deflate\"},{\"name\":\"Accept-Language\",\"value\":\"zh-CN,zh;q=0.9\"},{\"name\":\"Cookie\",\"value\":\"JSESSIONID=46C46EF23678E74686464D2D3C3AC48C; wyhtml=\\/dataasset\\/_1918c9ecaa25735_1724641102498\"}]",
        "response_headers": "[{\"name\":\"Server\",\"value\":\"nginx\\/1.24.0\"},{\"name\":\"Date\",\"value\":\"Thu, 29 Aug 2024 02:37:37 GMT\"},{\"name\":\"Content-Type\",\"value\":\"text\\/json;charset=UTF-8\"},{\"name\":\"Content-Length\",\"value\":\"14604\"},{\"name\":\"Connection\",\"value\":\"keep-alive\"},{\"name\":\"Cache-Control\",\"value\":\"no-cache\"},{\"name\":\"Expires\",\"value\":\"0\"},{\"name\":\"Pragma\",\"value\":\"No-cache\"},{\"name\":\"Content-Language\",\"value\":\"zh-CN\"},{\"name\":\"Access-Control-Allow-Origin\",\"value\":\"*\"},{\"name\":\"Access-Control-Allow-Headers\",\"value\":\"X-Requested-With\"},{\"name\":\"Access-Control-Allow-Methods\",\"value\":\"GET,POST,OPTIONS\"}]",
        "request_body": "",
        "response_body": "{\"success\":true,\"fieldErrors\":{},\"actionErrors\":[],\"messages\":[\"操作成功\"],\"totalCount\":17,\"data\":[{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委领导\",\"crorgLevelCode\":\"060000\",\"crorgName\":\"拱墅区委领导\",\"crorgOrder\":597,\"crorgOuterUuid\":\"GO_17da9e84bad74f5abc4b7a0e327dfd73\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576455,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_F1B0DA8C766E48FB989B00AAA216DBC9\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":true,\"levelCode\":\"060000\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":597,\"parent\":false,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委领导\",\"type\":\"2\",\"unid\":5576455,\"uuid\":\"ORG_F1B0DA8C766E48FB989B00AAA216DBC9\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委办公室\",\"crorgLevelCode\":\"060001\",\"crorgName\":\"拱墅区委办公室\",\"crorgOrder\":991,\"crorgOuterUuid\":\"GO_caba3451996746278cb486da6d35153a\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576456,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_6F8BDFED24AE4DD6AFE00FC67D0E0BDF\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060001\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":991,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委办公室\",\"type\":\"2\",\"unid\":5576456,\"uuid\":\"ORG_6F8BDFED24AE4DD6AFE00FC67D0E0BDF\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区纪委区监委\",\"crorgLevelCode\":\"060002\",\"crorgName\":\"拱墅区纪委区监委\",\"crorgOrder\":1360,\"crorgOuterUuid\":\"GO_c4f4a71a902f4c9aa9f268be9197c219\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576457,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_359556E3BD8149C6AFD40E6650C668C7\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060002\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":1360,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区纪委区监委\",\"type\":\"2\",\"unid\":5576457,\"uuid\":\"ORG_359556E3BD8149C6AFD40E6650C668C7\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委组织部\",\"crorgLevelCode\":\"060003\",\"crorgName\":\"拱墅区委组织部\",\"crorgOrder\":1710,\"crorgOuterUuid\":\"GO_2d0a4ad40a3b40d9be5938865101d694\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576458,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_6757E6884D044C029A790095ED8D4AE4\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060003\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":1710,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委组织部\",\"type\":\"2\",\"unid\":5576458,\"uuid\":\"ORG_6757E6884D044C029A790095ED8D4AE4\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委宣传部\",\"crorgLevelCode\":\"060004\",\"crorgName\":\"拱墅区委宣传部\",\"crorgOrder\":2029,\"crorgOuterUuid\":\"GO_fe954d4f65db477498e50f6915140d32\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576459,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_E3F4DD397B2840088A71F1ED0DAEDE42\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060004\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":2029,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委宣传部\",\"type\":\"2\",\"unid\":5576459,\"uuid\":\"ORG_E3F4DD397B2840088A71F1ED0DAEDE42\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委统战部\",\"crorgLevelCode\":\"060005\",\"crorgName\":\"拱墅区委统战部\",\"crorgOrder\":2314,\"crorgOuterUuid\":\"GO_d2e5fd0d432d4182972d9bdc37421867\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576460,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_906A2B2D6F504A33BFB9CB67F8A078EE\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060005\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":2314,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委统战部\",\"type\":\"2\",\"unid\":5576460,\"uuid\":\"ORG_906A2B2D6F504A33BFB9CB67F8A078EE\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委政法委\",\"crorgLevelCode\":\"060006\",\"crorgName\":\"拱墅区委政法委\",\"crorgOrder\":2553,\"crorgOuterUuid\":\"GO_c5b087c3d895486d80e0982347c83fde\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576461,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_567B44AC197B4558A33FE470CA97A0A1\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060006\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":2553,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委政法委\",\"type\":\"2\",\"unid\":5576461,\"uuid\":\"ORG_567B44AC197B4558A33FE470CA97A0A1\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委改革办\",\"crorgLevelCode\":\"060007\",\"crorgName\":\"拱墅区委改革办\",\"crorgOrder\":2759,\"crorgOuterUuid\":\"GO_fc60d6e048204209ab092e401edcffaa\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576462,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_2FF96EDD1094407F965D518DB05528B5\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060007\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":2759,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委改革办\",\"type\":\"2\",\"unid\":5576462,\"uuid\":\"ORG_2FF96EDD1094407F965D518DB05528B5\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委政研室\",\"crorgLevelCode\":\"060008\",\"crorgName\":\"拱墅区委政研室\",\"crorgOrder\":2928,\"crorgOuterUuid\":\"GO_0d38034d9a3a4aaeb923f05b244cc6f5\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576463,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_42CCD11143684939AEA326121BE26850\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":true,\"levelCode\":\"060008\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":2928,\"parent\":false,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委政研室\",\"type\":\"2\",\"unid\":5576463,\"uuid\":\"ORG_42CCD11143684939AEA326121BE26850\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委编办\",\"crorgLevelCode\":\"060009\",\"crorgName\":\"拱墅区委编办\",\"crorgOrder\":3064,\"crorgOuterUuid\":\"GO_0f28be9f989443068bb06158e02e291e\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576464,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_F5CEC5DEC4374823BC35E03C58FB5E2B\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"060009\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3064,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委编办\",\"type\":\"2\",\"unid\":5576464,\"uuid\":\"ORG_F5CEC5DEC4374823BC35E03C58FB5E2B\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委直属机关工委\",\"crorgLevelCode\":\"06000A\",\"crorgName\":\"拱墅区委直属机关工委\",\"crorgOrder\":3177,\"crorgOuterUuid\":\"GO_36d848d6dcda4af399a358555b398664\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576465,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_E8A7DEBE3DDF4410B34DED9F3CAB6B0E\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000A\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3177,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委直属机关工委\",\"type\":\"2\",\"unid\":5576465,\"uuid\":\"ORG_E8A7DEBE3DDF4410B34DED9F3CAB6B0E\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委巡察机构\",\"crorgLevelCode\":\"06000B\",\"crorgName\":\"拱墅区委巡察机构\",\"crorgOrder\":3270,\"crorgOuterUuid\":\"GO_e67d034429aa43378e5e63c6683eea11\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576466,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_878E9A6C79544938A6D649579E55F38B\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000B\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3270,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委巡察机构\",\"type\":\"2\",\"unid\":5576466,\"uuid\":\"ORG_878E9A6C79544938A6D649579E55F38B\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区信访局\",\"crorgLevelCode\":\"06000C\",\"crorgName\":\"拱墅区信访局\",\"crorgOrder\":3348,\"crorgOuterUuid\":\"GO_cb8637b3616640ac91464931bd3bbb91\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576467,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_E03D96311D7548468DA29F1C7441E040\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000C\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3348,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区信访局\",\"type\":\"2\",\"unid\":5576467,\"uuid\":\"ORG_E03D96311D7548468DA29F1C7441E040\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委老干部局\",\"crorgLevelCode\":\"06000D\",\"crorgName\":\"拱墅区委老干部局\",\"crorgOrder\":3421,\"crorgOuterUuid\":\"GO_55e6368393a14eae90b03b8da363982e\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576468,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_8C72187200B94178B0409D6B4FD70699\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000D\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3421,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委老干部局\",\"type\":\"2\",\"unid\":5576468,\"uuid\":\"ORG_8C72187200B94178B0409D6B4FD70699\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区委党史研究室\",\"crorgLevelCode\":\"06000E\",\"crorgName\":\"拱墅区委党史研究室\",\"crorgOrder\":3484,\"crorgOuterUuid\":\"GO_afae709447654bfb97bffcfd66fc8f69\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576469,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_279EF9C45AD34C21B8F797A70A30C870\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000E\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3484,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区委党史研究室\",\"type\":\"2\",\"unid\":5576469,\"uuid\":\"ORG_279EF9C45AD34C21B8F797A70A30C870\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区关工委\",\"crorgLevelCode\":\"06000F\",\"crorgName\":\"拱墅区关工委\",\"crorgOrder\":3541,\"crorgOuterUuid\":\"GO_b758a3f121ed4c48b09297e4477b471a\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576470,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_4606D946D5314C10BB053D9B2FBEC8C6\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000F\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3541,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区关工委\",\"type\":\"2\",\"unid\":5576470,\"uuid\":\"ORG_4606D946D5314C10BB053D9B2FBEC8C6\"},{\"cmmNodeType\":\"2\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区社会治理中心\",\"crorgLevelCode\":\"06000G\",\"crorgName\":\"拱墅区社会治理中心\",\"crorgOrder\":3588,\"crorgOuterUuid\":\"GO_3c9b0329f140443fbd042f75d7603cde\",\"crorgParentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"crorgStatus\":\"1\",\"crorgType\":\"2\",\"crorgUnid\":5576471,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_0DEDE216398C41E49206EB1B2A630F2E\",\"depth\":3,\"ext\":{},\"fullType\":\"22\",\"iconSkin\":\"xtree-depth-3 xtree-type-2 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":false,\"levelCode\":\"06000G\",\"majorType\":\"2\",\"minorType\":\"2\",\"order\":3588,\"parent\":true,\"parentUuid\":\"ORG_21C028E1CF26409E80A270821D44AC4C\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区社会治理中心\",\"type\":\"2\",\"unid\":5576471,\"uuid\":\"ORG_0DEDE216398C41E49206EB1B2A630F2E\"}]}",
        "request_body_json": "{}",
        "parameter_json": "{}"
    }
    dic_o = {
        "time": "2024-08-29T10:39:22",
        "app": "59.202.68.95:8215",
        "app_name": "高质量数据中心",
        "flow_id": "1801768297740086",
        "urld": "http://59.202.68.95:8215/dataasset/api/dataasset/assetTable/queryTableInfo",
        "url": "http://59.202.68.95:8215/dataasset/api/dataasset/other/queryOrgTree",
        "name": "数据服务-数据服务-选择源表",
        "account": "徐君",
        "auth_type": 5,
        "dstport": 8215,
        "srcip": "10.18.80.10",
        "parameter": "uuid==ORG_21C028E1CF26409E80A270821D44AC4C",
        "real_ip": "",
        "http_method": "GET",
        "status": 200,
        "api_type": "5",
        "qlength": 0,
        "yw_count": 0,
        "length": "90",
        "user_info": "{\"账户名\": \"徐君\", \"职位名称\": \"瑞成科技\", \"工作电话\": \"0571-0000000\"}",
        "srcport": 53904,
        "dstip": "59.202.68.95",
        "risk_level": "1",
        "content_length": 90,
        "id": "1724899363280306270",
        "age": 81915,
        "content_type": "JSON",
        "key": "\"\"",
        "info": "{}",
        "request_headers": "[{\"name\":\"Host\",\"value\":\"59.202.68.95:8215\"},{\"name\":\"Connection\",\"value\":\"keep-alive\"},{\"name\":\"Accept\",\"value\":\"application\\/json, text\\/plain, *\\/*\"},{\"name\":\"Pragma\",\"value\":\"no-cache\"},{\"name\":\"Cache-Control\",\"value\":\"no-cache, no-store\"},{\"name\":\"X-Requested-With\",\"value\":\"XMLHttpRequest\"},{\"name\":\"access_token\",\"value\":\"f05856f2c95746e77cd220b231bffe12\"},{\"name\":\"User-Agent\",\"value\":\"Mozilla\\/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit\\/537.36 (KHTML, like Gecko) Chrome\\/120.0.0.0 Safari\\/537.36\"},{\"name\":\"Content-Type\",\"value\":\"application\\/json;charset=utf-8\"},{\"name\":\"Referer\",\"value\":\"http:\\/\\/59.202.68.95:8215\\/dataSheet?activeId=302C64A00D6B458799DEEE96BDB442B1\"},{\"name\":\"Accept-Encoding\",\"value\":\"gzip, deflate\"},{\"name\":\"Accept-Language\",\"value\":\"zh-CN,zh;q=0.9\"},{\"name\":\"Cookie\",\"value\":\"JSESSIONID=46C46EF23678E74686464D2D3C3AC48C; wyhtml=\\/dataasset\\/_1918c9ecaa25735_1724641102498\"}]",
        "response_headers": "[{\"name\":\"Server\",\"value\":\"nginx\\/1.24.0\"},{\"name\":\"Date\",\"value\":\"Thu, 29 Aug 2024 02:39:22 GMT\"},{\"name\":\"Content-Type\",\"value\":\"text\\/json;charset=UTF-8\"},{\"name\":\"Content-Length\",\"value\":\"90\"},{\"name\":\"Connection\",\"value\":\"keep-alive\"},{\"name\":\"Cache-Control\",\"value\":\"no-cache\"},{\"name\":\"Expires\",\"value\":\"0\"},{\"name\":\"Pragma\",\"value\":\"No-cache\"},{\"name\":\"Content-Language\",\"value\":\"zh-CN\"},{\"name\":\"Access-Control-Allow-Origin\",\"value\":\"*\"},{\"name\":\"Access-Control-Allow-Headers\",\"value\":\"X-Requested-With\"},{\"name\":\"Access-Control-Allow-Methods\",\"value\":\"GET,POST,OPTIONS\"}]",
        "request_body": "",
        "response_body": "{\"success\":true,\"fieldErrors\":{},\"actionErrors\":[],\"messages\":[],\"totalCount\":0,\"data\":[]}",
        "request_body_json": "{}",
        "parameter_json": "{\"page\":\"1\",\"size\":\"10\",\"orgUuid\":\"ORG_6F8BDFED24AE4DD6AFE00FC67D0E0BDF\"}"
    }
    with open("./tree_dic.pkl", "rb") as fp:

        dict_tree = pickle.load(fp)

    ss = read_model_identify(an, dic_o, dict_tree)

    print(ss)
