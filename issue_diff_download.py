import requests
import pyarrow.parquet as pq
import os
from tqdm import tqdm
import time

parquet_file1 = pq.ParquetFile('SWE-bench_M/dev-00000-of-00001.parquet')
data1 = parquet_file1.read().to_pandas()
parquet_file2 = pq.ParquetFile('SWE-bench_M/test-00000-of-00001.parquet')
data2 = parquet_file2.read().to_pandas()

data_list = []
length = len(data1['problem_statement'])
for i in range(length):
    data_list.append({'repo': str(data1['repo'][i]), 'instance_id': str(data1['instance_id'][i]), 'base_commit': str(data1['base_commit'][i]),
                      'problem_statement': str(data1['problem_statement'][i]), 'image_assets': list(data1['image_assets'][i])})
length = len(data2['problem_statement'])
for i in range(length):
    data_list.append({'repo': str(data2['repo'][i]), 'instance_id': str(data2['instance_id'][i]), 'base_commit': str(data2['base_commit'][i]),
                      'problem_statement': str(data2['problem_statement'][i]), 'image_assets': list(data2['image_assets'][i])})

for data in tqdm(data_list):
    repo = data['repo']
    if not os.path.exists('diff/' + repo):
        os.makedirs('diff/' + repo)
    id = data['instance_id'].split('-')[-1]
    if os.path.exists('diff/' + repo + '/' + id + '.diff'):
        continue
    url = 'https://api.github.com/repos/' + repo + '/pulls/' + id
    headers = {'Accept': 'application/vnd.github.full+json'}
    r = requests.get(url, headers)
    if r.status_code != 200:
        print(data['repo'] + ' ' + data['instance_id'])
        print(f"r Status code: {r.status_code}")
        continue
    response_dict = r.json()
    diff_url = response_dict['diff_url']
    print(diff_url)
    diff_headers = {'Accept': 'application/vnd.github.text+json'}
    diff_r = requests.get(diff_url, diff_headers)
    if diff_r.status_code != 200:
        print(f"diff_r Status code: {diff_r.status_code}")
        continue
    with open('diff/' + repo + '/' + id + '.diff', 'w', encoding='UTF-8') as diff:
        diff.write(diff_r.content.decode("utf-8"))
    time.sleep(5)
