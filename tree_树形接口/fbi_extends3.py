#!/usr/bin/python
# -*- coding: utf-8 -*-
import shutil
import sys
import configparser
import uvicorn
window_file_path_config = {
    "store_base_dir": "./models_paths/",
    "extract_base_dir": "./models_paths/model_extract/",
    "download_base_dir": "./model_xlinks/",
}
file_path_config = {
    "store_base_dir": "/data/xlink/models_paths/",
    "extract_base_dir": "/data/xlink/models_paths/model_extract/",
    "download_base_dir": "/data/workspace/model_xlinks/",
}

sys.path.append("lib")

#from bottle import request, Bottle, abort, route, response, run
from fastapi import Request,FastAPI,Response
from fastapi import  Query, Body, File, UploadFile, Form
from fastapi import APIRouter
import json
import time
import zipfile
import ujson

sys.path.append("/opt/openfbi/pylibs")
from intell_analy_new import *

route = APIRouter()

@route.post("/cls_d")
async def get_clssify(data:dict,request:Request,response:Response):
    """
    获取前端传入的三条日志信息，返回分类上下文规则给前端
    :return:
    """
    # 接口后的参数信息 , body raw直接传入 数据 {“datas”:[{},{},{}]}
    try:
        datas = data
        o_data = datas.get("datas", {})

        result = clas_data(o_data)

        return {"code":200,"status": "Success", "cls_res": result}
    except Exception as e:
        return {"code":500,"status": "Error", "msg": str(e)}


def clas_data(datass):
    res = {}
    con_res = {}
    for o_data in datass:
        for key, value in o_data.items():
            # 忽略空值
            if not value:
                continue

            # 直接将键后面全部跟上列表
            res.setdefault(key, []).append(value)
    for key, value in res.items():
        # 判断键对应的值的类型
        if len(value) == 1:
            con_res = condition_judge(value, key, con_res)
        elif len(value) > 1:
            con_res = condition_judge(value, key, con_res, is_list=True)
    return con_res


def condition_judge(value, key, res, is_list=False):
    if len(value) == 1:
        if is_list:
            res.setdefault(key, {}).setdefault("judge", "in")
            res.setdefault(key, {}).setdefault("msg", value)
        else:
            res.setdefault(key, {}).setdefault("judge", "=")
            res.setdefault(key, {}).setdefault("msg", value[0])
    elif len(value) > 1:
        res.setdefault(key, {}).setdefault("judge", "in")
        res.setdefault(key, {}).setdefault("msg", value)
    return res


@route.post("/con_q")  # 上下文规则传递
async def query_save(item:dict,request:Request,response:Response):
    """
    :return: 获取经过人工处理过的分类信息
    """
    try:
        query_json = item
        query_name = query_json.get("query_name", "")  # 获取上下文规则名称
        condition = query_json.get("con", "")  #
        json_key = ujson.dumps(condition)
        return {"code":200,"status": "Success", "con": {query_name: json_key}}
    except Exception as e:
        return {"code":500,"status": "Error", "msg": str(e)}


@route.post("/als_d")
async def intell_analysis(item:dict,request:Request,response:Response):
    """
    智能分析接口,进行提取分析数据
    :return:
    """
    try:
        output_res = {}
        q_d = item  # 获取到前端发来的消息 其中包括上下文规则信息，标识的数据信息
        datas = q_d["datas"]  # 获取标识信息
        con = q_d["con"]  # 获取上下文规则信息
        map_dic = q_d.get("map_dic", {})  # 获取字典映射规则信息
        map_field = {}

        # 获取相应规则，目前按照1条规则进行测试
        try:
            intell_rule,temp_json_rules = handle_project(con, datas)  # 如果传入一条 则是返回一条，但是该条不能直接写入规则文件中，因为还需要判断识别是否为空
            print(intell_rule)
            # print(con)
        except Exception as e:
            return {"code":500,"status": "Error", "msg": f"规则提取失败:{e.__str__()}"}
        # 根据获取出的规则进行识别我们这三条信息，将数据传递给前端界面
        try:
            idx_message = an_data(datas, temp_json_rules, con)
        except Exception as e:
            # idx_message={}
            return {"code":500,"status": "Error", "msg": f"数据识别失败:{e.__str__()}"}
        # 根据获取出的字典映射识别信息
        try:
            if map_dic:
                map_field = map_tree(map_dic, datas)

        except Exception as e:
            return {"code":500,"status": "Error", "msg": f"字典映射识别失败:{e.__str__()}"}
        if idx_message:
            # 根据规则名称 获取规则名

            output_res.setdefault("outcome", idx_message)
        else:
            output_res.setdefault("outcome", {})

        for model_key, da in con.items():
            output_res.setdefault("model_key", model_key)
            output_res.setdefault("con", da)
            if intell_rule:
                output_res.setdefault("rules", intell_rule[model_key])
            else:
                output_res.setdefault("rules", {})
            if map_field:
                output_res.setdefault("map_dic", map_field)
        return {"code":200,"status": "Success", "res": output_res}
    except Exception as e:
        return {"code":500,"status": "Error", "res": str(e)}

@route.post("/s_rules_con")
async def rules_save(item:dict,request:Request,response:Response):
    # 保存规则信息
    # 获取前端的规则数据，写入文件中
    try:
        crlf_add_alter = item # 获取add_alter 修改的和新增内容
        add_data = crlf_add_alter.get("add", {})
        alter_data = crlf_add_alter.get("alter", {})
        file_str = crlf_add_alter.get("file_str", "")
    except Exception as e:
        return {"code":500,"status": "Error", "msg": f"获取前台数据失败:{e.__str__()}"}
    # 读取文件信息
    # 拼接文件路径
    # base_dir = "/data/xlink/models_paths/"
    # base_dir = "./"
    base_dir = file_path_config['store_base_dir']
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    source_file = os.path.join(base_dir, f"{file_str}_rcl_bak.pkl")
    destination_file = os.path.join(base_dir, f"{file_str}_rcl.pkl")
    tol_rulers = load_data(destination_file)
    add_msg = ""
    alter_msg = ""
    # 根据文件数据 进行增加修改规则
    if add_data:
        rules = add_data.get("rules", {})
        con = add_data.get("con", {})
        linfo = add_data.get("linfo", {})
        model_key = add_data.get("model_key", "")
        map_dic = alter_data.get("map_dic", {})
        MapField = alter_data.get("MapField", {})
        dict_assoc = alter_data.get("dict_assoc", "")
        con = con.get(model_key, {})
        # 先将两者写入 到副本文件中，如果存在报错信息，则删除副本文件，返回错误信息
        try:
            tol_rulers = add_all_data(rules, con, model_key, linfo, map_dic, MapField, dict_assoc, tol_rulers)
            add_msg = f"新增模型成功！"
        except Exception as e:
            return {"code":500,"status": "Error", "msg": f"子模型新增错误:{e.__str__()}"}
    if alter_data:
        rules = alter_data.get("rules", {})
        con = alter_data.get("con", {})
        linfo = alter_data.get("linfo", {})
        model_key = alter_data.get("model_key", "")
        old_key = alter_data.get("orl_key", "")
        map_dic = alter_data.get("map_dic", {})
        MapField = alter_data.get("MapField", {})
        dict_assoc = alter_data.get("dict_assoc", "")
        con = con.get(model_key, {})
        try:
            tol_rulers = alter_all_data(rules, con, model_key, linfo, old_key, map_dic, MapField, dict_assoc,
                                        tol_rulers)
            alter_msg = f"修改模型成功！"
        except Exception as e:
            return {"code":500,"status": "Error", "msg": f"子模型修改错误:{e.__str__()}"}
    res = write_replace(source_file, destination_file, tol_rulers)

    res.update({"add_msg": add_msg, "alter_msg": alter_msg,"code":200})

    return res


@route.post("/delete_rulers")
async def delete_rules(item:dict,request:Request,response:Response):
    # 删除子模型数据信息
    crlf = item
    model_key = crlf.get("model_key", {})
    file_str = crlf.get("file_str", "")
    res = delete_rules_data(model_key, file_str)
    return res



#             ##################add rzc 2024/4/28#####################
@route.post("/model_upload")
async def upload_models(item:dict,request:Request,response:Response,file_str:str = Query(None),
                        upload_file:UploadFile = File(...)):
    """
    上传模型接口，要将模型文件，上传至当前环境下
    :return:
    """
    try:
        extract_base_dir = file_path_config['extract_base_dir']  # 解压路径
        base_dir = file_path_config['store_base_dir']  # 基础路径
        #  判断解压路径存不存在
        if not os.path.isdir(extract_base_dir):
            os.makedirs(extract_base_dir)
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        #  获取当前查询分析得模型名称
        #file_str = request.params.get("file_str", "")  # 传入的是 当前模型的文件名
        # 对参数进行解码
        decoded_file_str = file_str
        # 获取上传的文件
        # upload_file = request.files.get("file")
        if not upload_file:
            return ujson.dumps({"code":500,"status": "Error", "msg": "未提供文件或文件名"}, ensure_ascii=False)

        # 获取文件压缩包原名称
        filename = upload_file.filename

        # 拼接路径名称
        zip_filepath = os.path.join(extract_base_dir, filename)
        with open(zip_filepath,"wb")as f:
            content = await upload_file.read()
            f.write(content)
        #upload_file.save(zip_filepath, overwrite=True)  # 保存 默认覆盖文件信息

        # 解压缩文件
        try:
            with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
                zip_ref.extractall(extract_base_dir)
        except Exception as e:
            return ujson.dumps({"code":500,"status": "Error", "msg": f"解压模型文件出错：{e.__str__()}"}, ensure_ascii=False)

        # 判断文件信息 然后进行读取返回给前端信息
        # 每次只能给一个智能模型 文件下面是三个文件
        extracted_files = os.listdir(extract_base_dir)
        cur_data = []
        res = {}
        #  默认等于三的时候才是正确的
        if len(extracted_files) == 3:
            for file in extracted_files:
                if file.endswith('.zip'):
                    continue
                elif file.endswith(".pkl"):
                    if "ui_data" in file:
                        # 需要返回的数据
                        # 读取该文件就行
                        with open(os.path.join(extract_base_dir, file), 'rb') as fp:
                            cur_data = pickle.load(fp)

                    else:
                        # 模型信息,如果 文件存在 就进行读取，如果不存在就写入
                        res = up_file_model(os.path.join(extract_base_dir, file), decoded_file_str, base_dir)
                        if res.get("status") == "Error":
                            shutil.rmtree(extract_base_dir)
                            return ujson.dumps(res, ensure_ascii=False)
                else:
                    shutil.rmtree(extract_base_dir)
                    return ujson.dumps({"code":500,"status": "Error", "msg": f"路径文件异常，请重新上传模型文件！"},
                                       ensure_ascii=False)
            # 也需要清空
            shutil.rmtree(extract_base_dir)
            return ujson.dumps({"code":200,"status": "Success", "data": cur_data, "model_info": res}, ensure_ascii=False)
        else:
            # 清空路径下面文件 重新上传模型
            shutil.rmtree(extract_base_dir)
            return ujson.dumps({"code":500,"status": "Error", "msg": f"路径文件异常，请重新上传模型文件！"}, ensure_ascii=False)
    except Exception as e:
        return f"错误：f{e.__str__()}"


@route.post("/model_download")
async def models_download(item:dict,request:Request,response:Response):
    """
    下载模型文件路由
    :param filename: 文件名
    :return:
    """
    try:
        # 设置文件存储路径
        file_str = item.get('filename', "")
        current_data = item.get('current_data', [])
        if not file_str:
            return "未提供文件名"

        base_dir = file_path_config['store_base_dir']

        download_base_dir = file_path_config['download_base_dir']

        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        filename = file_str + "_rcl.pkl"

        ui_file = f"{file_str}_ui_data.pkl"
        # 将数据写入.pkl文件
        new_file_path = os.path.join(base_dir, ui_file)
        try:
            with open(new_file_path, 'wb') as f:
                pickle.dump(current_data, f)
        except Exception as e:
            return {"code":500,"status": "Error", "msg": f"子模型列表导出失败：{e.__str__()}"}
        # 创建压缩文件信息
        zip_filename = f"{file_str}_rcl.zip"
        zip_file_path = os.path.join(base_dir, zip_filename)

        with zipfile.ZipFile(zip_file_path, "w") as zipf:
            zipf.write(new_file_path, ui_file)
            zipf.write(base_dir + filename, filename)
        #  将zip_file_path 移动到workspace下面
        if not os.path.exists(download_base_dir):
            os.makedirs(download_base_dir)
        workspace_path = os.path.join(download_base_dir, zip_filename)
        try:
            shutil.move(zip_file_path, workspace_path)
            # 删除 子模型列表信息
            os.remove(new_file_path)
        except Exception as e:
            return {"code":500,"status": "Error", "msg": f"移动文件出错：{e.__str__()}"}
        #response.content_type = 'application/zip'

        return {"code":200,"status": "Success", "download_link": workspace_path}

    except Exception as e:
        return {"code":500,"status": "Error", "msg": f"错误：{e.__str__()}"}


if __name__ == '__main__':
    uvicorn.run("fbi_extends3:route", host="0.0.0.0", port=9996)
