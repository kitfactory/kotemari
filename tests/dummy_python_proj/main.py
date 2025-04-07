from my_module import utils
from my_module.sub_module.helper import greet


def main():
    """Main function"""
    data = utils.load_data("data.txt")
    message = greet("World")
    print(message)
    print(f"Data length: {len(data)}")

if __name__ == "__main__":
    main() 