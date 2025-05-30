import pyarrow.parquet as pq
from tqdm import tqdm
import os
import requests

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
    id = data['instance_id'].split('-')[-1]
    problem_statement = data['problem_statement']
    image_assets = data['image_assets']
    if not os.path.exists('problem_statement/' + repo):
        os.makedirs('problem_statement/' + repo)
    with open('problem_statement/' + repo + '/' + id + '.md', 'w', encoding='UTF-8') as md:
        md.write(problem_statement.strip())
    if not os.path.exists('pic/' + repo + '/' + id):
        os.makedirs('pic/' + repo + '/' + id)
    for image in image_assets:
        if 'https://marked.js.org/demo/?text=%23%20Expected%20result%0A%0A%5B!%5BManny%20Pacquiao%5D' in image or 'https://content.markdowner.net/emoji/g/64/1f44d.png' in image:
            continue
        try:
            image_name = os.path.basename(image)
            save_path = os.path.join('ps_pic/' + repo + '/' + id, image_name)
            if os.path.exists(save_path):
                continue
            response = requests.get(image)
            if response.status_code == 200:
                with open(save_path, 'wb') as file:
                    file.write(response.content)
            else:
                print(repo + '/' + id)
                print(image)
                print('-' * 20)
        except:
            print(repo + '/' + id)
            print(image)
            print('-' * 20)
