import os
import json
import openai
from openai import OpenAI
import requests
from tqdm import tqdm
import time
import shutil
from DiffParser import DiffParser
import transformers

tokenizer = transformers.AutoTokenizer.from_pretrained('deepseek/', trust_remote_code=True)


def deepseek_chat(prompt):
    url = "https://api.siliconflow.cn/v1/chat/completions"

    payload = {
        "model": "deepseek-ai/DeepSeek-V3",
        "messages": [
            {"role": "system", "content": "You are an AI documentation assistant."},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "max_tokens": 4096,
        "frequency_penalty": 0,
        "temperature": 0,
        "response_format": {"type": "text"},
        "top_p": 1
    }
    headers = {
        "Authorization": "Bearer your-key",
        "Content-Type": "application/json"
    }
    try:
        response = requests.request("POST", url, json=payload, headers=headers)
        if response.status_code == 200:
            response_dict = json.loads(response.text)
            usage = response_dict['usage']
            prompt_tokens = usage['prompt_tokens']  # 提示文本消耗的 Token 数量
            completion_tokens = usage['completion_tokens']  # 生成文本消耗的 Token 数量
            total_tokens = usage['total_tokens']  # 总共消耗的 Token 数量
            return response_dict['choices'][0]['message']['content'], prompt_tokens, completion_tokens, total_tokens
        else:
            print("Response status code:", response.status_code)
            return int(response.status_code), 0, 0, 0
    except Exception as e:
        print("An unexpected error occurred:", e)
        return None, 0, 0, 0


def generate_document(repo_name, repo_id):
    func_doc_path = 'repo_document_func/' + repo_name + '/' + repo_id
    func_doc_list = os.listdir(func_doc_path)
    func_doc_meta = {}
    file_name = ""
    for func_doc in tqdm(func_doc_list):
        if file_name == "":
            if 'function' in func_doc or 'class' in func_doc:
                str_list = func_doc.replace('.txt', '').split("_")
                file_name = '_'.join(str_list[:-2]).rstrip('_')
                func_name = '_'.join(str_list[-2:])
            else:
                str_list = func_doc.replace('.txt', '').split("_")
                file_name = '_'.join(str_list[:-1]).rstrip('_')
                func_name = '_'.join(str_list[-1:])
        else:
            if 'function' in func_doc or 'class' in func_doc:
                str_list = func_doc.replace('.txt', '').split("_")
                sub_file_name = '_'.join(str_list[:-2]).rstrip('_')
                func_name = '_'.join(str_list[-2:])
            else:
                str_list = func_doc.replace('.txt', '').split("_")
                sub_file_name = '_'.join(str_list[:-1]).rstrip('_')
                func_name = '_'.join(str_list[-1:])
            if file_name != sub_file_name:
                file_name = sub_file_name

        with open(os.path.join(func_doc_path, func_doc), 'r', encoding='utf-8') as f:
            func_doc_content = f.readlines()
            func_doc = ""
            flag = False
            for line in func_doc_content:
                if line.startswith('**Code Description**:'):
                    flag = True
                if flag:
                    if line.startswith('**Note**:'):
                        break
                    func_doc += line.strip() + '\n'

        if file_name not in func_doc_meta.keys():
            func_doc_meta[file_name] = [{'func_or_class_name': func_name, 'code_description': func_doc}]
        else:
            func_doc_meta[file_name].append({'func_or_class_name': func_name, 'code_description': func_doc})

    save_directory = 'repo_document_file/' + repo_name + '/' + repo_id
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)

    print("Deepseek starts to generate the documentation of files for " + repo_name + "-" + repo_id + "...")
    for file_name in tqdm(func_doc_meta.keys()):
        max_try = 5
        file_type = file_name.split('.')[-1]
        code_description = ""
        func_list = func_doc_meta[file_name]
        index = 1
        for func in func_list:
            code_description += str(index) + '. ' + func['code_description'] + '\n'
            index += 1
        prompt = doc_generation_instruction.format(file_type=file_type, code_description=code_description)
        if os.path.exists(save_directory + '/' + file_name + '.txt'):
            continue

        try:
            token_list = tokenizer.encode(prompt)
            if len(token_list) > 128000:
                print(save_directory + '/' + file_name + '.txt is too \033[91mlong\033[0m to be generated')
                continue
        except:
            continue

        while max_try > 0:
            generated_text, prompt_tokens, completion_tokens, total_tokens = deepseek_chat(prompt)
            if generated_text is not None:
                if isinstance(generated_text, int):
                    if generated_text == 400:
                        max_try = 0
                        print(file_name)
                        print('------------------------------------------------------')
                        continue
                    else:
                        max_try -= 1
                        print(save_directory + '/' + file_name + '.txt \033[91mfails\033[0m to be generated')
                        print('Try again!')
                        time.sleep(600)
                else:
                    max_try = 0
                    with open(save_directory + '/' + file_name + '.txt', 'w', encoding='utf-8') as f:
                        f.write(generated_text)
                    print(save_directory + '/' + file_name + '.txt is \033[92msuccessfully\033[0m generated')
            else:
                max_try -= 1
                print(save_directory + '/' + file_name + '.txt \033[91mfails\033[0m to be generated')
                print('Try again!')
            time.sleep(5)
    print('-' * 100)


def generate_document_2(repo_name, old_repo_id, new_repo_id, diff_dict):
    target_directory = repo_name + '/' + new_repo_id
    from_directory = 'repo_document_file/' + repo_name + '/' + old_repo_id
    to_directory = 'repo_document_file/' + repo_name + '/' + new_repo_id
    if not os.path.exists(to_directory):
        os.makedirs(to_directory)

    key = list(diff_dict.keys())[0]
    diff_file_list = diff_dict[key]['file']
    from_files = []
    new_files = []
    for file in os.listdir(from_directory):
        from_files.append(file)
    for diff_file in diff_file_list:
        if 'test' in diff_file:
            continue
        if diff_file.startswith('-'):
            remove_name = diff_file[1:].replace('/', '_')
            for file in from_files.copy():
                if old_repo_id + '_' + remove_name in file:
                    from_files.remove(file)
        # 新增和有修改的文件都需要重新生成
        else:
            if diff_file.startswith('+'):
                new_files.append(os.path.join(target_directory, diff_file[1:]).replace('\\', '/').replace('/', '_'))
            else:
                remove_name = diff_file.replace('/', '_')
                for file in from_files.copy():
                    if old_repo_id + '_' + remove_name in file:
                        from_files.remove(file)
                new_files.append(os.path.join(target_directory, diff_file).replace('\\', '/').replace('/', '_'))

    for file in from_files:
        source_path = os.path.join(from_directory, file)
        file_parts = file.split('_')
        file_parts[2] = new_repo_id
        new_file = '_'.join(file_parts)
        destination_path = os.path.join(to_directory, new_file)
        shutil.copy2(source_path, destination_path)

    print("Deepseek starts to generate the documentation of files for " + repo_name + "-" + new_repo_id + "...")
    print('Number of new files to be generated: ' + str(len(new_files)))
    func_doc_path = 'repo_document_func/' + repo_name + '/' + new_repo_id
    func_doc_list = os.listdir(func_doc_path)
    func_doc_meta = {}
    file_name = ""
    for func_doc in tqdm(func_doc_list):
        if file_name == "":
            if 'function' in func_doc or 'class' in func_doc:
                str_list = func_doc.replace('.txt', '').split("_")
                file_name = '_'.join(str_list[:-2]).rstrip('_')
                func_name = '_'.join(str_list[-2:])
            else:
                str_list = func_doc.replace('.txt', '').split("_")
                file_name = '_'.join(str_list[:-1]).rstrip('_')
                func_name = '_'.join(str_list[-1:])
        else:
            if 'function' in func_doc or 'class' in func_doc:
                str_list = func_doc.replace('.txt', '').split("_")
                sub_file_name = '_'.join(str_list[:-2]).rstrip('_')
                func_name = '_'.join(str_list[-2:])
            else:
                str_list = func_doc.replace('.txt', '').split("_")
                sub_file_name = '_'.join(str_list[:-1]).rstrip('_')
                func_name = '_'.join(str_list[-1:])
            if file_name != sub_file_name:
                file_name = sub_file_name

        with open(os.path.join(func_doc_path, func_doc), 'r', encoding='utf-8') as f:
            func_doc_content = f.readlines()
            func_doc = ""
            flag = False
            for line in func_doc_content:
                if line.startswith('**Code Description**:'):
                    flag = True
                if flag:
                    if line.startswith('**Note**:'):
                        break
                    func_doc += line.strip() + '\n'

        if file_name not in func_doc_meta.keys():
            func_doc_meta[file_name] = [{'func_or_class_name': func_name, 'code_description': func_doc}]
        else:
            func_doc_meta[file_name].append({'func_or_class_name': func_name, 'code_description': func_doc})

    for file_name in tqdm(func_doc_meta.keys()):
        if file_name not in new_files:
            continue
        max_try = 5
        file_type = file_name.split('.')[-1]
        code_description = ""
        func_list = func_doc_meta[file_name]
        index = 1
        for func in func_list:
            code_description += str(index) + '. ' + func['code_description'] + '\n'
            index += 1
        prompt = doc_generation_instruction.format(file_type=file_type, code_description=code_description)
        if os.path.exists(to_directory + '/' + file_name + '.txt'):
            continue

        try:
            token_list = tokenizer.encode(prompt)
            if len(token_list) > 128000:
                print(to_directory + '/' + file_name + '.txt is too \033[91mlong\033[0m to be generated')
                continue
        except:
            continue

        while max_try > 0:
            generated_text, prompt_tokens, completion_tokens, total_tokens = deepseek_chat(prompt)
            if generated_text is not None:
                if isinstance(generated_text, int):
                    if generated_text == 400:
                        max_try = 0
                        print(file_name)
                        print('------------------------------------------------------')
                        continue
                    else:
                        max_try -= 1
                        print(to_directory + '/' + file_name + '.txt \033[91mfails\033[0m to be generated')
                        print('Try again!')
                        time.sleep(600)
                else:
                    max_try = 0
                    with open(to_directory + '/' + file_name + '.txt', 'w', encoding='utf-8') as f:
                        f.write(generated_text)
                    print(to_directory + '/' + file_name + '.txt is \033[92msuccessfully\033[0m generated')
            else:
                max_try -= 1
                print(to_directory + '/' + file_name + '.txt \033[91mfails\033[0m to be generated')
                print('Try again!')
            time.sleep(5)
    print('-' * 100)


def move_element_to_first_new_list(lst, element):
    if element in lst:
        idx = lst.index(element)
        return [lst[idx]] + lst[:idx] + lst[idx + 1:]
    return lst.copy()


doc_generation_instruction = '''
Your task is to summarize and generate documentation based on the given code description of one or more functions or classes in the same file. 
The content of the code descriptions of this {file_type} file (sorted by number) are as follows:\n
{code_description}\n\n
Please generate a detailed summary document for this file based on the code description of function or class in it.\n\n
The standard format is as follows:\n\n
**Summary of code description**: Summarize each code description by a few sentences.\n\n
**Conclusion**: A concise conclusion for the role of this file.\n
'''

if __name__ == '__main__':
    repo_dict = {}
    for repo in tqdm(os.listdir('repo')):
        for repo_sub in os.listdir('repo/' + repo):
            repo_name = repo + '/' + repo_sub
            for repo_id in os.listdir('repo/' + repo_name):
                if repo_name not in repo_dict.keys():
                    repo_dict[repo_name] = [int(repo_id)]
                else:
                    repo_dict[repo_name].append(int(repo_id))
                    repo_dict[repo_name] = sorted(repo_dict[repo_name])

    for repo_name in repo_dict.keys():
        if repo_name in ['Automattic/wp-calypso']:
            continue
        repo_id_list = repo_dict[repo_name]
        if len(repo_id_list) == 1:
            repo_id = repo_id_list[0]
            generate_document(repo_name, str(repo_id))
        else:
            repo_id = repo_id_list[0]
            generate_document(repo_name, str(repo_id))
            for i in range(1, len(repo_id_list)):
                diff_parser = DiffParser()
                old_repo_id = str(repo_id_list[i - 1])
                new_repo_id = str(repo_id_list[i])
                project_dirs = ['repo/' + repo_name + '/' + old_repo_id, 'repo/' + repo_name + '/' + new_repo_id]
                diff_dict = diff_parser.return_diff(project_dirs)
                generate_document_2(repo_name, old_repo_id, new_repo_id, diff_dict)
