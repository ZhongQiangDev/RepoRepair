import pyarrow.parquet as pq
import os
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import requests

driver = webdriver.Edge()

parquet_file1 = pq.ParquetFile('dev-00000-of-00001.parquet')
data1 = parquet_file1.read().to_pandas()
parquet_file2 = pq.ParquetFile('test-00000-of-00001.parquet')
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
    commit = data['base_commit']
    if not os.path.exists('zip/' + repo):
        os.makedirs('zip/' + repo)
    if os.path.exists('zip/' + repo + '/' + id + '.zip'):
        continue

    url = 'https://github.com/' + repo + '/tree/' + commit
    driver.get(url)
    time.sleep(5)

    code_button = driver.find_element(By.XPATH, '//*[@id=":R55ab:"]')
    code_button.click()
    download_url = driver.find_element(By.CLASS_NAME, 'Box-sc-g0xbh4-0.kMpzwx.prc-Link-Link-85e08').get_attribute('href')
    response = requests.get(download_url)
    with open('zip/' + repo + '/' + id + '.zip', 'wb') as file:
        file.write(response.content)
    time.sleep(5)
