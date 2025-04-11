# Kotemari 🪄

[![PyPI version](https://img.shields.io/pypi/v/kotemari.svg?style=flat-square)](https://pypi.python.org/pypi/kotemari) 
[![Build Status](https://img.shields.io/github/actions/workflow/status/<YOUR_GITHUB_USERNAME>/kotemari/ci.yml?branch=main&style=flat-square)](https://github.com/<YOUR_GITHUB_USERNAME>/kotemari/actions)
[![Code Coverage](https://img.shields.io/codecov/c/github/<YOUR_GITHUB_USERNAME>/kotemari?style=flat-square)](https://codecov.io/gh/<YOUR_GITHUB_USERNAME>/kotemari)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

Kotemari is a Python tool designed to analyze your Python project structure, understand dependencies, and intelligently generate context for Large Language Models (LLMs) like GPT. 🧠 It helps you focus your LLM prompts by providing only the relevant code snippets and dependencies. It also features real-time file monitoring to keep the analysis up-to-date effortlessly! ✨

## 🤔 Why Kotemari?

Working with large codebases and LLMs can be challenging. Providing the entire project context is often inefficient and costly. Kotemari solves this by:

*   **🎯 Smart Context Generation:** Creates concise context strings including only the necessary files and their dependencies, perfect for LLM prompts.
*   **🔄 Real-time Updates:** Monitors your project for file changes and automatically updates its understanding of dependencies in the background.
*   **🔍 Deep Project Insight:** Analyzes Python `import` statements to map dependencies between your project files.
*   **⚙️ Flexible Configuration:** Respects `.gitignore` and allows further customization via a `.kotemari.yml` configuration file (optional).
*   **💻 Simple CLI:** Offers easy-to-use commands for analysis, listing files, viewing dependencies, and generating context.

Kotemari makes interacting with LLMs about your code **simpler and more effective**. Get relevant context with just a few commands! 🎉

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

## ✨ Usage (CLI)

Kotemari provides a command-line interface for easy interaction.

```bash
# Activate your virtual environment first!
source .venv/bin/activate # Or .venv\Scripts\activate on Windows

# Get help
kotemari --help

# Analyze the project in the current directory
# (This builds an initial understanding and cache)
kotemari analyze

# List all tracked files (respecting .gitignore and .kotemari.yml)
kotemari list

# Show the project structure as a tree
kotemari tree

# Show dependencies for a specific file
kotemari dependencies src/kotemari/core.py

# Generate context for specific files (includes their dependencies)
kotemari context src/kotemari/gateway/cli_parser.py src/kotemari/controller/cli_controller.py

# Use verbose flags for more detailed logging
kotemari analyze -v   # INFO level logs
kotemari analyze -vv  # DEBUG level logs
```

*(The `watch` command for continuous background monitoring is under development and currently marked as experimental)*

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
