import time, datetime, json
from pathlib import Path
from eamis_sys import EamisCatcher
from eamis_sys.utils import spin_until_date


HERE = Path(__file__).parent


# 这个是选课时间
elect_date_info = (2024, 8, 25, 13, 0, 0) 

# 这个是你的选课计划
plan = {
    '1628': ['2577', '2599', '2589'],
}


client = EamisCatcher.from_webview()
print('---- 登录成功')
prepared_map, info_map = client.prepare_id(plan)
print('---- 课程数据加载成功')
elect_date = datetime.datetime(*elect_date_info)
print(f'---- 等待{elect_date}')
spin_until_date(elect_date)
print('---- 开始执行')
catch_log = client.speed_catch(prepared_map)
print('---- 执行完毕，记录日志')
with open(HERE / 'log.json', 'wt', encoding='utf-8') as log_wfp:
    log = { 'catch_results': catch_log, 'info_map': info_map, }
    json.dump(log, log_wfp, ensure_ascii=False, indent=4)
print('---- 日志已写入log.json')
