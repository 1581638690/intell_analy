import ujson
from intell_analy_new_front_end import *


def table_common(url, response_body, table_dic):
    if url == "/hsdsh/original/getOriginalTable":
        response_body = ujson.loads(response_body)
        data = response_body.get("data", [])
        if data:
            for item in data:
                system = item.get("system", "")
                tableName = item.get("tableName", "")
                tableComment = item.get("tableComment", "")
                id = str(item.get("id"))
                topics = item.get("topic", "")
                table_dic.setdefault(id, {}).setdefault("topic", topics)
                table_dic.setdefault(id, {}).setdefault("tableName", tableName)
                table_dic.setdefault(id, {}).setdefault("tableComment", tableComment)
                table_dic.setdefault(id, {}).setdefault("system", system)
    return table_dic


def tree_common(url, response_body, tree_dic):
    if url == "/dataasset/api/dataasset/other/queryOrgTree":
        response_body = ujson.loads(response_body)
        data = response_body.get("data", [])
        if data:
            for item in data:
                crorgUuid = item.get("crorgUuid", "")
                crorgFullName = item.get("crorgFullName", "")
                crorgParentUuid = item.get("crorgParentUuid", "")
                tree_dic.setdefault(crorgUuid, {}).setdefault("fullname", crorgFullName)
                tree_dic.setdefault(crorgUuid, {}).setdefault("parentuuid", crorgParentUuid)
    return tree_dic


def dict_common(url, response_body, dict_tree):
    if url in ["/dataasset/api/dataasset/dataDictionary/listAll", "/dataasset/api/dataasset/dataDictionary/likeTree"]:
        response_body = ujson.loads(response_body)
        data = response_body.get("data", [])
    if data:
        for item in data:
            crorgUuid = item.get("crdctUuid", "")
            crorgFullName = item.get("crdctName", "")
            crorgParentUuid = item.get("crdctParentUuid", "")
            dict_tree.setdefault(crorgUuid, {}).setdefault("fullname", crorgFullName)
            dict_tree.setdefault(crorgUuid, {}).setdefault("parentuuid", crorgParentUuid)
    return dict_tree


def tree_path(tree_dic, org_uuid):
    path = []
    current_uuid = org_uuid
    url_name = tree_dic.get(org_uuid, {}).get("fullname", "")
    while current_uuid:
        org_info = tree_dic.get(current_uuid)
        if not org_info:
            break
        path.append(org_info["fullname"])
        current_uuid = org_info["parentuuid"]
    return " -> ".join(reversed(path)), url_name


def common_handler(url, response_body, common_dic):
    # 定义不同的URL字段映射
    url_mapping = {
        "/dataasset/api/dataasset/dataDictionary/listAll": {
            "id_field": "crdctUuid",
            "fields": {
                "fullname": "crdctName",
                "parentuuid": "crdctParentUuid",
            }
        },
        "/dataasset/api/dataasset/dataDictionary/likeTree": {
            "id_field": "crdctUuid",
            "fields": {
                "fullname": "crdctName",
                "parentuuid": "crdctParentUuid",
            }
        },
        "/dataasset/api/dataasset/other/queryOrgTree": {
            "id_field": "crorgUuid",
            "fields": {
                "fullname": "crorgFullName",
                "parentuuid": "crorgParentUuid"
            }
        }
    }

    # 检查是否有该URL字段映射
    if url in url_mapping:
        # 获取该url的字段配置
        field_config = url_mapping[url]
        id_field = field_config["id_field"]
        fields = field_config["fields"]

        # 解析响应数据
        response_body = ujson.loads(response_body)
        data = response_body.get("data", [])
        if data:
            for item in data:
                # 获取 id 字段
                id_value = str(item.get(id_field, ""))

                # 遍历该 URL 的字段映射
                for key, field_name in fields.items():
                    field_value = item.get(field_name, "")
                    common_dic.setdefault(id_value, {}).setdefault(key, field_value)
    return common_dic


def map_tree(map_dic,datas):
    map_filed = {}
    # 获取当前日志信息
    data_id = map_dic.get("data_id")
    # 循环获取日志序号的日志信息
    current_data = next((d.get("data") for d in datas if d.get("idx") == data_id), None)
    # 获取标注日志的请求位置
    imp_pos = map_dic.get("imp_pos")

    http_data = current_data.get(imp_pos)
    http_data = ujson.loads(http_data)

    imp_type = map_dic.get("imp_type")

    id_path = filed_path(map_dic, "id_field", imp_type,http_data)
    fullname_path = filed_path(map_dic, "fullname", imp_type,http_data)
    parentuuid_path = filed_path(map_dic, "parentuuid", imp_type,http_data)
    map_filed.setdefault(imp_pos,{}).setdefault("id_field",id_path)
    map_filed.setdefault(imp_pos, {}).setdefault("fullname", fullname_path)
    map_filed.setdefault(imp_pos, {}).setdefault("parentuuid", parentuuid_path)


    return map_filed



def filed_path(map_dic, filed, imp_type,http_data):
    # new_path = {}
    path = []
    id_field = map_dic.get(filed)
    id_path = find_values_in_dict_little(http_data, id_field, imp_type)
    if id_path:
        path = id_path.get(id_field)

    return list(set(path))
def load_model_data_window(file_str):
    # 需要放入xlink中进行判断，拼接字符串
    base_dir = "./models_paths/"

    source_file = os.path.join(base_dir, f"{file_str}_rcl.pkl")
    if os.path.exists(source_file):
        with open(source_file, "rb") as fp:
            return pickle.load(fp)
    return {}

if __name__ == '__main__':
    data = {
        "con": {
            "数据目录-目录管理-组织结构_搜索31": {
                "url": {
                    "judge": "=",
                    "msg": "/dataasset/api/dataasset/other/queryOrgTree"
                }
            }
        },
        "datas": [
            {
                "data": {
                    "time": "2024-07-31T16:25:42",
                    "app": "10.18.80.25:8215",
                    "app_name": "高质量数据中心",
                    "flow_id": "1178586086558839",
                    "urld": "http://10.18.80.25:8215/dataasset/api/dataasset/other/queryOrgTree",
                    "url": "/dataasset/api/dataasset/other/queryOrgTree",
                    "name": "数据目录-目录管理-组织结构",
                    "account": "",
                    "auth_type": 5,
                    "dstport": 8215,
                    "srcip": "10.18.80.10",
                    "parameter": "keyword=人大",
                    "real_ip": "",
                    "http_method": "POST",
                    "status": 200,
                    "api_type": "5",
                    "qlength": 0,
                    "yw_count": 0,
                    "length": "95920",
                    "user_info": "",
                    "srcport": 50864,
                    "dstip": "10.18.80.25",
                    "risk_level": "1",
                    "content_length": 95920,
                    "id": "1722414660620834277",
                    "age": 452381,
                    "content_type": "JSON",
                    "key": "\"\"",
                    "info": "{}",
                    "request_body": "",
                    "response_body": "{\"success\":true,\"fieldErrors\":{},\"actionErrors\":[],\"messages\":[\"操作成功\"],\"totalCount\":3,\"data\":[{\"cmmNodeType\":\"T\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区发改经信局\",\"crorgLevelCode\":\"06\",\"crorgName\":\"拱墅区发改经信局\",\"crorgOrder\":1857,\"crorgOuterUuid\":\"GO_3df78a34867e40e6a337eb606d0cea95\",\"crorgParentUuid\":\"\",\"crorgStatus\":\"1\",\"crorgType\":\"T\",\"crorgUnid\":5577810,\"crorgUpdateTime\":\"2023-12-11 16:54:38\",\"crorgUuid\":\"ORG_83FFCCAA958640779F7E771A5F0444E9\",\"depth\":1,\"ext\":{},\"fullType\":\"TT\",\"iconSkin\":\"xtree-depth-1 xtree-type-T \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:38\",\"leaf\":true,\"levelCode\":\"06\",\"majorType\":\"T\",\"minorType\":\"T\",\"order\":1857,\"parent\":false,\"parentUuid\":\"\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区发改经信局\",\"type\":\"T\",\"unid\":5577810,\"uuid\":\"ORG_83FFCCAA958640779F7E771A5F0444E9\"},{\"children\":[{\"children\":[{\"cmmNodeType\":\"3\",\"crorgCreateTime\":\"2023-12-11 16:32:16\",\"crorgFullName\":\"拱墅区人大领导\",\"crorgLevelCode\":\"06010000\",\"crorgName\":\"拱墅区人大领导\",\"crorgOrder\":453,\"crorgOuterUuid\":\"GO_8fa66d4ad8c64b18a18cfcc09a346760\",\"crorgParentUuid\":\"ORG_A746EB07DBF6420EB356A0833705DB01\",\"crorgStatus\":\"1\",\"crorgType\":\"3\",\"crorgUnid\":5575072,\"crorgUpdateTime\":\"2023-12-11 16:54:40\",\"crorgUuid\":\"ORG_94D2460F32534E68A2AD481BF2A59B07\",\"depth\":4,\"ext\":{},\"fullType\":\"33\",\"iconSkin\":\"xtree-depth-4 xtree-type-3 \",\"intMap\":{},\"lastUpdateTime\":\"2023-12-11 16:54:40\",\"leaf\":true,\"levelCode\":\"06010000\",\"majorType\":\"3\",\"minorType\":\"3\",\"order\":453,\"parent\":false,\"parentUuid\":\"ORG_A746EB07DBF6420EB356A0833705DB01\",\"status\":\"1\",\"strList\":[],\"strMap\":{},\"text\":\"拱墅区人大领导\",\"type\":\"3\",\"unid\":5575072,\"uuid\":\"ORG_94D2460F32534E68A2AD481BF2A59B07\"}]}",
                    "request_body_json": "{}",
                    "parameter_json": "{}"
                },
                "imps": [
                    {
                        "imp_type": "JSON",
                        "imp_data": "success",
                        "imp_name": "返回结果>>执行状态",
                        "imp_pos": "response_body",
                        "imp_uid": "id-lz9lcda7-f5eas89bg"
                    },
                    {
                        "imp_type": "JSON",
                        "imp_data": "crorgUuid",
                        "imp_name": "返回结果>>当前ID",
                        "imp_pos": "response_body",
                        "imp_uid": "id-m0p1027b-b09fc8ous"
                    },
                    {
                        "imp_type": "JSON",
                        "imp_data": "crorgParentUuid",
                        "imp_name": "返回结果>>父ID",
                        "imp_pos": "response_body",
                        "imp_uid": "id-m0p10by1-6dtr6kfv5"
                    },
                    {
                        "imp_type": "JSON",
                        "imp_data": "crorgFullName",
                        "imp_name": "返回结果>>当前名称",
                        "imp_pos": "response_body",
                        "imp_uid": "id-m0p10kdv-7jzrnc9xm"
                    }
                ],
                "filed_map": {
                    "associate_url": "",
                    "id_field": "crorgUuid",
                    "fields": {
                        "fullname": "crorgFullName",
                        "parentuuid": "crorgParentUuid"
                    }
                },
                "idx": 0
            }
        ]
    }

    data1 = {
        "con": {
            "组织名称信息": {
                "url": {
                    "judge": "=",
                    "msg": "http://59.202.68.95:8215/dataasset/api/dataasset/other/queryOrgTree"
                }
            }
        },
        "datas": [
            {
                "data": {
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
                "imps": [
                    {
                        "imp_type": "TEXT",
                        "imp_data": "ORG_21C028E1CF26409E80A270821D44AC4C",
                        "imp_name": "操作>>组织名称",
                        "imp_pos": "parameter",
                        "imp_uid": "id-m0epppf9-uepklgyss"
                    },
                    {
                        "imp_type": "JSON_mutil",
                        "imp_data": "crorgFullName",
                        "imp_name": "返回结果>>组织名",
                        "imp_pos": "response_body",
                        "imp_uid": "id-m0epyp0q-so57iovnn"
                    },
                    {
                        "imp_type": "JSON_mutil",
                        "imp_data": "crorgUuid",
                        "imp_name": "返回结果>>当前ID",
                        "imp_pos": "response_body",
                        "imp_uid": "id-m0q2ji05-qas2blpbl"
                    },
                    {
                        "imp_type": "JSON_mutil",
                        "imp_data": "crorgParentUuid",
                        "imp_name": "返回结果>>父级ID",
                        "imp_pos": "response_body",
                        "imp_uid": "id-m0q2jrt1-did1ymm9e"
                    }
                ],
                "idx": 0
            }
        ],
        "map_tree": {
            "ass_url":"",
            "imp_pos": "response_body",
            "imp_type": "JSON_mutil",
            "id_field": "crorgUuid",
            "fullname": "crorgFullName",
            "parentuuid": "crorgParentUuid",
            "data_id": 0,
        },
        "MapField":{
            "预警主体类型":{
                "":"全部",
                "0":"企业",
                "1":"事件",
                "2":"人员"
            },
            "反馈状态":{"":"全部","0":"未反馈","1":"已反馈"},

        },
        "start_dict_assoc":"组织名称"
    }
    con = data1.get("con")
    datas = data1.get("datas")
    tree =data1.get("map_tree")
    intell_rule = handle_project(con, datas)


    map_filed =  map_tree(tree,datas)
    print(map_filed)

    da = load_model_data_window("operevent")
    print(da)