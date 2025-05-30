import os
import json
import time
from tqdm import tqdm
from tree_sitter import Language, Parser
import transformers

tokenizer = transformers.AutoTokenizer.from_pretrained('deepseek/', trust_remote_code=True)


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

        def find_call_function(node):
            functions = []
            if node.type == 'call_expression':
                for children in node.children:
                    if children.type == "identifier":
                        call_name = children.text.decode("utf8")
                        functions.append(call_name)
                        break
            for child in node.children:
                functions.extend(find_call_function(child))
            return functions

        return find_call_function(root_node)

    def parse_function(self, file_path, content):
        """
        Parses a JavaScript, JSX, or TypeScript file and returns its structure in JSON format.

        Parameters:
            file_path (str): The path to the file to parse.

        Returns:
            dict: The structure of the parsed file or an error message.
        """
        try:
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


if __name__ == '__main__':
    for repo_name in tqdm(os.listdir('repo')):
        for repo_name_sub in os.listdir('repo/' + repo_name):
            for repo_id in os.listdir('repo/' + repo_name + '/' + repo_name_sub):

                save_path = 'repo_doc_meta/' + repo_name + '/' + repo_name_sub + '/' + repo_id + '.jsonl'
                print(save_path)
                if not os.path.exists('repo_doc_meta/' + repo_name + '/' + repo_name_sub):
                    os.makedirs('repo_doc_meta/' + repo_name + '/' + repo_name_sub)
                if os.path.exists(save_path):
                    continue

                code_structure_file = 'code_structure/' + repo_name + '_' + repo_name_sub + '_' + repo_id + '.json'
                dependency_graph_file = 'dependency_graph/' + repo_name + '_' + repo_name_sub + '_' + repo_id + '.json'

                parser = CodeParser()

                import_info = {}
                with open(dependency_graph_file, 'r', encoding="utf-8") as f:
                    file_dependency = json.load(f)
                    dependencies = file_dependency['links']
                    for dependency in dependencies:
                        if dependency['source'] not in import_info.keys():
                            import_info[dependency['source']] = []
                            import_info[dependency['source']].append(dependency['target'])
                        else:
                            import_info[dependency['source']].append(dependency['target'])

                with open(code_structure_file, 'r', encoding='utf-8') as f:
                    code_structure = json.load(f)

                doc_meta = []
                for file_name in code_structure.keys():
                    if 'mermaid.min.js' in file_name or 'video.min.js' in file_name:
                        continue
                    file_meta = {'file_name': file_name, 'node_meta': []}
                    import_list = []
                    if file_name in import_info.keys():
                        import_list = import_info[file_name]
                    import_file_meta = {}
                    if len(import_list) > 0:
                        for imp in import_list:
                            if imp not in code_structure.keys():
                                continue
                            if imp not in import_file_meta.keys():
                                import_file_meta[imp] = []
                                for key in code_structure[imp].keys():
                                    import_file_meta[imp].append(code_structure[imp][key])
                            else:
                                for key in code_structure[imp].keys():
                                    import_file_meta[imp].append(code_structure[imp][key])

                    class_function_info = code_structure[file_name]
                    for node_name in class_function_info.keys():
                        if 'class' in node_name:
                            type = 'Class'
                        else:
                            type = 'Function'
                        name = class_function_info[node_name]['name']
                        content = class_function_info[node_name]['content']

                        try:
                            token_list = tokenizer.encode(content)
                            if len(token_list) > 50000:
                                # log += file_name + '-' + node_name + '\n'
                                continue
                        except:
                            continue

                        call_functions = parser.parse_function(file_name, content)
                        import_functions = []
                        for call in call_functions:
                            for imp in import_file_meta.keys():
                                for function in import_file_meta[imp]:
                                    # Class
                                    if 'functions' in function.keys():
                                        for f in function['functions']:
                                            if call == f['name']:
                                                import_functions.append({'file': imp, 'function': f})
                                    # Function
                                    else:
                                        if call == function['name']:
                                            import_functions.append({'file': imp, 'function': function})
                        node_meta = {'type': type, 'class_or_function': class_function_info[node_name], 'import': import_functions}
                        file_meta['node_meta'].append(node_meta)
                    doc_meta.append(file_meta)

                with open(save_path, 'w', encoding='UTF-8') as f:
                    for doc in doc_meta:
                        f.write(json.dumps(doc) + "\n")
