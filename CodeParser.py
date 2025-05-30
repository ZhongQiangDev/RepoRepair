import os
import json
from tqdm import tqdm
from tree_sitter import Language, Parser


class CodeParser:
    def __init__(self):
        """
        Initializes the parser with JavaScript and TypeScript languages.
        """
        # Load the compiled languages
        self.JAVASCRIPT_LANGUAGE = Language('build/my-languages.so', 'javascript')
        self.TYPESCRIPT_LANGUAGE = Language('build/my-languages.so', 'typescript')
        self.parser = Parser()

    def extract_code_structure(self, file_content, language):
        """
        Extracts class, function, and type alias information from the code using Tree-sitter.

        Parameters:
            file_content (str): The content of the file to parse.
            language (Language): The Tree-sitter language instance (JavaScript or TypeScript).

        Returns:
            dict: A dictionary representing the structure of the code.
        """
        self.parser.set_language(language)
        tree = self.parser.parse(bytes(file_content, "utf8"))
        root_node = tree.root_node

        def get_previous_comments(node, lines):
            """
            Extracts all relevant comments preceding a node, including multi-line and consecutive blocks.

            Parameters:
                node (Node): The Tree-sitter node to check for preceding comments.
                lines (list): The list of lines in the file content.

            Returns:
                str: The comments preceding the node, if any.
            """
            start_line = node.start_point[0]
            comments = []
            for i in range(start_line - 1, -1, -1):  # Traverse lines backward
                line = lines[i].strip()
                if line.startswith("//") or line.startswith("/*") or line.startswith("*"):
                    comments.append(line)
                elif line == "":  # Allow empty lines between comments
                    if comments:  # Stop if we already found comments and hit another empty line
                        break
                else:  # Stop at the first non-comment line
                    break
            return "\n".join(reversed(comments)) if comments else None

        def has_return_statement(node):
            if node.type == 'return_statement':
                return True
            for child in node.children:
                if has_return_statement(child):
                    return True
            return False

        def traverse(node, lines, current_class=None, counters=None):
            """
            Recursively traverses the AST to extract code structure.

            Parameters:
                node (Node): The current AST node to process.
                lines (list): The list of lines in the file content.
                current_class (dict): The current class context, if any.
                counters (dict): A dictionary to store counters for classes and functions.

            Returns:
                dict: A dictionary representing the structure of the current node.
            """
            if counters is None:
                counters = {"class_counter": 0, "function_counter": 0}

            result = {}

            # For classes
            if node.type == "class_declaration":
                class_name_node = node.child_by_field_name("name")
                class_name = class_name_node.text.decode("utf8") if class_name_node else f"class_{counters['class_counter'] + 1}"
                signature = get_previous_comments(node, lines) or ""
                content = "\n".join(lines[node.start_point[0]:node.end_point[0] + 1])
                class_info = {
                    "signature": signature,
                    "content": content,
                    "name": class_name,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "return": False,
                    "functions": []
                }
                result[f'class_{counters["class_counter"] + 1}'] = class_info
                current_class = class_info
                counters["class_counter"] += 1

            # For functions (including method declarations, arrow functions, and TypeScript-specific declarations)
            elif node.type in ["function_declaration", "arrow_function", "method_definition", "type_alias_declaration", "function_expression"]:
                func_name_node = node.child_by_field_name("name")
                func_name = func_name_node.text.decode("utf8") if func_name_node else f"function_{counters['function_counter'] + 1}"
                params = []
                params_node = node.child_by_field_name("parameters")
                if params_node:
                    for param in params_node.children:
                        if param.type == "identifier":  # Only extract valid identifiers
                            param_name = param.text.decode("utf8")
                            params.append(param_name)

                signature = get_previous_comments(node, lines) or ""
                content = "\n".join(lines[node.start_point[0]:node.end_point[0] + 1])
                func_info = {
                    "signature": signature,
                    "content": content,
                    "name": func_name,
                    "parameters": params,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "return": has_return_statement(node)
                }
                if current_class:
                    current_class["functions"].append(func_info)
                else:
                    counters["function_counter"] += 1
                    result[f'function_{counters["function_counter"]}'] = func_info

            # For TypeScript-specific declarations like interfaces
            elif node.type in ["interface_declaration", "type_alias_declaration"]:
                type_name_node = node.child_by_field_name("name")
                type_name = type_name_node.text.decode("utf8") if type_name_node else f"type_{counters['class_counter'] + 1}"
                signature = get_previous_comments(node, lines) or ""
                content = "\n".join(lines[node.start_point[0]:node.end_point[0] + 1])
                type_info = {
                    "signature": signature,
                    "content": content,
                    "name": type_name,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "return": has_return_statement(node)
                }
                result[f'type_{counters["class_counter"] + 1}'] = type_info

            # Recursively process children
            for child in node.children:
                result.update(traverse(child, lines, current_class, counters))
            return result

        lines = file_content.splitlines()
        return traverse(root_node, lines)

    def parse_file(self, file_path):
        """
        Parses a JavaScript, JSX, or TypeScript file and returns its structure in JSON format.

        Parameters:
            file_path (str): The path to the file to parse.

        Returns:
            dict: The structure of the parsed file or an error message.
        """
        try:
            with open(file_path, "r", encoding="utf8") as file:
                content = file.read()

            # Determine the language based on file extension
            if file_path.endswith((".js", ".jsx")):
                language = self.JAVASCRIPT_LANGUAGE
            elif file_path.endswith((".ts", ".tsx")):
                language = self.TYPESCRIPT_LANGUAGE
            else:
                return {"error": "Unsupported file extension."}

            # Extract structure
            structure = self.extract_code_structure(content, language)
            return structure
        except Exception as e:
            return {"error": str(e)}


def delete_overlap_function(dictionary):
    lineno_list = [0] * 10000000
    new_dictionary = {}
    for key in dictionary.keys():
        flag = False
        if key.startswith("function"):
            start = dictionary[key]['start_line']
            end = dictionary[key]['end_line']
            for i in range(start, end + 1):
                if lineno_list[i] == 0:
                    lineno_list[i] = 1
                else:
                    flag = True
                    break
        if flag is False:
            new_dictionary[key] = dictionary[key]
    return new_dictionary


# Example Usage
if __name__ == "__main__":
    for repo_name in tqdm(os.listdir('repo')):
        for repo_name_sub in os.listdir('repo/' + repo_name):
            for repo_id in os.listdir('repo/' + repo_name + '/' + repo_name_sub):
                parser = CodeParser()
                result = {}
                output_path = 'code_structure/' + repo_name.replace('/', '_') + '_' + repo_name_sub.replace('/', '_') + '_' + repo_id + '.json'
                if os.path.exists(output_path):
                    continue
                repo_path = "repo/" + repo_name + '/' + repo_name_sub + '/' + repo_id
                print(repo_path)
                js_ts_files = []
                for root, dirs, files in os.walk(repo_path):
                    if 'test' in root:
                        continue
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        if file_path.split('.')[-1] in ['js', 'jsx', 'ts', 'tsx']:
                            if file_path.endswith('min.js'):
                                if file_path.replace('min.', '') in js_ts_files:
                                    continue
                            js_ts_files.append(file_path)
                for file in js_ts_files:
                    result[file] = delete_overlap_function(parser.parse_file(file))
                with open(output_path, "w", encoding="utf8") as output_file:
                    json.dump(result, output_file, ensure_ascii=False, indent=4)
                print(f"Code structure has been saved to {output_path}")
