# Kotemari  Kotemari: Your Codebase Companion for LLMs <0xF0><0x9F><0xA6><0xB1>✨

[![PyPI version](https://badge.fury.io/py/kotemari.svg)](https://badge.fury.io/py/kotemari) <!-- Add badges for tests, coverage, license later -->

**Kotemari is a Python library and CLI tool designed to analyze your codebase, understand dependencies, and generate accurate, context-rich prompts for Large Language Models (LLMs).** Spend less time manually gathering code snippets and more time getting results! <0xF0><0x9F><0xA4><0xAF>

It simplifies the process of Retrieval-Augmented Generation (RAG) for coding tasks by automatically providing the necessary context based on your project's structure and dependencies.

## <0xF0><0x9F><0x9A><0x80> Key Features

*   **<0xF0><0x9F><0x94><0x8D> Project Analysis (`analyze`):** Scans your project, respecting `.gitignore` and `.kotemari.yml` configurations, providing a summary of files.
*   **<0xF0><0x9F><0x93><0x82> File Listing (`list`):** Lists all relevant files in your project (ignores applied).
*   **<0xF0><0x9F><0xAA><0xB3> Directory Tree (`tree`):** Displays a clean tree structure of your project files (ignores applied).
*   **<0xF0><0x9F><0xAA><0xB2> Dependency Mapping (`dependencies`):** Analyzes Python imports to show dependencies for a specific file (identifies internal/external modules - *Note: Internal detection under refinement*).
*   **<0xE2><0x9C><0xA8> Context Generation (`context`):** Automatically gathers the content of specified files *and* their relevant dependencies to create a comprehensive context string, perfect for feeding into an LLM.
*   **<0xF0><0x9F><0x92><0xBE> Caching:** Speeds up subsequent analyses by caching project structure information.
*   **<0xF0><0x9F><0x91><0x80> File Watching (`watch` - *Experimental*):** Monitors file changes and can automatically update analysis or clear cache (useful for development workflows).

## <0xF0><0x9F><0x9A><0x80> Why Kotemari?

*   **<0xE2><0x9C><0x85> Effortless Context:** Stop manually copy-pasting code! Kotemari does the heavy lifting of finding relevant files and dependencies.
*   **<0xF0><0x9F><0xA7><0xAE> Accurate Prompts:** Provides LLMs with the *right* context, leading to better code generation, explanations, and debugging assistance.
*   **<0xF0><0x9F><0xA7><0xAD> Streamlined Workflow:** Integrates smoothly into your development process via a simple CLI.
*   **<0xF0><0x9F><0xAA><0xA1> Configurable:** Fine-tune analysis using `.gitignore` and an optional `.kotemari.yml` file.

## <0xE2><0x9A><0x99><0xEF><0xB8><0x8F> Installation

Get Kotemari easily using pip:

```bash
pip install kotemari
```

## <0xF0><0x9F><0x92><0xBB> Basic Usage (CLI)

Navigate to your project's root directory and use the `kotemari` command:

```bash
# Analyze the project (uses cache by default)
kotemari analyze

# List relevant files
kotemari list .

# Show the project tree
kotemari tree .

# Show dependencies for a specific file
kotemari dependencies src/my_module/main.py

# Generate context for a file (includes its dependencies)
kotemari context src/my_module/main.py

# Generate context for multiple files
kotemari context src/my_module/main.py src/my_module/utils.py

# Analyze without using the cache
kotemari analyze --no-use-cache 
```

For more options, use `kotemari --help` or `kotemari [COMMAND] --help`.

## <0xF0><0x9F><0x92><0xBB> Library Usage (Python)

You can also use Kotemari directly within your Python scripts:

```python
from pathlib import Path
from kotemari import Kotemari

# Initialize with the project root directory
project_path = Path("/path/to/your/project")
kotemari = Kotemari(project_root=project_path, use_cache=True)

# 1. Analyze the project (required before most other operations)
try:
    analyzed_files = kotemari.analyze_project()
    print(f"Analyzed {len(analyzed_files)} files.")
except Exception as e: # Catch KotemariError or its subclasses
    print(f"Error during analysis: {e}")
    exit()

# 2. List analyzed files
try:
    file_list = kotemari.list_files(relative=True)
    print("\nAnalyzed Files:")
    for f in file_list:
        print(f"- {f}")
except Exception as e: # e.g., AnalysisError if analyze wasn't called
    print(f"Error listing files: {e}")

# 3. Get dependencies for a specific file
try:
    dependencies = kotemari.get_dependencies("src/module/my_file.py")
    print("\nDependencies for src/module/my_file.py:")
    for dep in dependencies:
        print(f"- {dep.module_name} ({dep.dependency_type.name})")
except Exception as e: # e.g., FileNotFoundErrorInAnalysis
    print(f"Error getting dependencies: {e}")

# 4. Generate context for a file (includes dependencies)
try:
    context = kotemari.get_context(["src/module/my_file.py"])
    print("\nGenerated Context:")
    print("-"*20)
    print(context)
    print("-"*20)
except Exception as e: # e.g., FileNotFoundErrorInAnalysis, ContextGenerationError
    print(f"Error generating context: {e}")

# You can also get the tree structure (less common for library usage)
# try:
#     tree_str = kotemari.get_tree()
#     print("\nProject Tree:")
#     print(tree_str)
# except Exception as e:
#     print(f"Error getting tree: {e}")

```

## <0xF0><0x9F><0x92><0xBB> Requirements

*   **Python:** 3.9 or higher
*   **Operating System:** OS Independent (Tested on Windows, Linux, macOS)

## <0xF0><0x9F><0x93><0x9C> License

This project is licensed under the **MIT License**. See the `LICENSE` file (to be created) for details.

## <0xF0><0x9F><0xAA><0xA1> Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request.

*(More detailed contribution guidelines to come.)*

---

Happy coding with Kotemari! <0xF0><0x9F><0xA6><0xB1>
