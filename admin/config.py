"""
管理后台配置文件
"""

# 版本信息
VERSION = "1.0.0"

# 管理后台配置
ADMIN_CONFIG = {
    "host": "0.0.0.0",
    "port": 9090,
    "username": "admin",
    "password": "admin123",
    "debug": False,
    "secret_key": "admin_secret_key",
    "max_history": 1000
}

# API配置
API_CONFIG = {
    "timeout": 30,
    "retry": 3,
    "cache_ttl": 3600
}

# 日志配置
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s | %(levelname)s | %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S"
}

# 插件市场配置
PLUGIN_MARKET_CONFIG = {
    "base_url": "https://xianan.xin:1562/api",
    "cache_dir": "_cache",
    "temp_dir": "_temp",
    "sync_interval": 3600
}
 