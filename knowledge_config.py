# 知识库配置文件
# 用户可以根据自己的知识库系统修改以下配置

# 知识库API基础配置
KNOWLEDGE_BASE_CONFIG = {
    # API基础URL
    "base_url": "https://knowledge.spaceplat.com",
    
    # 获取知识库列表的API端点
    "list_api": "/v1/kb/list",
    
    # 上传文件的API端点 
    "upload_api": "/v1/document/upload",
    
    # 解析文档的API端点
    "parse_api": "/v1/document/run",
    
    # 认证token (用户需要替换为自己的token)
    "authorization": "Bearer ZH_00015:eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiJ0ZXN0IiwibG9naW5NZXRob2QiOm51bGwsInRlbmVtZW50Q29kZSI6IlpIXzAwMDE1IiwiZXhwIjoxNzU0NDc0MTM3LCJpYXQiOjE3NTMxNzgxMzcsImFjY291bnQiOiIxMzUzMDg3MDU3NiJ9.7Gyow44Uc9nvjVUAiQZEN2P4cmiG9NiZerKr8cTSjLo",
    
    # APP相关配置
    "app_id": "PCSIGN",
    "app_sign": "2a44ad9b37c4c2cf8995b00efbc62f59aee483bcfee2223d4baf26d8ef3d0d00",
    
    # 请求超时时间（秒）
    "timeout": {
        "list": 30,      # 获取列表超时时间
        "upload": 120,   # 上传文件超时时间
        "parse": 180     # 解析文档超时时间
    },
    
    # 文件上传限制
    "file_limits": {
        "max_size_mb": 100,  # 最大文件大小（MB）
        "allowed_types": [   # 支持的文件类型
            ".pdf", ".doc", ".docx", ".txt", ".html", ".wps"
        ]
    },
    
    # 默认请求头
    "default_headers": {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    }
}

# MIME类型映射
MIME_TYPES_MAP = {
    '.pdf': 'application/pdf',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.txt': 'text/plain',
    '.html': 'text/html',
    '.wps': 'application/vnd.ms-works'
}

def get_knowledge_base_headers():
    """获取知识库API请求头"""
    from datetime import datetime
    
    headers = KNOWLEDGE_BASE_CONFIG["default_headers"].copy()
    headers.update({
        "Authorization": KNOWLEDGE_BASE_CONFIG["authorization"],
        "x-app-id": KNOWLEDGE_BASE_CONFIG["app_id"],
        "x-app-sign": KNOWLEDGE_BASE_CONFIG["app_sign"],
        "x-app-time": str(int(datetime.now().timestamp() * 1000))
    })
    return headers

def get_mime_type(file_name):
    """根据文件名获取MIME类型"""
    import os
    ext = os.path.splitext(file_name)[1].lower()
    return MIME_TYPES_MAP.get(ext, 'application/octet-stream') 
