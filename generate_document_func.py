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


def get_directory_structure(root_dir, target_file, indent=""):
    """
    递归打印目录结构，并为特定文件添加星号标记
    :param root_dir: 根目录路径
    :param target_file: 需要标记的目标文件名
    :param indent: 缩进字符串，用于显示层级关系
    """
    directory_structure = f"{indent}{os.path.basename(root_dir)}/\n"

    indent += "    "

    for item in os.listdir(root_dir):
        item_path = os.path.join(root_dir, item)
        if os.path.isdir(item_path):
            if 'test' in item_path:
                continue
            directory_structure += get_directory_structure(item_path, target_file, indent)
        else:
            if item.endswith('.js') or item.endswith('.jsx') or item.endswith('.ts'):
                if item == target_file:
                    directory_structure += f"{indent}*{item}\n"
                else:
                    directory_structure += f"{indent}{item}\n"
    return directory_structure


def get_referenced_prompt(save_directory, code_import):
    if len(code_import) == 0:
        return ""
    prompt = [
        """As you can see, the code calls the following objects, their code and docs are as following:"""
    ]
    for reference_item in code_import:
        document_file = save_directory + '/' + reference_item['file'][4:].split('.')[0].replace('/', '_').replace('\\', '_') + '_' + reference_item['function'][
            'name'].strip() + '.txt'
        if os.path.exists(document_file):
            with open(document_file, 'r', encoding='utf-8') as f:
                document = f.read()
        else:
            document = 'None'
        instance_prompt = (
                f"""obj: {reference_item['file']}\nDocument: \n{document}\nRaw code:```\n{reference_item['function']['signature']}\n{reference_item['function']['content']}\n```"""
                + "=" * 10
        )
        prompt.append(instance_prompt)
    return "\n".join(prompt)


def generate_document(repo_name, repo_id):
    target_directory = 'repo/' + repo_name + '/' + repo_id
    save_directory = 'repo_document_func/' + repo_name + '/' + repo_id
    log_path = 'log/' + repo_name + '/func_log-' + repo_id + '.txt'
    logger = ""
    prompt_token_count = 0
    completion_token_count = 0
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)
    if not os.path.exists('log/' + repo_name):
        os.makedirs('log/' + repo_name)
    print("Deepseek starts to generate the documentation of classes or functions for " + repo_name + "-" + repo_id + "...")

    doc_meta = []
    with open('repo_doc_meta/' + repo_name + '/' + repo_id + '.jsonl') as f:
        for line in f:
            doc_meta.append(json.loads(line))

    after_doc = []
    for doc in tqdm(doc_meta):
        file_path = doc['file_name']
        # project_structure = get_directory_structure(target_directory, file_path)
        if not doc['node_meta']:
            continue
        for node_meta in doc['node_meta']:
            max_try = 5
            code_type = node_meta['type']
            parameters_or_attribute = "attributes" if code_type == "Class" else "parameters"
            code_name = node_meta['class_or_function']['name'].strip()
            code_signature = node_meta['class_or_function']['signature'].strip()
            code_content = node_meta['class_or_function']['content'].strip()
            if node_meta['class_or_function']['return']:
                have_return = "**Output Example**: Mock up a possible appearance of the code's return value."
            else:
                have_return = ""
            code_import = node_meta['import']
            reference_letter = get_referenced_prompt(save_directory, code_import)
            if code_import:
                after_doc.append({'file_name': file_path, 'node_meta': {'type': code_type, 'class_or_function': {'signature': code_signature, 'content': code_content, 'name': code_name, 'return': have_return}, 'import': code_import}})
                continue
            prompt = doc_generation_instruction.format(file_path=file_path,
                                                       code_type_tell=code_type,
                                                       code_name=code_name,
                                                       code_content=code_signature + '\n\n' + code_content,
                                                       reference_letter=reference_letter,
                                                       combine_ref_situation="",
                                                       parameters_or_attribute=parameters_or_attribute,
                                                       language="English",
                                                       has_relationship="",
                                                       have_return_tell=have_return)
            if os.path.exists(save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt'):
                continue
            try:
                token_list = tokenizer.encode(prompt)
                if len(token_list) > 128000:
                    print(save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is too \033[91mlong\033[0m to be generated')
                    logger += save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is too long to be generated\n'
                    logger += '\n' + '-' * 50 + '\n'
                    continue
            except:
                continue

            while max_try > 0:
                generated_text, prompt_tokens, completion_tokens, total_tokens = deepseek_chat(prompt)
                if generated_text is not None:
                    if isinstance(generated_text, int):
                        if generated_text == 400:
                            max_try = 0
                            print(file_path)
                            print(code_name)
                            print('------------------------------------------------------')
                            continue
                        else:
                            max_try -= 1
                            logger += save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt fails to be generated\n'
                            logger += '\n' + '-' * 50 + '\n'
                            print(save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt \033[91mfails\033[0m to be generated')
                            print('Try again!')
                            time.sleep(600)
                    else:
                        max_try = 0
                        prompt_token_count += prompt_tokens
                        completion_token_count += completion_tokens
                        with open(save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt', 'w', encoding='utf-8') as f:
                            f.write(generated_text)
                        logger += save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is successfully generated\n'
                        logger += '-' * 50 + '\n'
                        print(save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is \033[92msuccessfully\033[0m generated')
                else:
                    max_try -= 1
                    logger += save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt fails to be generated\n'
                    logger += '\n' + '-' * 50 + '\n'
                    print(save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt \033[91mfails\033[0m to be generated')
                    print('Try again!')
                time.sleep(5)

    print("Deepseek starts to generate the documentation of classes or functions (have imports) for " + repo_name + "-" + repo_id + "...")
    if after_doc:
        first_loop = True
        while after_doc:
            for doc in tqdm(after_doc.copy()):
                max_try = 5
                import_list = doc['node_meta']['import']
                need_after = False
                for imp in import_list:
                    if not os.path.exists(save_directory + '/' + imp['file'][5:].replace('/', '_').replace('\\', '_') + '_' + imp['function']['name'].strip() + '.txt'):
                        print(save_directory + '/' + imp['file'][5:].replace('/', '_').replace('\\', '_') + '_' + imp['function']['name'].strip() + '.txt not exists')
                        need_after = True
                        break
                if need_after:
                    if first_loop:
                        continue
                    else:
                        need_after = False
                # 前置条件都满足
                if need_after is False:
                    file_path = doc['file_name']
                    # project_structure = get_directory_structure(target_directory, file_path)
                    if not doc['node_meta']:
                        after_doc.remove(doc)
                        continue
                    code_type = doc['node_meta']['type']
                    parameters_or_attribute = "attributes" if code_type == "Class" else "parameters"
                    code_name = doc['node_meta']['class_or_function']['name'].strip()
                    code_signature = doc['node_meta']['class_or_function']['signature'].strip()
                    code_content = doc['node_meta']['class_or_function']['content'].strip()
                    have_return = doc['node_meta']['class_or_function']['return']
                    code_import = doc['node_meta']['import']
                    reference_letter = get_referenced_prompt(save_directory, code_import)
                    combine_ref_situation = "and combine it with its calling situation in the project,"
                    has_relationship = "And please include the relationship with its callees in the project from a functional perspective."
                    prompt = doc_generation_instruction.format(file_path=file_path,
                                                               code_type_tell=code_type,
                                                               code_name=code_name,
                                                               code_content=code_signature + '\n\n' + code_content,
                                                               reference_letter=reference_letter,
                                                               combine_ref_situation=combine_ref_situation,
                                                               parameters_or_attribute=parameters_or_attribute,
                                                               language="English",
                                                               has_relationship=has_relationship,
                                                               have_return_tell=have_return)
                    if os.path.exists(save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt'):
                        after_doc.remove(doc)
                        continue
                    try:
                        token_list = tokenizer.encode(prompt)
                        if len(token_list) > 128000:
                            print(save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is too \033[91mlong\033[0m to be generated')
                            logger += save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is too long to be generated\n'
                            logger += '\n' + '-' * 50 + '\n'
                            after_doc.remove(doc)
                            continue
                    except Exception as e:
                        print(e)
                        after_doc.remove(doc)
                        continue
                    while max_try > 0:
                        # generated_text, prompt_tokens, completion_tokens, total_tokens = openai_chat(prompt)
                        generated_text, prompt_tokens, completion_tokens, total_tokens = deepseek_chat(prompt)
                        if generated_text is not None:
                            if isinstance(generated_text, int):
                                if generated_text == 400:
                                    max_try = 0
                                    print(file_path)
                                    print(code_name)
                                    print('------------------------------------------------------')
                                    after_doc.remove(doc)
                                    continue
                                else:
                                    max_try -= 1
                                    logger += save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt fails to be generated\n'
                                    logger += '\n' + '-' * 50 + '\n'
                                    print(save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt \033[91mfails\033[0m to be generated')
                                    print('Try again!')
                                    time.sleep(600)
                            else:
                                max_try = 0
                                prompt_token_count += prompt_tokens
                                completion_token_count += completion_tokens
                                with open(save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt', 'w', encoding='utf-8') as f:
                                    f.write(generated_text)
                                logger += save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is successfully generated\n'
                                logger += '-' * 50 + '\n'
                                print(save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is \033[92msuccessfully\033[0m generated')
                        else:
                            max_try -= 1
                            logger += save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt fails to be generated\n'
                            logger += '\n' + '-' * 50 + '\n'
                            print(save_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt \033[91mfails\033[0m to be generated')
                            print('Try again!')
                        time.sleep(5)

                    after_doc.remove(doc)
            print("First loop is over.")
            first_loop = False
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(logger)
    print("Total number of prompt tokens is " + str(prompt_token_count))
    print("Total number of completion tokens is " + str(completion_token_count))
    print('-' * 100)


def generate_document_2(repo_name, old_repo_id, new_repo_id, diff_dict):
    target_directory = 'repo/' + repo_name + '/' + new_repo_id
    from_directory = 'repo_document_func/' + repo_name + '/' + old_repo_id
    to_directory = 'repo_document_func/' + repo_name + '/' + new_repo_id
    log_path = 'log/' + repo_name + '/func_log-' + new_repo_id + '.txt'
    logger = ""
    prompt_token_count = 0
    completion_token_count = 0
    if not os.path.exists(to_directory):
        os.makedirs(to_directory)
    if not os.path.exists('log/' + repo_name):
        os.makedirs('log/' + repo_name)

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
                new_files.append(os.path.join(target_directory, diff_file[1:].replace('\\', '/')))
            else:
                remove_name = diff_file.replace('/', '_')
                for file in from_files.copy():
                    if old_repo_id + '_' + remove_name in file:
                        from_files.remove(file)
                new_files.append(os.path.join(target_directory, diff_file.replace('\\', '/')))

    for file in from_files:
        source_path = os.path.join(from_directory, file)
        file_parts = file.split('_')
        file_parts[2] = new_repo_id
        new_file = '_'.join(file_parts)
        destination_path = os.path.join(to_directory, new_file)
        shutil.copy2(source_path, destination_path)

    print("Deepseek starts to generate the documentation of classes or functions for " + repo_name + "-" + new_repo_id + "...")
    print('Number of new files to be generated: ' + str(len(new_files)))
    doc_meta = []
    with open('repo_doc_meta/' + repo_name + '/' + new_repo_id + '.jsonl') as f:
        for line in f:
            doc_meta.append(json.loads(line))
    after_doc = []
    for doc in tqdm(doc_meta):
        file_path = doc['file_name'].replace('\\', '/')
        if file_path not in new_files:
            continue
        if not doc['node_meta']:
            continue

        for node_meta in doc['node_meta']:
            max_try = 5
            code_type = node_meta['type']
            parameters_or_attribute = "attributes" if code_type == "Class" else "parameters"
            code_name = node_meta['class_or_function']['name'].strip()
            code_signature = node_meta['class_or_function']['signature'].strip()
            code_content = node_meta['class_or_function']['content'].strip()
            if node_meta['class_or_function']['return']:
                have_return = "**Output Example**: Mock up a possible appearance of the code's return value."
            else:
                have_return = ""
            code_import = node_meta['import']
            reference_letter = get_referenced_prompt(to_directory, code_import)
            if code_import:
                after_doc.append({'file_name': file_path, 'node_meta': {'type': code_type, 'class_or_function': {'signature': code_signature, 'content': code_content, 'name': code_name, 'return': have_return}, 'import': code_import}})
                continue
            prompt = doc_generation_instruction.format(file_path=file_path,
                                                       code_type_tell=code_type,
                                                       code_name=code_name,
                                                       code_content=code_signature + '\n\n' + code_content,
                                                       reference_letter=reference_letter,
                                                       combine_ref_situation="",
                                                       parameters_or_attribute=parameters_or_attribute,
                                                       language="English",
                                                       has_relationship="",
                                                       have_return_tell=have_return)
            if os.path.exists(to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt'):
                continue
            try:
                token_list = tokenizer.encode(prompt)
                if len(token_list) > 128000:
                    print(to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is too \033[91mlong\033[0m to be generated')
                    logger += to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is too long to be generated\n'
                    logger += '\n' + '-' * 50 + '\n'
                    continue
            except:
                continue
            while max_try > 0:
                generated_text, prompt_tokens, completion_tokens, total_tokens = deepseek_chat(prompt)
                if generated_text is not None:
                    if isinstance(generated_text, int):
                        if generated_text == 400:
                            max_try = 0
                            print(file_path)
                            print(code_name)
                            print('------------------------------------------------------')
                            continue
                        else:
                            max_try -= 1
                            logger += to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt fails to be generated\n'
                            logger += '\n' + '-' * 50 + '\n'
                            print(to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt \033[91mfails\033[0m to be generated')
                            print('Try again!')
                            time.sleep(600)
                    else:
                        max_try = 0
                        prompt_token_count += prompt_tokens
                        completion_token_count += completion_tokens
                        with open(to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt', 'w', encoding='utf-8') as f:
                            f.write(generated_text)
                        logger += to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is successfully generated\n'
                        logger += '-' * 50 + '\n'
                        print(to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is \033[92msuccessfully\033[0m generated')
                else:
                    max_try -= 1
                    logger += to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt fails to be generated\n'
                    logger += '\n' + '-' * 50 + '\n'
                    print(to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt \033[91mfails\033[0m to be generated')
                    print('Try again!')
                time.sleep(5)

    print("Deepseek starts to generate the documentation of classes or functions (have imports) for " + repo_name + "-" + new_repo_id + "...")
    if after_doc:
        first_loop = True
        while after_doc:
            for doc in tqdm(after_doc.copy()):
                max_try = 5
                import_list = doc['node_meta']['import']
                need_after = False
                for imp in import_list:
                    if not os.path.exists(to_directory + '/' + imp['file'][5:].replace('/', '_').replace('\\', '_') + '_' + imp['function']['name'].strip() + '.txt'):
                        print(to_directory + '/' + imp['file'][5:].replace('/', '_').replace('\\', '_') + '_' + imp['function']['name'].strip() + '.txt not exists')
                        need_after = True
                        break
                if need_after:
                    if first_loop:
                        continue
                    else:
                        need_after = False
                # 前置条件都满足
                if need_after is False:
                    file_path = doc['file_name']
                    # project_structure = get_directory_structure(target_directory, file_path)
                    if not doc['node_meta']:
                        after_doc.remove(doc)
                        continue
                    code_type = doc['node_meta']['type']
                    parameters_or_attribute = "attributes" if code_type == "Class" else "parameters"
                    code_name = doc['node_meta']['class_or_function']['name'].strip()
                    code_signature = doc['node_meta']['class_or_function']['signature'].strip()
                    code_content = doc['node_meta']['class_or_function']['content'].strip()
                    have_return = doc['node_meta']['class_or_function']['return']
                    code_import = doc['node_meta']['import']
                    reference_letter = get_referenced_prompt(to_directory, code_import)
                    combine_ref_situation = "and combine it with its calling situation in the project,"
                    has_relationship = "And please include the relationship with its callees in the project from a functional perspective."
                    prompt = doc_generation_instruction.format(file_path=file_path,
                                                               code_type_tell=code_type,
                                                               code_name=code_name,
                                                               code_content=code_signature + '\n\n' + code_content,
                                                               reference_letter=reference_letter,
                                                               combine_ref_situation=combine_ref_situation,
                                                               parameters_or_attribute=parameters_or_attribute,
                                                               language="English",
                                                               has_relationship=has_relationship,
                                                               have_return_tell=have_return)
                    if os.path.exists(to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt'):
                        after_doc.remove(doc)
                        continue
                    try:
                        token_list = tokenizer.encode(prompt)
                        if len(token_list) > 128000:
                            print(to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is too \033[91mlong\033[0m to be generated')
                            logger += to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is too long to be generated\n'
                            logger += '\n' + '-' * 50 + '\n'
                            after_doc.remove(doc)
                            continue
                    except Exception as e:
                        print(e)
                        after_doc.remove(doc)
                        continue
                    while max_try > 0:
                        # generated_text, prompt_tokens, completion_tokens, total_tokens = openai_chat(prompt)
                        generated_text, prompt_tokens, completion_tokens, total_tokens = deepseek_chat(prompt)
                        if generated_text is not None:
                            if isinstance(generated_text, int):
                                if generated_text == 400:
                                    max_try = 0
                                    print(file_path)
                                    print(code_name)
                                    print('------------------------------------------------------')
                                    after_doc.remove(doc)
                                    continue
                                else:
                                    max_try -= 1
                                    logger += to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt fails to be generated\n'
                                    logger += '\n' + '-' * 50 + '\n'
                                    print(to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt \033[91mfails\033[0m to be generated')
                                    print('Try again!')
                                    time.sleep(600)
                            else:
                                max_try = 0
                                prompt_token_count += prompt_tokens
                                completion_token_count += completion_tokens
                                with open(to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt', 'w', encoding='utf-8') as f:
                                    f.write(generated_text)
                                logger += to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is successfully generated\n'
                                logger += '-' * 50 + '\n'
                                print(to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt is \033[92msuccessfully\033[0m generated')
                        else:
                            max_try -= 1
                            logger += to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt fails to be generated\n'
                            logger += '\n' + '-' * 50 + '\n'
                            print(to_directory + '/' + file_path[5:].replace('/', '_').replace('\\', '_') + '_' + code_name + '.txt \033[91mfails\033[0m to be generated')
                            print('Try again!')
                        time.sleep(5)

                    after_doc.remove(doc)
            print("First loop is over.")
            first_loop = False
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(logger)
    print("Total number of prompt tokens is " + str(prompt_token_count))
    print("Total number of completion tokens is " + str(completion_token_count))
    print('-' * 100)


def move_element_to_first_new_list(lst, element):
    if element in lst:
        idx = lst.index(element)
        return [lst[idx]] + lst[:idx] + lst[idx + 1:]
    return lst.copy()


doc_generation_instruction = '''
Your task is to generate documentation based on the given code of an object. The purpose of the documentation is to help developers and beginners understand the function and specific usage of the code.
Now you need to generate a document for a {code_type_tell}, whose name is "{code_name}".\n\n
The content of the code is as follows:\n
{code_content}\n\n
{reference_letter}\n\n
Please generate a detailed explanation document for this object based on the code of the target object itself {combine_ref_situation}.\n\n
Please write out the function of this {code_type_tell} in bold plain text, followed by a detailed analysis in plain text
(including all details), in language {language} to serve as the documentation for this part of the code.\n\n
The standard format is as follows:\n\n
**{code_name}**: The function of {code_name} is XXX. (Only code name and one sentence function description are required)\n
**{parameters_or_attribute}**: The {parameters_or_attribute} of this {code_type_tell}.\n
· parameter1: XXX\n
· parameter2: XXX\n
· ...\n
**Code Description**: The description of this {code_type_tell}.\n
(Detailed and CERTAIN code analysis and description...{has_relationship})\n
**Note**: Points to note about the use of the code\n
{have_return_tell}\n\n
Please note:\n
- Any part of the content you generate SHOULD NOT CONTAIN Markdown hierarchical heading and divider syntax.\n
- Write mainly in the desired language. If necessary, you can write with some English words in the analysis and description 
to enhance the document's readability because you do not need to translate the function name or variable name into the target language.\n
'''

documentation_guideline = '''
Keep in mind that your audience is document readers, so use a deterministic tone to generate precise content and don't let them know you're provided with code snippet and documents. 
AVOID ANY SPECULATION and inaccurate descriptions! Now, provide the documentation for the target object in {language} in a professional way.
'''

if __name__ == '__main__':
    old_repo_list = [
        "alibaba-fusion/next/1063", "alibaba-fusion/next/1064", "alibaba-fusion/next/1067", "alibaba-fusion/next/1509",
        "alibaba-fusion/next/1586", "alibaba-fusion/next/1708", "alibaba-fusion/next/1720",
        "alibaba-fusion/next/1742", "alibaba-fusion/next/2355", "alibaba-fusion/next/2860", "alibaba-fusion/next/2919", "alibaba-fusion/next/2923",
        "alibaba-fusion/next/3218", "alibaba-fusion/next/3454", "alibaba-fusion/next/3724", "alibaba-fusion/next/3947",
        "alibaba-fusion/next/4021", "alibaba-fusion/next/4182", "alibaba-fusion/next/4806", "alibaba-fusion/next/4859",
        "alibaba-fusion/next/665", "alibaba-fusion/next/717", "alibaba-fusion/next/94",

        "Automattic/wp-calypso/22242", "Automattic/wp-calypso/23915", "Automattic/wp-calypso/25778",
        "Automattic/wp-calypso/26286", "Automattic/wp-calypso/26335", "Automattic/wp-calypso/29804",
        "Automattic/wp-calypso/33245", "Automattic/wp-calypso/34435",

        "bpmn-io/bpmn-js/1011", "bpmn-io/bpmn-js/1119", "bpmn-io/bpmn-js/1143", "bpmn-io/bpmn-js/1151",
        "bpmn-io/bpmn-js/1168", "bpmn-io/bpmn-js/1172", "bpmn-io/bpmn-js/1174", "bpmn-io/bpmn-js/1192",
        "bpmn-io/bpmn-js/1196", "bpmn-io/bpmn-js/1206", "bpmn-io/bpmn-js/1221", "bpmn-io/bpmn-js/1236",
        "bpmn-io/bpmn-js/1256", "bpmn-io/bpmn-js/1299", "bpmn-io/bpmn-js/1330", "bpmn-io/bpmn-js/1348",
        "bpmn-io/bpmn-js/1434", "bpmn-io/bpmn-js/1442", "bpmn-io/bpmn-js/1542", "bpmn-io/bpmn-js/1557",
        "bpmn-io/bpmn-js/1567", "bpmn-io/bpmn-js/1578", "bpmn-io/bpmn-js/1607", "bpmn-io/bpmn-js/1610", "bpmn-io/bpmn-js/1623",
        "bpmn-io/bpmn-js/1636", "bpmn-io/bpmn-js/1638", "bpmn-io/bpmn-js/1659", "bpmn-io/bpmn-js/1679",
        "bpmn-io/bpmn-js/1719", "bpmn-io/bpmn-js/1720", "bpmn-io/bpmn-js/1847",

        "carbon-design-system/carbon/11664", "carbon-design-system/carbon/12302", "carbon-design-system/carbon/12329", "carbon-design-system/carbon/12384",
        "carbon-design-system/carbon/12410", "carbon-design-system/carbon/15197", "carbon-design-system/carbon/3118", "carbon-design-system/carbon/3139",
        "carbon-design-system/carbon/3362", "carbon-design-system/carbon/3610", "carbon-design-system/carbon/4226",
        "carbon-design-system/carbon/4273", "carbon-design-system/carbon/4286", "carbon-design-system/carbon/4354",
        "carbon-design-system/carbon/4430", "carbon-design-system/carbon/4678", "carbon-design-system/carbon/4801",
        "carbon-design-system/carbon/4816", "carbon-design-system/carbon/4862", "carbon-design-system/carbon/4891",
        "carbon-design-system/carbon/4952", "carbon-design-system/carbon/4991", "carbon-design-system/carbon/4999",
        "carbon-design-system/carbon/5156", "carbon-design-system/carbon/5173", "carbon-design-system/carbon/5330",
        "carbon-design-system/carbon/6566", "carbon-design-system/carbon/6675", "carbon-design-system/carbon/6726", "carbon-design-system/carbon/6906",
        "carbon-design-system/carbon/6964", "carbon-design-system/carbon/6976", "carbon-design-system/carbon/7353",
        "carbon-design-system/carbon/7722", "carbon-design-system/carbon/8912", "carbon-design-system/carbon/8945",
        "carbon-design-system/carbon/9136", "carbon-design-system/carbon/9189", "carbon-design-system/carbon/9402",
        "carbon-design-system/carbon/9700", "carbon-design-system/carbon/9994",

        "chartjs/Chart.js/10157", "chartjs/Chart.js/10301", "chartjs/Chart.js/10806", "chartjs/Chart.js/11116",
        "chartjs/Chart.js/11352", "chartjs/Chart.js/8705", "chartjs/Chart.js/8710", "chartjs/Chart.js/8867",
        "chartjs/Chart.js/8868", "chartjs/Chart.js/9027", "chartjs/Chart.js/9101", "chartjs/Chart.js/9367",
        "chartjs/Chart.js/9613", "chartjs/Chart.js/9766",

        "diegomura/react-pdf/1178", "diegomura/react-pdf/1280", "diegomura/react-pdf/471", "diegomura/react-pdf/1541",

        "eslint/eslint/12472", "eslint/eslint/12652", "eslint/eslint/14242", "eslint/eslint/15243",
        "eslint/eslint/17618", "eslint/eslint/8120", "eslint/eslint/8850", "eslint/eslint/9436",

        "GoogleChrome/lighthouse/10176", "GoogleChrome/lighthouse/10295", "GoogleChrome/lighthouse/11489",
        "GoogleChrome/lighthouse/14479", "GoogleChrome/lighthouse/14587", "GoogleChrome/lighthouse/14672",
        "GoogleChrome/lighthouse/14800", "GoogleChrome/lighthouse/15092", "GoogleChrome/lighthouse/1563",
        "GoogleChrome/lighthouse/1617", "GoogleChrome/lighthouse/1755", "GoogleChrome/lighthouse/1786",
        "GoogleChrome/lighthouse/1895", "GoogleChrome/lighthouse/1916", "GoogleChrome/lighthouse/1941", "GoogleChrome/lighthouse/2016",
        "GoogleChrome/lighthouse/2610", "GoogleChrome/lighthouse/3442", "GoogleChrome/lighthouse/3606",
        "GoogleChrome/lighthouse/3692", "GoogleChrome/lighthouse/4036", "GoogleChrome/lighthouse/4301",
        "GoogleChrome/lighthouse/5011", "GoogleChrome/lighthouse/5791", "GoogleChrome/lighthouse/6922",
        "GoogleChrome/lighthouse/7210", "GoogleChrome/lighthouse/8940", "GoogleChrome/lighthouse/9151",
        "GoogleChrome/lighthouse/9451", "GoogleChrome/lighthouse/9727",

        "grommet/grommet/6227", "grommet/grommet/6239", "grommet/grommet/6282", "grommet/grommet/6293",
        "grommet/grommet/6307", "grommet/grommet/6350", "grommet/grommet/6490", "grommet/grommet/6722",

        "highlightjs/highlight.js/2684", "highlightjs/highlight.js/2703", "highlightjs/highlight.js/2704",
        "highlightjs/highlight.js/2727", "highlightjs/highlight.js/2750", "highlightjs/highlight.js/2765",
        "highlightjs/highlight.js/2785", "highlightjs/highlight.js/2811", "highlightjs/highlight.js/2897",
        "highlightjs/highlight.js/2899", "highlightjs/highlight.js/2927", "highlightjs/highlight.js/2932",
        "highlightjs/highlight.js/2958", "highlightjs/highlight.js/2969", "highlightjs/highlight.js/3000",
        "highlightjs/highlight.js/3070", "highlightjs/highlight.js/3154", "highlightjs/highlight.js/3203",
        "highlightjs/highlight.js/3212", "highlightjs/highlight.js/3249", "highlightjs/highlight.js/3278",
        "highlightjs/highlight.js/3312", "highlightjs/highlight.js/3316", "highlightjs/highlight.js/3367",
        "highlightjs/highlight.js/3381", "highlightjs/highlight.js/3411", "highlightjs/highlight.js/3438",
        "highlightjs/highlight.js/3457", "highlightjs/highlight.js/3516", "highlightjs/highlight.js/3559",
        "highlightjs/highlight.js/3644",

        "markedjs/marked/1262", "markedjs/marked/1435", "markedjs/marked/1535", "markedjs/marked/1674",
        "markedjs/marked/1825", "markedjs/marked/2483", "markedjs/marked/684",

        "openlayers/openlayers/10545", "openlayers/openlayers/10982", "openlayers/openlayers/11226",
        "openlayers/openlayers/11377", "openlayers/openlayers/11545", "openlayers/openlayers/12141",
        "openlayers/openlayers/12194", "openlayers/openlayers/12393", "openlayers/openlayers/12467",
        "openlayers/openlayers/12683", "openlayers/openlayers/13013", "openlayers/openlayers/13150",
        "openlayers/openlayers/13198", "openlayers/openlayers/13226", "openlayers/openlayers/13509",
        "openlayers/openlayers/13669", "openlayers/openlayers/13860", "openlayers/openlayers/13974",
        "openlayers/openlayers/13975", "openlayers/openlayers/13981", "openlayers/openlayers/14015",
        "openlayers/openlayers/14100", "openlayers/openlayers/14332", "openlayers/openlayers/14414",
        "openlayers/openlayers/14483", "openlayers/openlayers/14599", "openlayers/openlayers/14627",
        "openlayers/openlayers/14659", "openlayers/openlayers/14719", "openlayers/openlayers/15168",
        "openlayers/openlayers/15229", "openlayers/openlayers/15365", "openlayers/openlayers/15484",
        "openlayers/openlayers/15614", "openlayers/openlayers/15683", "openlayers/openlayers/15685", "openlayers/openlayers/15787",
        "openlayers/openlayers/15796", "openlayers/openlayers/7554", "openlayers/openlayers/9083",

        "prettier/prettier/14961", "prettier/prettier/16347", "prettier/prettier/4115",
        "prettier/prettier/4153", "prettier/prettier/4202", "prettier/prettier/6319", "prettier/prettier/8536",

        "PrismJS/prism/2295", "PrismJS/prism/2649", "PrismJS/prism/2678", "PrismJS/prism/2686", "PrismJS/prism/2705",
        "PrismJS/prism/2792", "PrismJS/prism/2841", "PrismJS/prism/2861", "PrismJS/prism/3001",
        "PrismJS/prism/3351", "PrismJS/prism/3355", "PrismJS/prism/3438",

        "processing/p5.js/3068", "processing/p5.js/3680", "processing/p5.js/3709", "processing/p5.js/5555",
        "processing/p5.js/5771", "processing/p5.js/5794", "processing/p5.js/5855", "processing/p5.js/5915",
        "processing/p5.js/5917", "processing/p5.js/5970", "processing/p5.js/6069", "processing/p5.js/6111",

        "quarto-dev/quarto-cli/1029", "quarto-dev/quarto-cli/1373", "quarto-dev/quarto-cli/2689",
        "quarto-dev/quarto-cli/4064", "quarto-dev/quarto-cli/4695", "quarto-dev/quarto-cli/4708",
        "quarto-dev/quarto-cli/4732", "quarto-dev/quarto-cli/5547", "quarto-dev/quarto-cli/896",

        "scratchfoundation/scratch-gui/5039", "scratchfoundation/scratch-gui/8492"
    ]

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
                if repo_name + '/' + new_repo_id in old_repo_list:
                    continue
                project_dirs = ['repo/' + repo_name + '/' + old_repo_id, 'repo/' + repo_name + '/' + new_repo_id]
                diff_dict = diff_parser.return_diff(project_dirs)
                generate_document_2(repo_name, old_repo_id, new_repo_id, diff_dict)
