# Kotemari 🌳 - Understand Your Python Project's Soul Instantly!

[![PyPI version](https://badge.fury.io/py/kotemari.svg)](https://badge.fury.io/py/kotemari) <!-- Placeholder -->
[![Build Status](https://travis-ci.org/your-username/kotemari.svg?branch=main)](https://travis-ci.org/your-username/kotemari) <!-- Placeholder -->
[![Coverage Status](https://coveralls.io/repos/github/your-username/kotemari/badge.svg?branch=main)](https://coveralls.io/github/your-username/kotemari?branch=main) <!-- Placeholder -->

**Kotemari helps you effortlessly understand and leverage the dependency structure of your Python projects.** ✨

Ever wondered which files import a specific module? Or needed to gather all related code for an LLM prompt? Kotemari analyzes your Python project, tracks dependencies in real-time, and provides context with just a few lines of code!

## 🤔 Why Kotemari?

*   ** ridiculously Easy:** Get started in minutes. Install, point to your project, and analyze! 🚀
*   **⚡️ Real-time Awareness:** Automatically detects file changes and updates dependencies on the fly.
*   **🧠 Intelligent Analysis:** Understands Python imports to build an accurate dependency graph.
*   **🏎️ Efficient:** Uses caching for lightning-fast re-analysis.
*   **🎯 Versatile:** Perfect for code comprehension, refactoring assistance, context generation for LLMs, and more!
*   ** respecting `.gitignore`:** Plays nicely with your existing ignore rules.

## ✨ Key Features

*   **Automatic Dependency Analysis:** Parses Python files to find `import` statements.
*   **Real-time File Watching:** Monitors your project for changes (creations, modifications, deletions).
*   **Dependency Propagation:** Updates the status of files affected by changes in their dependencies.
*   **Context Generation:** Creates formatted context strings including a file and its dependencies (useful for LLMs).
*   **Caching:** Stores analysis results for faster subsequent runs.
*   **`.gitignore` Integration:** Respects rules defined in your `.gitignore` files.

## 📦 Installation

```bash
pip install kotemari
```
*(Note: Kotemari is not yet published on PyPI. For now, install from source.)*

To install the development version:
```bash
git clone https://github.com/your-username/kotemari.git # Replace with actual repo URL
cd kotemari
pip install -e .
```

## 🚀 Basic Usage

Using Kotemari is incredibly simple!

```python
import logging
from pathlib import Path
from kotemari import Kotemari

# Optional: Configure logging to see what Kotemari is doing
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 1. Initialize Kotemari with your project's root directory
project_path = Path("./path/to/your/python_project") # <-- Change this to your project path!
kotemari = Kotemari(project_path)

# 2. Analyze the project (this might take a moment the first time)
print("Analyzing project...")
kotemari.analyze_project()
print("Analysis complete!")

# 3. List all analyzed files
print("\nAnalyzed Files:")
for file_info in kotemari.list_files():
    print(f"- {file_info.path.relative_to(project_path)}")

# 4. Get dependencies of a specific file
target_file = project_path / "src" / "module_a.py" # Example file
print(f"\nDependencies of {target_file.name}:")
try:
    dependencies = kotemari.get_dependencies(target_file)
    if dependencies:
        for dep_path in dependencies:
            print(f"- {dep_path.relative_to(project_path)}")
    else:
        print("- No dependencies found.")
except FileNotFoundError:
    print(f"- File {target_file.name} not found in analysis results.")

# 5. Get files that depend on a specific file (reverse dependencies)
dependent_on_file = project_path / "src" / "utils.py" # Example file
print(f"\nFiles depending on {dependent_on_file.name}:")
try:
    reverse_deps = kotemari.get_reverse_dependencies(dependent_on_file)
    if reverse_deps:
        for rev_dep_path in reverse_deps:
            print(f"- {rev_dep_path.relative_to(project_path)}")
    else:
        print("- No files depend on this.")
except FileNotFoundError:
    print(f"- File {dependent_on_file.name} not found in analysis results.")

# 6. Get formatted context for a file and its dependencies
context_file = project_path / "src" / "main_logic.py" # Example file
print(f"\nGenerating context for {context_file.name} (max 4000 tokens):")
try:
    # max_tokens helps limit the context size, useful for LLMs
    context = kotemari.get_context(context_file, max_tokens=4000)
    print("--- Context Start ---")
    print(context)
    print("--- Context End ---")
except FileNotFoundError:
    print(f"- File {context_file.name} not found.")
except Exception as e:
    print(f"An error occurred generating context: {e}")


# 7. Optional: Start watching for file changes in the background
print("\nStarting file watcher (press Ctrl+C to stop)...")
kotemari.start_watching()

# Keep the script running to allow the watcher to work
try:
    # Example: Wait for a change or run other logic
    import time
    while True:
        # Check if a dependency became stale due to changes
        # (You might integrate this check into your application loop)
        # stale_files = [f for f in kotemari.list_files() if f.dependencies_stale]
        # if stale_files:
        #    print(f"\nDetected stale dependencies for: {[f.path.name for f in stale_files]}")
        #    # You might want to re-analyze or regenerate context here
        time.sleep(5)
except KeyboardInterrupt:
    print("\nStopping watcher...")
    kotemari.stop_watching()
    print("Watcher stopped.")

print("\nKotemari example finished.")

```

**Explanation:**

1.  **`Kotemari(project_root)`:** Creates an instance linked to your project directory.
2.  **`analyze_project()`:** Scans files, parses imports, and builds the initial dependency graph. It uses caching, so subsequent calls are faster unless `force_reanalyze=True` is used.
3.  **`list_files()`:** Returns a list of `FileInfo` objects for all successfully analyzed files.
4.  **`get_dependencies(path)`:** Returns a set of `Path` objects representing files that the given `path` directly imports.
5.  **`get_reverse_dependencies(path)`:** Returns a set of `Path` objects representing files that directly import the given `path`.
6.  **`get_context(path, max_tokens)`:** Fetches the content of the specified `path` and its direct dependencies, formats them clearly, and returns a single string. `max_tokens` provides an approximate limit to prevent overly large outputs (useful for LLM prompts). It prioritizes the target file's content.
7.  **`start_watching()` / `stop_watching()`:** Manages a background thread that monitors filesystem events. When relevant changes occur, Kotemari updates its internal state (e.g., marking files with changed dependencies as `dependencies_stale=True`).

## ⚙️ Configuration (Optional)

*(Details on configuration options, e.g., via `kotemari.toml` or init parameters, will be added here if applicable.)*

## 🙌 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

*(Contribution guidelines will be added here.)*

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 💻 Supported Environments

*   **Python:** 3.8+
*   **OS:** Windows, macOS, Linux (tested primarily on Windows)

---

Let Kotemari simplify your Python project analysis! 🌳
