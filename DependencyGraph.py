import os
import json
import networkx as nx
from tree_sitter import Language, Parser
from pyvis.network import Network
import matplotlib.pyplot as plt
from tqdm import tqdm


class DependencyGraph:
    def __init__(self):
        """
        Initializes the parser with JavaScript and TypeScript languages.
        """
        self.JAVASCRIPT_LANGUAGE = Language('build/my-languages.so', 'javascript')
        self.TYPESCRIPT_LANGUAGE = Language('build/my-languages.so', 'typescript')
        self.parser = Parser()

    def extract_imports(self, file_content, language):
        """
        Extracts import statements from the file content.

        Parameters:
            file_content (str): The content of the file to parse.
            language (Language): The Tree-sitter language instance.

        Returns:
            list: A list of imported module/file names.
        """
        self.parser.set_language(language)
        tree = self.parser.parse(bytes(file_content, "utf8"))
        root_node = tree.root_node
        imports = []

        def traverse(node):
            if node.type == "import_statement":
                import_path_node = node.child_by_field_name("source")
                if import_path_node:
                    import_path = import_path_node.text.decode("utf8").strip("\"'")
                    imports.append(import_path)
            for child in node.children:
                traverse(child)

        traverse(root_node)
        return imports

    def parse_project(self, root_dir):
        """
        Parses all JavaScript, JSX, and TypeScript files in a directory to build import relationships.

        Parameters:
            root_dir (str): The root directory containing the project files.

        Returns:
            nx.DiGraph: A directed graph representing the import relationships.
        """
        graph = nx.DiGraph()

        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                if 'test' in dirpath:
                    continue
                if filename.endswith((".js", ".jsx", ".ts", ".tsx")):
                    file_path = os.path.join(dirpath, filename)
                    with open(file_path, "r", encoding="utf8") as file:
                        content = file.read()

                    # Determine language
                    if filename.endswith((".js", ".jsx")):
                        language = self.JAVASCRIPT_LANGUAGE
                    elif filename.endswith((".ts", ".tsx")):
                        language = self.TYPESCRIPT_LANGUAGE

                    # Extract imports
                    imports = self.extract_imports(content, language)

                    # Add edges for imports
                    graph.add_node(file_path, type="file")
                    for imp in imports:
                        _, ext = os.path.splitext(imp)
                        if ext:
                            if ext not in ['.js', '.jsx', '.ts', '.tsx']:
                                continue
                        else:
                            _, file_type = os.path.splitext(file_path)
                            imp += file_type

                        if imp.startswith("./"):
                            imp = os.path.join(dirpath, imp[2:])
                        elif imp.startswith("../"):
                            imp_path = dirpath
                            while imp.startswith("../"):
                                imp_path = os.path.dirname(imp_path)
                                imp = imp[3:]
                            imp = os.path.join(imp_path, imp)
                        graph.add_edge(file_path, imp, type="import")

        return graph

    def save_graph(self, graph, output_path):
        """
        Saves the graph to a JSON file.

        Parameters:
            graph (nx.DiGraph): The directed graph.
            output_path (str): The path to save the graph.
        """
        data = nx.readwrite.json_graph.node_link_data(graph)
        with open(output_path, "w", encoding="utf8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

    def visualize_graph_static(self, graph, output_image_path):
        """
        Visualizes the dependency graph as a static image.
        """
        plt.figure(figsize=(14, 10))
        pos = nx.spring_layout(graph, seed=42)  # Consistent layout
        nx.draw(
            graph, pos,
            with_labels=True,
            node_color="lightblue",
            edge_color="gray",
            node_size=2000,
            font_size=10,
            alpha=0.8,
            arrowsize=15
        )
        plt.title("File Dependency Graph", fontsize=16)
        plt.savefig(output_image_path)
        plt.show()
        print(f"Static graph saved as {output_image_path}")

    def visualize_graph_interactive(self, graph, output_html_path):
        """
        Visualizes the dependency graph as an interactive HTML file.
        """
        net = Network(notebook=False, height="750px", width="100%", directed=True)

        for node, attrs in graph.nodes(data=True):
            net.add_node(node, title=attrs.get('type', 'File'), label=node)

        for u, v, attrs in graph.edges(data=True):
            edge_type = attrs.get("type", "Edge")
            net.add_edge(u, v, title=edge_type)

        net.save_graph(output_html_path)
        print(f"Interactive graph saved as {output_html_path}")


if __name__ == "__main__":
    for repo_name in tqdm(os.listdir('repo')):
        for repo_name_sub in os.listdir('repo/' + repo_name):
            for repo_id in os.listdir('repo/' + repo_name + '/' + repo_name_sub):
                root_directory = "repo/" + repo_name + '/' + repo_name_sub + '/' + repo_id
                output_path = 'dependency_graph/' + repo_name.replace('/', '_') + '_' + repo_name_sub.replace('/', '_') + '_' + repo_id + '.json'
                if os.path.exists(output_path):
                    continue
                parser = DependencyGraph()
                dependency_graph = parser.parse_project(root_directory)

                parser.save_graph(dependency_graph, output_path)
