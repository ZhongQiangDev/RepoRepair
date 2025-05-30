import os
from langchain.schema import Document
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


class FilenameInsertTextLoader(TextLoader):
    """自定义 TextLoader，在文件内容开头插入文件名"""

    def load(self) -> list[Document]:
        docs = super().load()
        for doc in docs:
            filepath = doc.metadata["source"]
            filename = os.path.basename(filepath)
            filename = filename.replace(".txt", "")
            filename = '/'.join(filename.split('_')[3:])
            doc.page_content = f"Filename: {filename}\n\n{doc.page_content}"
            # # 可选：在 metadata 中也记录文件名（便于后续检索）
            # doc.metadata["filename"] = filename
        return docs


def load_files_from_directory(directory_path):
    """从目录中加载所有文本文件"""
    text_loader_kwargs = {"autodetect_encoding": True}
    loader = DirectoryLoader(directory_path, glob="**/*.txt", loader_cls=FilenameInsertTextLoader, loader_kwargs=text_loader_kwargs)
    documents = loader.load()
    return documents


def split_documents(documents, chunk_size=500, chunk_overlap=50):
    """将文档分割成较小的块"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    texts = text_splitter.split_documents(documents)
    return texts


def build_vector_index(texts):
    """使用嵌入模型生成向量并构建 FAISS 索引"""
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2", cache_folder='./models', show_progress=True)
    vectorstore = FAISS.from_documents(texts, embeddings)
    return vectorstore


def retrieve_top_files(vectorstore, query, top_k):
    """根据查询检索相似度最高的 Top K 文件"""
    retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
    results = retriever.invoke(query)
    return results


if __name__ == '__main__':
    for repo in os.listdir('repo'):
        for repo_sub in os.listdir('repo/' + repo):
            repo_name = repo + '/' + repo_sub
            for repo_id in os.listdir('repo/' + repo_name):
                if not os.path.exists('repo_file_rag/' + repo_name):
                    os.makedirs('repo_file_rag/' + repo_name)
                if os.path.exists('repo_file_rag/' + repo_name + '/' + repo_id + '.txt'):
                    continue
                doc_file_path = "repo_document_file/" + repo_name + '/' + repo_id
                if not os.path.exists("repo_document_file/" + repo_name + '/' + repo_id):
                    continue
                documents = load_files_from_directory(doc_file_path)
                texts = split_documents(documents)
                vectorstore = build_vector_index(texts)
                query_list = []
                with open('problem_statement_analysis/' + repo_name + '/' + repo_id + '.txt', 'r', encoding='UTF-8') as f:
                    for line in f.readlines():
                        if line.startswith('**Cause**'):
                            query_list.append(line.replace('**Cause**:', '').strip())
                        if line.startswith('**Wrong Behavior**'):
                            query_list.append(line.replace('**Wrong Behavior**:', '').strip())
                        if line.startswith('**Summary**'):
                            query_list.append(line.replace('**Summary**:', '').strip())
                top_files_result = set()
                for query in query_list:
                    top_files = retrieve_top_files(vectorstore, query.strip(), top_k=50)
                    for i, doc in enumerate(top_files):
                        top_files_result.add(doc.metadata['source'])
                with open('repo_file_rag/' + repo_name + '/' + repo_id + '.txt', 'w', encoding='UTF-8') as f:
                    for top_file in top_files_result:
                        f.write(top_file + '\n')
                print('repo_file_rag/' + repo_name + '/' + repo_id + '.txt is \033[92msuccessfully\033[0m generated')
