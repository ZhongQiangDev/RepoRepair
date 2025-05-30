import os
import json
import math
import time
from openai import OpenAI
import pyarrow.parquet as pq
from PIL import Image
import base64
from dashscope import get_tokenizer
import tiktoken

os.environ["OPENAI_API_KEY"] = "your-key"
os.environ["OPENAI_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"

tokenizer = get_tokenizer('qwen-turbo')


def qwen_chat(prompt, images, root):
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
            model="qwen-vl-max-0125",
            temperature=0,
            presence_penalty=0,
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


reason_analyse_instruction = '''
Please look through the following GitHub problem description with images or videos, and then find all causes for the problem.

### GitHub Problem Description ###
{problem_statement}

###

Now you need to follow these steps to answer:
1. Identify all wrong behaviors that you think need to be fixed
2. Analyze the causes behind the wrong behaviors above

The standard format of the answer is as follows:\n\n
### Answer 1
**Wrong Behavior**: ...
**Cause**: ...

### Answer 2
...

...

### Answer N
...

### Conclusion
**Summary**: An overall summary of each answer above
'''


if __name__ == '__main__':
    parquet_file1 = pq.ParquetFile('SWE-bench_M/dev-00000-of-00001.parquet')
    data1 = parquet_file1.read().to_pandas()
    parquet_file2 = pq.ParquetFile('SWE-bench_M/test-00000-of-00001.parquet')
    data2 = parquet_file2.read().to_pandas()

    data_dict = {}
    length = len(data1['problem_statement'])
    for i in range(length):
        data_dict[str(data1['repo'][i]) + '/' + str(data1['instance_id'][i]).split('-')[-1]] = {'problem_statement': str(data1['problem_statement'][i]), 'image_assets': list(data1['image_assets'][i])}
    length = len(data2['problem_statement'])
    for i in range(length):
        data_dict[str(data2['repo'][i]) + '/' + str(data2['instance_id'][i]).split('-')[-1]] = {'problem_statement': str(data2['problem_statement'][i]), 'image_assets': list(data2['image_assets'][i])}
    prompt_token_count = 0
    completion_token_count = 0

    for repo in os.listdir('repo'):
        for repo_sub in os.listdir('repo/' + repo):
            repo_name = repo + '/' + repo_sub

            for repo_id in os.listdir('repo/' + repo_name):
                repo = repo_name + '/' + repo_id
                root = 'pic/' + repo_name + '/' + str(repo_id)

                # GitHub Problem Description
                problem_statement = data_dict[repo]['problem_statement']
                image_assets = data_dict[repo]['image_assets']

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

                prompt = reason_analyse_instruction.format(problem_statement=problem_statement)

                if not os.path.exists('problem_statement_analysis/' + repo_name):
                    os.makedirs('problem_statement_analysis/' + repo_name)
                if os.path.exists('problem_statement_analysis/' + repo_name + '/' + str(repo_id) + '.txt'):
                    continue
                max_try = 3
                while max_try > 0:
                    generated_text, prompt_tokens, completion_tokens, total_tokens = qwen_chat(prompt, image_assets, root='pic/' + repo_name + '/' + str(repo_id))
                    if generated_text is not None:
                        if generated_text == 'ERROR':
                            max_try -= 1
                        else:
                            max_try = 0
                            prompt_token_count += prompt_tokens
                            completion_token_count += completion_tokens
                            print("Number of prompt tokens is " + str(prompt_tokens))
                            print("Number of completion tokens is " + str(completion_tokens))
                            with open('problem_statement_analysis/' + repo_name + '/' + str(repo_id) + '.txt', 'w', encoding='UTF-8') as f:
                                f.write(generated_text)
                                print('problem_statement_analysis/' + repo_name + '/' + str(repo_id) + '.txt is \033[92msuccessfully\033[0m generated')
                    else:
                        max_try -= 1
                    time.sleep(10)

    print("Total number of prompt tokens is " + str(prompt_token_count))
    print("Total number of completion tokens is " + str(completion_token_count))