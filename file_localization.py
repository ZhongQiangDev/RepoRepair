import os
import json
import math
import time
import requests
from openai import OpenAI
import pyarrow.parquet as pq
from PIL import Image
import base64
from dashscope import get_tokenizer
import tiktoken
from tqdm import tqdm

os.environ["OPENAI_API_KEY"] = "your-key"
os.environ["OPENAI_BASE_URL"] = "your-url"

tokenizer = get_tokenizer('gpt-4o')


def openai_chat(prompt, images, root):
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL")
    )
    content = [{"type": "text", "text": prompt}]
    for image in images:
        image_name = os.path.basename(image)
        image_path = os.path.join(root, image_name)
        if not os.path.exists(image_path):
            continue
        if image.endswith('.gif'):
            gif_key_folder = os.path.join(root, 'gif_key')
            gif_key_list = os.listdir(gif_key_folder)
            video_list = []
            for gif_key in gif_key_list:
                if gif_key.startswith(image_name):
                    base64_image = encode_image(os.path.join(gif_key_folder, gif_key))
                    video_list.append(f"data:image/png;base64,{base64_image}")
            if len(video_list) < 4:
                for video in video_list:
                    content.append({"type": "image_url", "image_url": {"url": video}})
            else:
                content.append({"type": "video", "video": video_list})
        elif image_path.endswith('.png'):
            base64_image = encode_image(image_path)
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}})
        elif image_path.endswith('.jpeg') or image_path.endswith('.jpg'):
            base64_image = encode_image(image_path)
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})
        elif image_path.endswith('.webp'):
            base64_image = encode_image(image_path)
            content.append({"type": "image_url", "image_url": {"url": f"data:image/webp;base64,{base64_image}"}})
        else:
            print(f"{image_path} 图片格式不符合QWen输入要求！")
            continue
    try:
        completion = client.chat.completions.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            temperature=0,
            seed=0,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": content}
            ]
        )
        prompt_tokens = completion.usage.prompt_tokens
        completion_tokens = completion.usage.completion_tokens
        total_tokens = completion.usage.total_tokens
        return completion.choices[0].message.content, prompt_tokens, completion_tokens, total_tokens
    except Exception as e:
        print(e)
        return 'ERROR', 0, 0, 0


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def smart_resize(image_path, factor=28, vl_high_resolution_images=False):
    """
    对图像进行预处理。

    参数:
        image_path：图像的路径
        factor：图像转换为Token的最小单位
        vl_high_resolution_images：是否提高模型的单图Token上限

    """
    if not os.path.exists(image_path):
        return 0, 0
    # 打开指定的PNG图片文件
    try:
        image = Image.open(image_path)
    except:
        return 0, 0

    # 获取图片的原始尺寸
    height = image.height
    width = image.width
    # 将高度调整为28的整数倍
    h_bar = round(height / factor) * factor
    # 将宽度调整为28的整数倍
    w_bar = round(width / factor) * factor

    # 图像的Token下限：4个Token
    min_pixels = 28 * 28 * 4

    # 根据vl_high_resolution_images参数确定图像的Token上限
    if not vl_high_resolution_images:
        max_pixels = 1280 * 28 * 28
    else:
        max_pixels = 16384 * 28 * 28

    # 对图像进行缩放处理，调整像素的总数在范围[min_pixels,max_pixels]内
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = math.floor(height / beta / factor) * factor
        w_bar = math.floor(width / beta / factor) * factor
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = math.ceil(height * beta / factor) * factor
        w_bar = math.ceil(width * beta / factor) * factor
    return h_bar, w_bar


find_file_instruction = '''
Please look through the following GitHub problem description with images/videos, and repository information, then provide a list of files each of which would need to edit to fix the problem.

### GitHub Problem Description ###
{problem_statement}

###

### Repository Information ###
{knowledge}

###

Please follow these steps to answer:
1. Identify the wrong behavior involved in `GitHub Problem Description`
2. Analyze the cause behind the wrong behavior
3. Find up to 5 files most related to the cause from `Repository Information`. The returned files should be separated by new lines ordered by most to least important and wrapped with ```
For example:
```
file1.js
file2.js
...
```
'''

if __name__ == '__main__':
    parquet_file1 = pq.ParquetFile('SWE-bench_M/dev-00000-of-00001.parquet')
    data1 = parquet_file1.read().to_pandas()
    parquet_file2 = pq.ParquetFile('SWE-bench_M/test-00000-of-00001.parquet')
    data2 = parquet_file2.read().to_pandas()

    data_dict = {}
    length = len(data1['problem_statement'])
    for i in range(length):
        data_dict[str(data1['repo'][i]) + '/' + str(data1['instance_id'][i]).split('-')[-1]] = {'problem_statement': str(data1['problem_statement'][i]),
                                                                                                'image_assets': list(data1['image_assets'][i])}
    length = len(data2['problem_statement'])
    for i in range(length):
        data_dict[str(data2['repo'][i]) + '/' + str(data2['instance_id'][i]).split('-')[-1]] = {'problem_statement': str(data2['problem_statement'][i]),
                                                                                                'image_assets': list(data2['image_assets'][i])}

    prompt_token_count = 0
    completion_token_count = 0

    for repo in os.listdir('repo'):
        for repo_sub in os.listdir('repo/' + repo):
            repo_name = repo + '/' + repo_sub

            for repo_id in os.listdir('repo/' + repo_name):

                repo = repo_name + '/' + repo_id
                repo_doc_file_dir = 'repo_document_file/' + repo_name + '/' + repo_id
                repo_doc_meta = 'repo_doc_meta/' + repo_name + '/' + repo_id + '.jsonl'
                root = 'pic/' + repo_name + '/' + str(repo_id)

                # GitHub Problem Description
                problem_statement = data_dict[repo]['problem_statement']
                problem_statement_list = list(problem_statement.split('\n'))
                image_assets = data_dict[repo]['image_assets']
                for line in problem_statement_list.copy():
                    for image in image_assets:
                        if image in line:
                            if line in problem_statement_list:
                                problem_statement_list.remove(line)
                new_problem_statement = '\n'.join(problem_statement_list)

                pic_tokens = 0
                for image in image_assets:
                    image_name = os.path.basename(image)
                    image_path = os.path.join(root, image_name)
                    if image_path.endswith('.gif'):
                        gif_key_folder = os.path.join(root, 'gif_key')
                        gif_key_list = os.listdir(gif_key_folder)
                        for gif_key in gif_key_list:
                            if gif_key.startswith(image_name):
                                h_bar, w_bar = smart_resize(os.path.join(gif_key_folder, gif_key))
                                pic_tokens += int((h_bar * w_bar) / (28 * 28))
                    else:
                        h_bar, w_bar = smart_resize(image_path)
                        pic_tokens += int((h_bar * w_bar) / (28 * 28))

                doc_meta = []
                with open('repo_doc_meta/' + repo_name + '/' + repo_id + '.jsonl') as f:
                    for line in f:
                        doc_meta.append(json.loads(line))

                # RAG
                rag_file_list = []
                with open('repo_file_rag/' + repo_name + '/' + repo_id + '.txt') as f:
                    for line in f.readlines():
                        if line.strip() != '':
                            rag_file_list.append('\\'.join(line.strip().split('\\')[-1].replace('.txt', '').split('_')[3:]))
                rag_file_list.sort()

                # Repository Knowledge
                knowledge_list = []
                for doc in doc_meta:
                    if not doc['node_meta']:
                        continue
                    file_path = doc['file_name']

                    for rag_file in rag_file_list:
                        if rag_file in file_path:
                            # file_name
                            file_knowledge = {'file_name': '_'.join(file_path.replace('\\', '/').split('/')[4:])}
                            # file_summary
                            repo_doc_file = repo_doc_file_dir + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '.txt'
                            if not os.path.exists(repo_doc_file):
                                file_knowledge['file_summary'] = "None"
                            else:
                                with open(repo_doc_file, 'r', encoding='UTF-8') as f:
                                    summary = ""
                                    for line in f.readlines():
                                        if line.strip() == '':
                                            continue
                                        summary += line.strip() + '\n'
                                    if 'file_summary' not in file_knowledge.keys():
                                        file_knowledge['file_summary'] = summary.replace('**Conclusion**:', 'Summary:').replace('**Summary of code description**:', 'Class/Function:').replace('**', '').strip()
                                    else:
                                        file_knowledge['file_summary'] += summary.replace('**Conclusion**:', 'Summary:').replace('**Summary of code description**:', 'Class/Function:').replace('**', '').strip()
                            # # file_elements
                            # elements = []
                            # for node in doc['node_meta']:
                            #     if 'function' in node['class_or_function']['name']:
                            #         continue
                            #     elements.append(node['class_or_function']['name'])
                            # file_knowledge['file_elements'] = elements
                            if file_knowledge in knowledge_list:
                                continue
                            knowledge_list.append(file_knowledge)

                # # Only Name
                # knowledge_str_list = []
                # knowledge_str = "* {file_name}\n"
                # for knowledge in knowledge_list:
                #     knowledge_str_list.append(knowledge_str.format(file_name='`' + knowledge['file_name'].replace('_', '/') + '`'))

                # With Repo
                knowledge_str_list = []
                knowledge_str = "* {file_name}: \n{file_summary}\n\n"
                for knowledge in knowledge_list:
                    knowledge_str_list.append(knowledge_str.format(file_name='`' + knowledge['file_name'].replace('_', '/') + '`', file_summary=knowledge['file_summary']))

                base_prompt = find_file_instruction.format(problem_statement=problem_statement, knowledge="")
                text_tokens = len(tokenizer.encode(base_prompt))
                if text_tokens + pic_tokens > 128000:
                    print("图片占用token量太多！")
                    pass

                # knowledge_str_list.sort(key=lambda x: len(x))
                max_index_record = []
                knowledge = ''
                for index in range(len(knowledge_str_list)):
                    knowledge += knowledge_str_list[index] + '\n'
                    current_prompt = find_file_instruction.format(problem_statement=problem_statement, knowledge=knowledge)
                    text_tokens = len(tokenizer.encode(current_prompt))
                    if text_tokens + pic_tokens < 128000:
                        if index == len(knowledge_str_list) - 1:
                            max_index_record.append(index)
                        continue
                    else:
                        knowledge = ''
                        max_index_record.append(index - 1)
                # max_index_record = [5, 9, ...] -> (0, 5), (6, 9), ...
                print(repo_name + '-' + repo_id + ': number of patch for prompting is: ' + str(len(max_index_record)))
                for i in range(len(max_index_record)):
                    if i == 0:
                        max_index = max_index_record[i]
                        if max_index == 0:
                            knowledge = knowledge_str_list[0]
                        else:
                            knowledge = '\n'.join(knowledge_str_list[:max_index + 1])
                    else:
                        max_index = max_index_record[i]
                        start_index = max_index_record[i - 1] + 1
                        knowledge = '\n'.join(knowledge_str_list[start_index:max_index + 1])
                    prompt = find_file_instruction.format(problem_statement=problem_statement, knowledge=knowledge)

                    # print(prompt)

                    if not os.path.exists('buggy_files/' + repo_name):
                        os.makedirs('buggy_files/' + repo_name)
                    if os.path.exists('buggy_files/' + repo_name + '/' + str(repo_id) + '.txt'):
                        if len(max_index_record) < 2:
                            continue
                    max_try = 3
                    while max_try > 0:
                        generated_text, prompt_tokens, completion_tokens, total_tokens = openai_chat(prompt, image_assets, root='ps_pic/' + repo_name + '/' + str(repo_id))
                        # generated_text, prompt_tokens, completion_tokens, total_tokens = openai_chat(prompt, image_assets)
                        if generated_text is not None:
                            if generated_text == 'ERROR':
                                max_try -= 1
                            else:
                                max_try = 0
                                prompt_token_count += prompt_tokens
                                completion_token_count += completion_tokens
                                print("Number of prompt tokens is " + str(prompt_tokens))
                                print("Number of completion tokens is " + str(completion_tokens))
                                with open('buggy_files-2/buggy_files/' + repo_name + '/' + str(repo_id) + '.txt', 'a', encoding='UTF-8') as f:
                                    f.write(generated_text + '\n')
                                    print('buggy_files/' + repo_name + '/' + str(repo_id) + '.txt is \033[92msuccessfully\033[0m generated')
                        else:
                            max_try -= 1
                        time.sleep(5)

    print("Total number of prompt tokens is " + str(prompt_token_count))
    print("Total number of completion tokens is " + str(completion_token_count))
