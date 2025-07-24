import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    
    # 爬虫相关配置
    CRAWLER_CONFIG = {
        'download_timeout': 30,
        'page_load_timeout': 20,
        'max_retry_times': 3,
        'default_max_pages': 10,
        'default_max_docs': None
    }
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    
    # 下载目录配置
    DOWNLOAD_PATHS = {
        'gz': './规章',
        'memgov': './法律法规'
    }

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 