# RepoRepair

RepoRepair is a novel **language-agnostic** approach for repository-level bug fixing, leveraging LLM-generated code documentation to achieve precise fault localization and cost-effective repairs. Evaluated on SWE-bench Multimodal, it
outperforms state-of-the-art tools by **10% accuracy** while reducing costs to **\$0.21 per repair**.

## Key Features

- 🧠 **Hierarchical Localization**:  
  Combines file-level localization (49.8% accuracy) with function-level verification
- 📚 **Documentation-Aware**:  
  Uses LLM-generated code documentation for cross-file context understanding
- 💰 **Cost-Efficient**:  
  82.3% fewer tokens than non-retrieval baselines (23.5M vs 132.6M)
- 🌐 **Multimodal Ready**:  
  Processes visual issue descriptions (screenshots/GIFs) via QWen2.5-VL

## Performance Highlights

| Metric               | RepoRepair | Agentless Lite | Improvement |
|----------------------|------------|----------------|-------------|
| %Resolved            | 36.18%     | 26.1%          | +10%        |
| Avg. Cost/Repair     | \$0.21     | \$0.34         | 38% cheaper |
| Correct Localization | 49.8%      | 30.4%          | +19.4%      |

## Installation

```bash
git clone https://github.com/ZhongQiangDev/RepoRepair.git
cd RepoRepair
pip install -r requirements.txt  # Requires Python 3.9+
```

## Usage

### 1. Resource Download

```bash
# Download issues and repositories
python issue_diff_download.py

python issue_repo_download.py
python unzip.py

# Process visual data
python issue_ps_pic_download.py
python gif_slice.py  # Uses scikit-image for keyframe extraction
```

* Use **Selenium** to fetch the repository's compressed file from Github.
* Use **scikit-image** to extract key frames from dynamic images (.gif).

### 2. Repository Parsing

```bash
# Parse code and analyze dependencies
python CodeParser.py  # Uses Tree-sitter for JS/TS parsing
python DependencyGraph.py
python generate_doc_meta.py  # Output: repo_doc_meta/
```

### 3. Code Documentation Generation
```bash
# Generate documentation at different levels
python generate_document_func.py  # Output: repo_document_func/

python generate_document_file.py  # Output: repo_document_file/
```

* Cloud resources will be released post-publication.

### 4. File Retrieval
```bash
# Analyze and retrieve relevant files
python ps_cause_analyze.py  # Output: problem_statement_analysis/

python file_retrival.py  # Uses LangChain, output: repo_file_rag/
```

### 5. Localization
```bash
# Hierarchical localization
python file_localization.py  # Output: buggy_files/

python func_localization.py  # Output: buggy_elements/
```


### 6. Repair
```bash
# Generate patches
python bug_repair.py  # Output: bug_repair/
```

## Directory Structure

```angular2html
├── repo_doc_meta/            # Parsed repository metadata
├── repo_document_func/       # Function-level documentation
├── repo_document_file/       # File-level documentation
├── problem_statement_analysis/ # Issue analysis results
├── repo_file_rag/            # Retrieved files
├── buggy_files/              # Localized problematic files  
├── buggy_elements/           # Localized functions/classes
└── bug_repair/               # Generated patches
```