import os

def load_data(filepath: str) -> str:
    """Loads data from a file."""
    # In a real scenario, provide proper path handling
    # 実際のシナリオでは、適切なパス処理を提供する
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""

def process_item(item):
    """Processes a single item."""
    return str(item).upper() 