import os
import re
import pandas as pd

def _normalize_image_inputs(paths_or_folder):
    if paths_or_folder is None:
        return []
    valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp')
    if isinstance(paths_or_folder, (list, tuple, set)):
        return [
            p for p in paths_or_folder
            if isinstance(p, str)
            and p.lower().endswith(valid_extensions)
            and os.path.isfile(p)
        ]
    if isinstance(paths_or_folder, str):
        if os.path.isdir(paths_or_folder):
            folder = paths_or_folder
            return [
                os.path.join(folder, name)
                for name in os.listdir(folder)
                if name.lower().endswith(valid_extensions)
                and os.path.isfile(os.path.join(folder, name))
            ]
        if os.path.isfile(paths_or_folder) and paths_or_folder.lower().endswith(valid_extensions):
            return [paths_or_folder]
    return []


def parse_aoi_images(paths_or_folder):
    data = []

    file_paths = _normalize_image_inputs(paths_or_folder)
    for file_path in file_paths:
        filename = os.path.basename(file_path)
        status = 'PASS' if 'ALL PASS' in filename.upper() else 'FAIL' if 'FAIL' in filename.upper() else 'UNKNOWN'
        if status == 'UNKNOWN':
            continue

        date_match = re.search(r'\d{8}', filename)
        if date_match:
            data.append({'Date': date_match.group(), 'Status': status, 'File': filename})
                
    if not data:
        return pd.DataFrame(columns=['Date', 'PASS', 'FAIL'])
        
    df = pd.DataFrame(data)
    summary = df.groupby(['Date', 'Status']).size().unstack(fill_value=0).reset_index()
    
    if 'PASS' not in summary.columns: summary['PASS'] = 0
    if 'FAIL' not in summary.columns: summary['FAIL'] = 0
        
    return summary