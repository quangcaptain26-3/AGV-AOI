import os
import re
import pandas as pd

def _normalize_log_inputs(paths_or_folder):
    if paths_or_folder is None:
        return []
    if isinstance(paths_or_folder, (list, tuple, set)):
        return [p for p in paths_or_folder if isinstance(p, str) and p.lower().endswith(".txt") and os.path.isfile(p)]
    if isinstance(paths_or_folder, str):
        if os.path.isdir(paths_or_folder):
            folder = paths_or_folder
            return [
                os.path.join(folder, name)
                for name in os.listdir(folder)
                if name.lower().endswith(".txt") and os.path.isfile(os.path.join(folder, name))
            ]
        if os.path.isfile(paths_or_folder) and paths_or_folder.lower().endswith(".txt"):
            return [paths_or_folder]
    return []


def parse_agv_logs(paths_or_folder):
    offline_events, api_errors, system_events = [], [], []
    # Timestamp trong log thực tế đôi khi không nằm đầu dòng và có thể có milliseconds
    # Log của bạn có thể có nhiều khoảng trắng giữa ngày và giờ
    time_pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})(?:\.\d+)?'

    file_paths = _normalize_log_inputs(paths_or_folder)
    ts_min_all = None
    ts_max_all = None
    for file_path in file_paths:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                time_match = re.search(time_pattern, line)
                if not time_match:
                    continue

                try:
                    timestamp = pd.to_datetime(time_match.group(1))
                except Exception:
                    continue

                if ts_min_all is None or timestamp < ts_min_all:
                    ts_min_all = timestamp
                if ts_max_all is None or timestamp > ts_max_all:
                    ts_max_all = timestamp

                # 1. Rớt mạng
                offline_match = re.search(r'(\d+)号AGV已经掉线', line)
                if offline_match:
                    agv_id = offline_match.group(1)
                    offline_events.append({
                        'TS': timestamp,
                        'Hour': timestamp.strftime('%d/%m %H:00'),
                        'AGV': agv_id,
                    })
                    system_events.append(f"[{timestamp.strftime('%H:%M:%S')}] AGV {agv_id}: BỊ MẤT KẾT NỐI (OFFLINE)")

                # 2. Lỗi API Server
                if ("无法连接到远程服务器" in line) or ("Unable to connect to the remote server" in line):
                    url_match = re.search(r'https?://[^\s，,]+', line)
                    api_name_match = re.search(r'/agvapi/([A-Za-z0-9_]+)', line)
                    api_name = api_name_match.group(1) if api_name_match else "api"
                    api_errors.append({
                        'TS': timestamp,
                        'Hour': timestamp.strftime('%d/%m %H:00'),
                        'API': api_name,
                        'URL': url_match.group(0) if url_match else "",
                    })

                # 3. Sự kiện Thang máy / Sạc
                event_match = re.search(r'(呼叫电梯|释放电梯|充电中|等待对接完成|释放资源集\d+|充电桩\d+对接完成)', line)
                if event_match:
                    agv_id = re.search(r'(\d+)号', line)
                    agv = agv_id.group(1) if agv_id else "Sys"
                    system_events.append(f"[{timestamp.strftime('%H:%M:%S')}] AGV {agv}: {event_match.group(1)}")

    # Gom nhóm dữ liệu
    if offline_events:
        _offline = pd.DataFrame(offline_events)
        df_offline = _offline.groupby(['Hour', 'AGV']).size().reset_index(name='Count')
    else:
        df_offline = pd.DataFrame()
    if api_errors:
        _api = pd.DataFrame(api_errors)
        df_api = _api.groupby(['Hour', 'API']).size().reset_index(name='Count')
    else:
        df_api = pd.DataFrame()
    
    coverage = {
        "ts_min": ts_min_all,
        "ts_max": ts_max_all,
        "files": len(file_paths),
    }

    # Không lọc event để người xem nắm được toàn cảnh
    return df_offline, df_api, system_events, coverage