import logging
import os
from colorama import Fore, Style, Back

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        levelname_color = {
            'DEBUG': Fore.CYAN + Style.BRIGHT,
            'INFO': Fore.GREEN + Style.BRIGHT,
            'WARNING': Fore.YELLOW + Style.BRIGHT,
            'ERROR': Fore.RED + Style.BRIGHT,
            'CRITICAL': Fore.RED + Style.BRIGHT,
        }
        message = super().format(record)
        if record.levelname in levelname_color:
            message = levelname_color[record.levelname] + message + Style.RESET_ALL
        return message


class CustomLogger:
    def __init__(self):
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 创建日志目录
        log_dir = os.path.join(current_dir, '..', '..', 'log')
        os.makedirs(log_dir, exist_ok=True)
        # 设置日志文件路径
        self.log_file = os.path.join(log_dir, 'test.txt')
        
        self.logger = logging.getLogger('Stocklogger')
        self.logger.setLevel(logging.DEBUG)

        # 创建一个handler用于写入日志文件
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        plain_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(plain_formatter)

        # 创建一个handler用于输出到控制台（带有颜色）
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        colored_formatter = ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(colored_formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)


log = CustomLogger()
