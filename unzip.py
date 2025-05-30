import os
import pyarrow.parquet as pq
from tqdm import tqdm
import zipfile
import shutil


def unzip_and_rename(zip_path, extract_to, new_folder_name):
    """
    解压ZIP文件到指定文件夹，并重命名解压后的文件夹。

    :param zip_path: ZIP文件的路径
    :param extract_to: 解压到的目标文件夹
    :param new_folder_name: 解压后文件夹的新名称
    """
    # 确保目标文件夹存在
    if not os.path.exists(extract_to):
        os.makedirs(extract_to)

    # 临时解压路径
    temp_extract_path = os.path.join(extract_to, "temp_extracted")

    # 解压ZIP文件到临时文件夹
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # 遍历ZIP文件中的每个文件或文件夹
        for file_info in zip_ref.infolist():
            try:
                # 尝试解压文件或文件夹
                zip_ref.extract(file_info, temp_extract_path)
            except Exception as e:
                # 捕获异常并跳过错误文件
                print(f"解压失败: {file_info.filename}，错误原因: {e}")

    # 获取解压后的文件夹名称（假设ZIP文件中只有一个顶级文件夹）
    extracted_folder_name = os.listdir(temp_extract_path)[0]
    extracted_folder_path = os.path.join(temp_extract_path, extracted_folder_name)

    # 新文件夹路径
    new_folder_path = os.path.join(extract_to, new_folder_name)

    # 重命名文件夹
    shutil.move(extracted_folder_path, new_folder_path)

    # 删除临时解压文件夹
    shutil.rmtree(temp_extract_path)

    print(f"文件夹已解压并重命名为: {new_folder_path}")


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
    if not os.path.exists('repo/' + repo):
        os.makedirs('repo/' + repo)
    id = data['instance_id'].split('-')[-1]
    if os.path.exists('repo/' + repo + '/' + id):
        continue
    zip_path = 'zip/' + repo + '/' + id + '.zip'
    extract_to = 'repo/' + repo
    new_folder_path = id

    print(zip_path)
    unzip_and_rename(zip_path, extract_to, new_folder_path)

