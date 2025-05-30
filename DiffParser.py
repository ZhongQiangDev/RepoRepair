import os
import json
import filecmp
from tree_sitter import Language, Parser


class DiffParser:
    def __init__(self):
        """
        初始化时加载 JavaScript 和 TypeScript 的 tree-sitter 解析器。
        假定 build/my-languages.so 已构建好包含 javascript 和 typescript 语言。
        """
        self.JAVASCRIPT_LANGUAGE = Language('build/my-languages.so', 'javascript')
        self.TYPESCRIPT_LANGUAGE = Language('build/my-languages.so', 'typescript')
        self.parser = Parser()

    def diff_pair(self, old_dir, new_dir):
        """
        比较两个版本的项目目录，old_dir 为旧版本，new_dir 为新版。
        输出的 diff 结果为一个字典，结构如下：
            {
                "folder": [文件夹级别 diff]，  (新增前加 "+"，删除前加 "-")
                "file": [文件级别 diff]，      (仅针对 js/jsx/ts 文件，新文件前加 "+"，删除前加 "-")
                "class/function": [函数/类级别 diff]，
                      对于函数/类：0
                        + 前缀表示新增
                        - 前缀表示删除
                        无前缀表示同名但内容有修改（不记录具体 diff 内容）
            }
        所有路径均为相对于项目根目录的相对路径。
        """
        result = {"folder": [], "file": [], "class/function": []}

        # 分别遍历两个版本的目录，获得相对于项目根目录的文件夹和文件列表
        old_tree = self.get_tree(old_dir)
        new_tree = self.get_tree(new_dir)

        # 1. 文件夹级别 diff
        old_folders = old_tree['folders']
        new_folders = new_tree['folders']
        added_folders = new_folders - old_folders
        removed_folders = old_folders - new_folders

        for folder in sorted(added_folders):
            result["folder"].append("+" + folder)
        for folder in sorted(removed_folders):
            result["folder"].append("-" + folder)

        # 2. 文件级别 diff（仅支持 js/jsx/ts/tsx 文件）
        old_files = old_tree['files']
        new_files = new_tree['files']
        old_supported_files = {f for f in old_files if self.is_supported_file(f)}
        new_supported_files = {f for f in new_files if self.is_supported_file(f)}

        added_files = new_supported_files - old_supported_files
        removed_files = old_supported_files - new_supported_files

        for rel_path in sorted(added_files):
            result["file"].append("+" + rel_path)
        for rel_path in sorted(removed_files):
            result["file"].append("-" + rel_path)

        # 3. 函数/类级别 diff（仅针对 js/jsx/ts/tsx 文件）
        # 只对同时存在的支持类型文件进行比较
        common_files = old_supported_files.intersection(new_supported_files)
        for rel_path in sorted(common_files):
            old_file_path = os.path.join(old_dir, rel_path)
            new_file_path = os.path.join(new_dir, rel_path)
            if filecmp.cmp(old_file_path, new_file_path, shallow=False):
                continue
            else:
                result["file"].append(rel_path)

        # old_defs = self.extract_definitions(old_file_path)
        # new_defs = self.extract_definitions(new_file_path)
        # old_def_names = set(old_defs.keys())
        # new_def_names = set(new_defs.keys())
        #
        # # 新增的函数/类
        # for name in sorted(new_def_names - old_def_names):
        #     result["class/function"].append("+" + rel_path + "/" + name)
        # # 删除的函数/类
        # for name in sorted(old_def_names - new_def_names):
        #     result["class/function"].append("-" + rel_path + "/" + name)
        # # 对于同名但内容发生修改的（仅记录名称，无前缀）
        # for name in sorted(old_def_names.intersection(new_def_names)):
        #     if old_defs[name] != new_defs[name]:
        #         result["class/function"].append(rel_path + "/" + name)

        return result

    def diff_all(self, project_dirs):
        """
        对传入的多个项目目录（按时间顺序）进行连续比较，
        比较方式为依次比较 1 与 2，2 与 3，依此类推。
        每次比较的结果以一个键值对存放到一个字典中，键为 head，
        head 中记录了 repo 名称以及两个版本的标识（从路径中提取）。
        返回的总结果为：
            {
                head1: { "folder": [...], "file": [...], "class/function": [...] },
                head2: { ... },
                ...
            }
        """
        all_diff = {}
        for i in range(len(project_dirs) - 1):
            old_dir = project_dirs[i]
            new_dir = project_dirs[i + 1]
            diff_result = self.diff_pair(old_dir, new_dir)
            # 构造 head 信息：利用项目路径上一级目录作为 repo 名称，
            # 并结合各个版本目录的 basename 作为版本标识。
            repo_name_old = self.get_repo_name(old_dir)
            repo_name_new = self.get_repo_name(new_dir)
            version_old = os.path.basename(old_dir)
            version_new = os.path.basename(new_dir)
            # head 格式示例： "Chart.js: Chart.js-6bc47d3cea5ac0f4 -> Chart.js-6dbb7e74462d5b7d"
            head = f"{repo_name_old}: {version_old} -> {version_new}"
            all_diff[head] = diff_result
        return all_diff

    def return_diff(self, project_dirs):
        """
        对传入的多个项目目录计算连续比较的 diff 结果，
        并将所有结果保存到同一个 JSON 文件中。
        """
        all_diff = self.diff_all(project_dirs)
        try:
            return all_diff
        except Exception as e:
            print("Diff出错: {e}")
            return None

    def get_tree(self, root_dir):
        """
        遍历指定的 root_dir 目录，递归收集所有文件夹和文件，
        返回字典：{'folders': set(...), 'files': set(...)}，
        路径均为相对于 root_dir 的相对路径。
        """
        folders = set()
        files = set()
        for dirpath, dirnames, filenames in os.walk(root_dir):
            rel_dir = os.path.relpath(dirpath, root_dir)
            if rel_dir != '.':
                folders.add(rel_dir)
            for filename in filenames:
                rel_file = os.path.join(rel_dir, filename) if rel_dir != '.' else filename
                files.add(rel_file)
        return {"folders": folders, "files": files}

    def is_supported_file(self, file_path):
        """
        判断文件是否为支持的 js/jsx/ts 文件（file_path 为相对路径）。
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in ['.js', '.jsx', '.ts', '.tsx']

    def get_language_for_file(self, file_path):
        """
        根据文件扩展名返回对应的 tree-sitter 语言对象。
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.js', '.jsx']:
            return self.JAVASCRIPT_LANGUAGE
        elif ext in ['.ts', '.tsx']:
            return self.TYPESCRIPT_LANGUAGE
        else:
            return None

    def extract_definitions(self, file_path):
        """
        使用 tree-sitter 解析文件，提取其中的函数和类定义，
        返回字典：{ 函数/类名: 定义的源代码 } 。
        仅针对 js/jsx/ts/tsx 文件有效，不支持的文件返回空字典。
        """
        language = self.get_language_for_file(file_path)
        if language is None:
            return {}
        try:
            with open(file_path, 'rb') as f:
                source_code = f.read()
        except Exception:
            return {}
        self.parser.set_language(language)
        tree = self.parser.parse(source_code)
        root_node = tree.root_node
        definitions = self.extract_definitions_from_node(root_node, source_code)
        return definitions

    def extract_definitions_from_node(self, node, source_code):
        """
        递归遍历 tree-sitter 语法树，查找函数和类定义。
        支持的节点类型包括：
          - function_declaration（函数声明）：子节点 identifier 为函数名
          - class_declaration（类声明）：子节点 identifier 为类名
          - method_definition（方法定义）：子节点 property_identifier 或 identifier 为方法名
        返回字典：{ name: 源代码字符串 }。
        """
        definitions = {}
        if node.type in ["function_declaration", "class_declaration"]:
            for child in node.children:
                if child.type == "identifier":
                    try:
                        name = source_code[child.start_byte:child.end_byte].decode("utf8", errors="ignore")
                        code = source_code[node.start_byte:node.end_byte].decode("utf8", errors="ignore")
                        definitions[name] = code
                    except Exception:
                        continue
        elif node.type == "method_definition":
            for child in node.children:
                if child.type in ["property_identifier", "identifier"]:
                    try:
                        name = source_code[child.start_byte:child.end_byte].decode("utf8", errors="ignore")
                        code = source_code[node.start_byte:node.end_byte].decode("utf8", errors="ignore")
                        definitions[name] = code
                    except Exception:
                        continue
        # 递归遍历子节点
        for child in node.children:
            child_defs = self.extract_definitions_from_node(child, source_code)
            definitions.update(child_defs)
        return definitions

    def get_repo_name(self, dir_path):
        """
        简单从项目目录路径中提取 repo 名称。
        这里假设 dir_path 的上一级目录名称即为 repo 名称。
        例如： 'zip/chartjs/Chart.js/Chart.js-commitid' 则 repo 名称为 'Chart.js'
        """
        return os.path.basename(os.path.dirname(dir_path))


# ------------------------------
# 使用示例：
#
# 假设有多个版本的项目目录，按时间顺序排列，例如：
#
# project_dirs = [
#     'zip/chartjs/Chart.js/Chart.js-6bc47d3cea5ac0f496dc1b6bd53ed2fa5e1446d1',
#     'zip/chartjs/Chart.js/Chart.js-6dbb7e74462d5b7dedf2124a622a3e678964dd83',
#     'zip/chartjs/Chart.js/Chart.js-abcdef1234567890abcdef1234567890abcdef12'
# ]
#
# 调用方式如下，结果将存入 diff_result.json 文件中：
#
# diff_parser = DiffParser()
# diff_parser.save_diff_to_json(project_dirs, "diff_result.json")
#
# 输出的 JSON 文件内容类似于：
# {
#     "Chart.js: Chart.js-6bc47d3cea5ac0f496dc1b6bd53ed2fa5e1446d1 -> Chart.js-6dbb7e74462d5b7dedf2124a622a3e678964dd83": {
#         "folder": [...],
#         "file": [...],
#         "class/function": [
#             "+somefile.js/newFunction",
#             "-somefile.js/oldFunction",
#             "somefile.js/modifiedFunction"
#         ]
#     },
#     "Chart.js: Chart.js-6dbb7e74462d5b7dedf2124a622a3e678964dd83 -> Chart.js-abcdef1234567890abcdef1234567890abcdef12": {
#         ...
#     }
# }
# ------------------------------

if __name__ == "__main__":
    diff_parser = DiffParser()
    project_dirs = [
        'repo/prettier/prettier/4115',
        'repo/prettier/prettier/4153'
    ]
    print(diff_parser.return_diff(project_dirs))
