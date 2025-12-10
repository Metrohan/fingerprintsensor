# logger.py
# Merkezi loglama modülü - tüm sistem loglarını dosyaya ve konsola yazar

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Proje kök dizini ve log dosyası yolu
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "data")
LOG_FILE = os.path.join(LOG_DIR, "system.log")

# Log dizini yoksa oluştur
os.makedirs(LOG_DIR, exist_ok=True)

# Formatter - log formatı
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logger(name: str, level=logging.INFO) -> logging.Logger:
    """
    Belirtilen isimde bir logger oluşturur.
    Hem konsola hem de dosyaya log yazar.
    
    Args:
        name: Logger adı (genellikle modül adı)
        level: Log seviyesi (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        logging.Logger instance
    """
    logger = logging.getLogger(name)
    
    # Eğer zaten handler varsa tekrar ekleme
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Konsol handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    # Dosya handler (rotating - max 5MB, 3 yedek dosya)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5*1024*1024,  # 5 MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

# Varsayılan logger
default_logger = setup_logger("system")

def log_info(msg: str):
    """Bilgi mesajı logla"""
    default_logger.info(msg)

def log_warning(msg: str):
    """Uyarı mesajı logla"""
    default_logger.warning(msg)

def log_error(msg: str):
    """Hata mesajı logla"""
    default_logger.error(msg)

def log_debug(msg: str):
    """Debug mesajı logla"""
    default_logger.debug(msg)
