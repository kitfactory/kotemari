# Kotemari 🪄

[![PyPI version](https://img.shields.io/pypi/v/kotemari.svg?style=flat-square)](https://pypi.python.org/pypi/kotemari) 
[![Build Status](https://img.shields.io/github/actions/workflow/status/<YOUR_GITHUB_USERNAME>/kotemari/ci.yml?branch=main&style=flat-square)](https://github.com/<YOUR_GITHUB_USERNAME>/kotemari/actions)
[![Code Coverage](https://img.shields.io/codecov/c/github/<YOUR_GITHUB_USERNAME>/kotemari?style=flat-square)](https://codecov.io/gh/<YOUR_GITHUB_USERNAME>/kotemari)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

Kotemari is a Python library designed to analyze your Python project structure, understand dependencies, and intelligently generate context for Large Language Models (LLMs) like GPT. 🧠 Its core purpose is to be integrated into other development tools (like IDE extensions, analysis scripts, or chat interfaces) to provide on-demand project insights and context. It also features real-time file monitoring to keep the analysis up-to-date effortlessly! ✨

## 🤔 Why Kotemari?

Integrating project understanding capabilities into tools or automating context generation for LLMs can be complex. Kotemari simplifies this by providing a robust Python API that:

*   **🎯 Delivers Smart Context:** Generate concise context strings including only necessary files and their dependencies via simple API calls.
*   **🔄 Stays Up-to-Date:** Offers background file monitoring and automatic cache/dependency updates, ensuring the information provided by the API is current.
*   **🔍 Provides Deep Insight:** Exposes methods to access detailed dependency information (direct and reverse) derived from analyzing Python `import` statements.
*   **⚙️ Offers Flexibility:** Easily configurable through Python arguments or an optional `.kotemari.yml` file, respecting `.gitignore` rules.
*   **🧩 Enables Integration:** Designed to be easily embedded into your custom Python applications and development workflows.

Kotemari empowers your tools by providing sophisticated project analysis capabilities through a **simple and effective Python API**. 🎉

## 🚀 Installation

Kotemari is currently under development. To install the development version:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/<YOUR_GITHUB_USERNAME>/kotemari.git
    cd kotemari
    ```
2.  **Create a virtual environment:**
    ```bash
    # Using venv
    python -m venv .venv
    source .venv/bin/activate # On Windows use `.venv\Scripts\activate`

    # Or using uv (recommended)
    uv venv
    source .venv/bin/activate # On Windows use `.venv\Scripts\activate`
    ```
3.  **Install the package in editable mode:**
    ```bash
    # Using pip
    pip install -e .[dev]

    # Or using uv
    uv pip install -e .[dev]
    ```

*(Once released, installation will be as simple as `pip install kotemari`)*

## ✨ Usage (Python API)

Using Kotemari in your Python code is straightforward:

```python
import logging
from pathlib import Path
from kotemari import Kotemari

# Optional: Configure logging to see Kotemari's internal activity
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')

# 1. Initialize Kotemari with your project's root directory
project_path = Path("./your/project/path") # <-- Change this!
kotemari = Kotemari(project_path)

# 2. Analyze the project (builds initial cache and dependency graph)
print("Analyzing project...")
kotemari.analyze_project()
print("Analysis complete!")

# 3. Get a list of analyzed files (FileInfo objects)
print("\nAnalyzed Files:")
all_files = kotemari.list_files()
for file_info in all_files[:5]: # Print first 5 for brevity
    print(f"- {file_info.path.relative_to(project_path)} (Hash: {file_info.hash[:7]}...)")

# 4. Get dependencies of a specific file
target_file = project_path / "src/module_a.py" # Example
print(f"\nDependencies of {target_file.name}:")
try:
    dependencies = kotemari.get_dependencies(target_file)
    if dependencies:
        for dep_path in dependencies:
            print(f"- {dep_path.relative_to(project_path)}")
    else:
        print("- No direct dependencies found.")
except FileNotFoundError:
    print(f"- File {target_file.name} not found in analysis results.")

# 5. Get files that depend ON a specific file (reverse dependencies)
dependent_on_file = project_path / "src/utils.py" # Example
print(f"\nFiles depending on {dependent_on_file.name}:")
try:
    reverse_deps = kotemari.get_reverse_dependencies(dependent_on_file)
    if reverse_deps:
        for rev_dep_path in reverse_deps:
            print(f"- {rev_dep_path.relative_to(project_path)}")
    else:
        print("- No files directly depend on this.")
except FileNotFoundError:
    print(f"- File {dependent_on_file.name} not found in analysis results.")

# 6. Generate formatted context for LLM (target file + dependencies)
context_file = project_path / "src/main_logic.py" # Example
print(f"\nGenerating context for {context_file.name}:")
try:
    context_string = kotemari.get_context(context_file)
    print("--- Context Start ---")
    print(context_string[:500] + "... (truncated)") # Print start for brevity
    print("--- Context End ---")
except FileNotFoundError:
    print(f"- File {context_file.name} not found.")
except Exception as e:
    print(f"An error occurred: {e}")

# 7. Optional: Start background file watching for real-time updates
# Kotemari will automatically update its internal state when files change.
print("\nStarting file watcher (runs in background)...")
kotemari.start_watching() 

# --- Your application logic here --- 
# You can now query kotemari methods (list_files, get_dependencies, etc.) 
# and get up-to-date results reflecting any file changes.

print("Watcher is running. Modify project files to see updates (check logs if INFO enabled).")
input("Press Enter to stop watching and exit...\n")

print("Stopping watcher...")
kotemari.stop_watching()
print("Watcher stopped.")

```

### Key API Methods:

*   **`Kotemari(project_root, config_path=None, use_cache=True, log_level=logging.WARNING)`:** Initialize the analyzer.
*   **`analyze_project()`:** Performs the initial full analysis.
*   **`list_files()`:** Returns `List[FileInfo]` for all tracked files.
*   **`get_dependencies(file_path: Path)`:** Returns `Set[Path]` of files the target file imports.
*   **`get_reverse_dependencies(file_path: Path)`:** Returns `Set[Path]` of files that import the target file.
*   **`get_context(file_path: Path, include_dependencies=True, formatter=...)`:** Generates a context string.
*   **`start_watching()` / `stop_watching()`:** Controls the background file monitor.
*   **`clear_cache()`:** Removes cached analysis results.

## 🛠️ CLI Usage (Optional)

Kotemari also provides a basic command-line interface for quick checks and simple tasks:

```bash
# Activate environment
source .venv/bin/activate # Or .venv\Scripts\activate

# Basic commands
kotemari analyze
kotemari list
kotemari tree
kotemari dependencies <path/to/file.py>
kotemari context <path/to/file1.py> [<path/to/file2.py>...]

# Get help
kotemari --help
kotemari analyze --help
```

## 🔧 Development

Interested in contributing?

1.  **Set up the environment** (See Installation section).
2.  **Run tests:**
    ```bash
    pytest
    ```
3.  **Check code coverage:**
    ```bash
    pytest --cov=src/kotemari
    ```

Please refer to `CONTRIBUTING.md` (to be created) for contribution guidelines.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 💻 Supported Environments

*   **Python:** 3.8+
*   **OS:** Windows, macOS, Linux (tested primarily on Windows)

---

Let Kotemari simplify your Python project analysis! 🌳
