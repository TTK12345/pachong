# --- 核心稳定性修复: Gevent猴子补丁 ---
# 必须在所有其他导入之前执行，以将标准库转换为非阻塞模式
from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit, join_room
import os
import threading
import json
from datetime import datetime, timedelta
import zipfile
import tempfile
import traceback
import platform
import uuid
import re
import gevent # 导入gevent用于异步sleep
import random # <--- 新增导入
import requests # 用于调用Jina AI API
from selenium.common.exceptions import TimeoutException # 导入Timeout异常类
import shutil # 用于文件操作
import mimetypes # 用于文件类型检测
from knowledge_config import KNOWLEDGE_BASE_CONFIG, get_knowledge_base_headers, get_mime_type

# 导入重构后的爬虫类
import sys
sys.path.append('./demo')
from gz_crawler_refactored import GzCrawler
from mem_gov_crawler_refactored import MemGovCrawler
from standard_text_crawler_refactored import StandardTextCrawler
from system_file_crawler_refactored import SystemFileCrawler
from normative_file_crawler_refactored import NormativeFileCrawler
from flk_crawler_refactored import FlkCrawler
from custom_page_crawler import CustomPageCrawler

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-for-multi-task'

# 根据系统选择不同的异步模式
if platform.system() == 'Linux':
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')
else:
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- 新增: 日志文件配置 ---
LOGS_DIR = 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)
    print(f"已创建日志文件夹: {LOGS_DIR}")

# --- 新增: 任务总结文件配置 ---
SUMMARIES_DIR = 'summaries'
if not os.path.exists(SUMMARIES_DIR):
    os.makedirs(SUMMARIES_DIR)
    print(f"已创建任务总结文件夹: {SUMMARIES_DIR}")

# --- 核心改动: 任务管理 ---
# 使用一个字典来管理所有任务
CRAWLER_TASKS = {}
# 存储任务总结报告的字典
TASK_SUMMARIES = {}

# 统一的爬虫类型名称映射
CRAWLER_TYPE_NAMES = {
    # 中华人民共和国应急管理部
    'mem_gz': '应急部-规章',
    'mem_flfg': '应急部-法律法规',
    'mem_gfxwj': '应急部-规范性文件', 
    'mem_bzwb': '应急部-标准文本',
    'mem_zdwj': '应急部-制度文件',
    
    # 国家法律法规数据库
    'flk_xf': '法规库-宪法',
    'flk_fl': '法规库-法律',
    'flk_xzfg': '法规库-行政法规',
    'flk_jcfg': '法规库-监察法规',
    'flk_sfjs': '法规库-司法解释',
    'flk_dfxfg': '法规库-地方性法规',
    
    # 其他
    'custom': '自定义页面'
}

# 统一的下载目录配置
DOWNLOAD_DIRS = {
    # 中华人民共和国应急管理部
    "应急部-规章": "./应急部-规章",
    "应急部-法律法规": "./应急部-法律法规", 
    "应急部-规范性文件": "./应急部-规范性文件",
    "应急部-标准文本": "./应急部-标准文本",
    "应急部-制度文件": "./应急部-制度文件",
    
    # 国家法律法规数据库
    "法规库-宪法": "./法规库-宪法",
    "法规库-法律": "./法规库-法律",
    "法规库-行政法规": "./法规库-行政法规",
    "法规库-监察法规": "./法规库-监察法规", 
    "法规库-司法解释": "./法规库-司法解释",
    "法规库-地方性法规": "./法规库-地方性法规",
    
    # 其他
    "自定义页面": "./自定义页面"
}

def save_summary_to_file(task_id, summary_data):
    """将任务总结保存到文件"""
    try:
        summary_file_path = os.path.join(SUMMARIES_DIR, f"{task_id}_summary.json")
        with open(summary_file_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
        print(f"[DEBUG] 任务总结已保存到文件: {summary_file_path}")
        return True
    except Exception as e:
        print(f"[ERROR] 保存任务总结到文件失败: {e}")
        return False

# 临时修复：重写load_summaries_from_files函数
def load_summaries_from_files_fixed():
    """从文件加载所有任务总结 - 修复版本"""
    global TASK_SUMMARIES
    TASK_SUMMARIES = {}
    try:
        if not os.path.exists(SUMMARIES_DIR):
            return
        
        for filename in os.listdir(SUMMARIES_DIR):
            if filename.endswith('_summary.json'):
                task_id = filename.replace('_summary.json', '')
                file_path = os.path.join(SUMMARIES_DIR, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        summary_data = json.load(f)
                        TASK_SUMMARIES[task_id] = summary_data
                        print(f"[DEBUG] 已加载任务总结: {task_id}")
                except Exception as e:
                    print(f"[ERROR] 加载任务总结文件 {filename} 失败: {e}")
        
        print(f"[DEBUG] 总共加载了 {len(TASK_SUMMARIES)} 个任务总结")
    except Exception as e:
        print(f"[ERROR] 加载任务总结时发生错误: {e}")

# 使用修复版本
load_summaries_from_files = load_summaries_from_files_fixed

def delete_summary_file(task_id):
    """删除任务总结文件"""
    try:
        summary_file_path = os.path.join(SUMMARIES_DIR, f"{task_id}_summary.json")
        if os.path.exists(summary_file_path):
            os.remove(summary_file_path)
            print(f"[DEBUG] 已删除任务总结文件: {summary_file_path}")
            return True
        return False
    except Exception as e:
        print(f"[ERROR] 删除任务总结文件失败: {e}")
        return False

def crawl_custom_page(task_id, page_url, logger, attachment_crawler=None):
    """使用Jina AI API爬取自定义页面并下载附件"""
    try:
        logger.log("开始自定义页面爬取任务...")
        
        # 更新进度 - 总共5个步骤：API获取、保存内容、搜索附件、下载附件、完成
        update_task_progress(task_id, {'current': 1, 'total': 5, 'percentage': 20})
        
        # 验证和规范化URL
        if not page_url.startswith(('http://', 'https://')):
            page_url = 'https://' + page_url
            logger.log(f"已自动添加https://前缀: {page_url}")
        
        # 第一步：使用Jina AI API获取页面内容
        logger.log("正在连接Jina AI API...")
        jina_api_url = f"https://r.jina.ai/{page_url}"
        headers = {
            "Authorization": "Bearer jina_cdb5f0355dee4b2ba732fa2c36a8d309tlFOpHzeNtXqc_lja-s9WS4wzIx1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/plain, */*"
        }
        
        logger.log(f"正在爬取页面: {page_url}")
        logger.log(f"Jina API URL: {jina_api_url}")
        
        # 调用Jina AI API
        response = requests.get(jina_api_url, headers=headers, timeout=60)
        
        # 详细的响应调试信息
        logger.log(f"API响应状态码: {response.status_code}")
        if response.status_code != 200:
            logger.log(f"响应头: {dict(response.headers)}")
            logger.log(f"响应内容: {response.text[:500]}...")  # 只显示前500字符
        
        if response.status_code != 200:
            error_msg = f"API请求失败，状态码: {response.status_code}"
            logger.log(error_msg, 'error')
            return {'success': False, 'error': error_msg}
        
        # 第二步：保存页面内容
        update_task_progress(task_id, {'current': 2, 'total': 5, 'percentage': 40})
        
        content = response.text
        logger.log(f"成功获取页面内容，长度: {len(content)} 字符")
        
        # 检查是否被停止（在保存前检查）
        if attachment_crawler and attachment_crawler.is_stopped:
            logger.log("任务已被停止", 'warning')
            return {'success': False, 'error': '任务已被停止'}
        
        # 创建保存目录
        save_dir = "./自定义页面"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            logger.log(f"已创建保存目录: {save_dir}")
        
        # 生成页面内容文件名（更清晰的命名）
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(page_url)
            domain = parsed_url.netloc or "unknown_domain"
            # 清理域名中的特殊字符
            clean_domain = re.sub(r'[^\w\.-]', '_', domain)
            filename = f"页面内容_{clean_domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        except:
            filename = f"页面内容_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        # 保存内容到文件
        file_path = os.path.join(save_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"页面URL: {page_url}\n")
            f.write(f"爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"任务ID: {task_id}\n")
            f.write("="*60 + "\n\n")
            f.write(content)
        
        logger.log(f"页面内容已保存到: {file_path}")
        
        # 第三步：搜索并下载附件
        update_task_progress(task_id, {'current': 3, 'total': 5, 'percentage': 60})
        
        # 检查是否被停止（在搜索附件前检查）
        if attachment_crawler and attachment_crawler.is_stopped:
            logger.log("任务已被停止", 'warning')
            return {'success': False, 'error': '任务已被停止'}
        
        logger.log("开始搜索页面附件...")
        
        # 如果没有传入爬虫实例，则创建一个（向后兼容）
        if attachment_crawler is None:
            attachment_crawler = CustomPageCrawler(
                download_path=save_dir,
                logger=logger,
                task_id=task_id,
                socketio=socketio,
                progress_callback=update_task_progress
            )
        
        # 设置基础URL用于处理相对链接
        attachment_crawler.set_base_url(page_url)
        
        # 初始化爬虫的统计信息
        attachment_stats = {
            'total_pages': 1,
            'total_sub_links': 0,
            'total_documents': 1,  # 页面内容文件
            'successful_downloads': 1,  # 页面内容文件
            'failed_downloads': 0,
            'pages_processed': [{'page_num': 1, 'sub_links_count': 0}],
            'failed_links': []
        }
        
        try:
            # 启动浏览器驱动
            attachment_crawler.start_driver()
            
            # 搜索附件
            attachments = attachment_crawler.get_sub_links(page_url)
            attachment_stats['total_sub_links'] = len(attachments)
            
            # 第四步：下载附件
            update_task_progress(task_id, {'current': 4, 'total': 5, 'percentage': 80})
            
            if attachments:
                logger.log(f"开始下载 {len(attachments)} 个附件...")
                
                for i, attachment in enumerate(attachments):
                    # 检查是否被停止
                    if attachment_crawler.is_stopped:
                        logger.log("任务已被停止", 'warning')
                        attachment_stats['status'] = 'stopped'
                        break
                        
                    logger.log(f"下载附件 {i+1}/{len(attachments)}: {attachment.get('title', '未知附件')}")
                    
                    # 下载附件
                    success = attachment_crawler.download_from_sublink(attachment)
                    
                    if success:
                        attachment_stats['successful_downloads'] += 1
                        attachment_stats['total_documents'] += 1
                    else:
                        attachment_stats['failed_downloads'] += 1
                        attachment_stats['failed_links'].append({
                            'title': attachment.get('title', '未知附件'),
                            'url': attachment.get('url', ''),
                            'error': '下载失败'
                        })
                    
                    # 更新进度
                    attachment_progress = 80 + (i + 1) / len(attachments) * 15  # 80-95%
                    update_task_progress(task_id, {'current': 4, 'total': 5, 'percentage': attachment_progress})
                
                logger.log(f"附件下载完成，成功: {attachment_stats['successful_downloads']-1}，失败: {attachment_stats['failed_downloads']}")
            else:
                logger.log("未发现可下载的附件")
                
        except Exception as e:
            logger.log(f"附件下载过程中出错: {str(e)}", 'warning')
            import traceback
            logger.log(f"详细错误: {traceback.format_exc()}", 'warning')
        finally:
            # 关闭浏览器驱动
            if attachment_crawler.driver:
                attachment_crawler.close_driver()
        
        # 第五步：完成任务
        update_task_progress(task_id, {'current': 5, 'total': 5, 'percentage': 100})
        
        # 保存任务总结
        save_custom_page_summary(task_id, page_url, file_path, content, attachment_stats)
        
        logger.log("自定义页面爬取任务完成！", 'success')
        return {
            'success': True, 
            'file_path': file_path, 
            'content_length': len(content),
            'attachments_found': attachment_stats['total_sub_links'],
            'attachments_downloaded': attachment_stats['successful_downloads'] - 1  # 减去页面内容文件
        }
            
    except requests.exceptions.Timeout:
        error_msg = "请求超时，请检查网络连接或稍后重试"
        logger.log(error_msg, 'error')
        return {'success': False, 'error': error_msg}
    except requests.exceptions.RequestException as e:
        error_msg = f"网络请求错误: {str(e)}"
        logger.log(error_msg, 'error')
        return {'success': False, 'error': error_msg}
    except Exception as e:
        error_msg = f"爬取过程中发生错误: {str(e)}"
        logger.log(error_msg, 'error')
        import traceback
        logger.log(f"详细错误: {traceback.format_exc()}", 'error')
        return {'success': False, 'error': error_msg}

def save_custom_page_summary(task_id, page_url, file_path, content, stats):
    """保存自定义页面爬取的任务总结"""
    try:
        # 生成总结报告文本
        summary_lines = []
        
        def add_line(txt):
            summary_lines.append(txt)
        
        add_line("\n" + "="*60)
        add_line("自定义页面爬取总结报告")
        add_line("="*60)
        add_line(f"\n🌐 页面信息:")
        add_line(f"   页面URL: {page_url}")
        add_line(f"   爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        add_line(f"   任务ID: {task_id}")
        
        add_line(f"\n📊 内容统计:")
        add_line(f"   页面内容长度: {len(content)} 字符")
        add_line(f"   页面保存文件: {file_path}")
        
        # 附件统计信息
        attachments_found = stats.get('total_sub_links', 0)
        successful_attachments = stats.get('successful_downloads', 1) - 1  # 减去页面内容文件
        failed_attachments = stats.get('failed_downloads', 0)
        
        add_line(f"\n📎 附件统计:")
        add_line(f"   发现附件数量: {attachments_found}")
        add_line(f"   成功下载附件: {successful_attachments}")
        if failed_attachments > 0:
            add_line(f"   下载失败附件: {failed_attachments}")
        
        add_line(f"\n📁 文件保存位置: ./自定义页面")
        
        add_line("\n🎯 任务总结:")
        add_line("   ✅ 成功爬取了 1 个自定义页面")
        add_line("   ✅ 页面内容已保存到本地文件")
        if attachments_found > 0:
            add_line(f"   📎 发现并处理了 {attachments_found} 个附件")
            if successful_attachments > 0:
                add_line(f"   ✅ 成功下载了 {successful_attachments} 个附件")
            if failed_attachments > 0:
                add_line(f"   ❌ {failed_attachments} 个附件下载失败")
        else:
            add_line("   📎 未发现可下载的附件")
        
        # 显示失败的附件信息
        failed_links = stats.get('failed_links', [])
        if failed_links:
            add_line(f"\n❌ 下载失败的附件:")
            for i, failed_link in enumerate(failed_links, 1):
                add_line(f"   {i}. {failed_link.get('title', '未知附件')} - {failed_link.get('error', '未知错误')}")
        
        add_line("\n" + "="*60)
        add_line("自定义页面爬取任务完成！")
        add_line("="*60)
        
        summary_text = "\n".join(summary_lines)
        
        # 保存到TASK_SUMMARIES
        TASK_SUMMARIES[task_id] = {
            'task_id': task_id,
            'summary': summary_text,
            'stats': stats,
            'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'crawler_type': 'custom',
            'crawler_name': '自定义页面',
            'save_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 同时保存到文件
        save_summary_to_file(task_id, TASK_SUMMARIES[task_id])
        
        print(f"[DEBUG] 已保存自定义页面任务 {task_id} 的总结报告")
            
    except Exception as e:
        print(f"[ERROR] 保存自定义页面总结时出错: {e}")

class WebSocketLogger:
    """用于向特定任务房间发送日志并写入文件的类"""
    def __init__(self, socketio, task_id):
        self.socketio = socketio
        self.task_id = task_id
        self.log_file_path = os.path.join(LOGS_DIR, f"{self.task_id}.log")
        try:
            # 以UTF-8编码追加模式打开文件
            self.log_file = open(self.log_file_path, 'a', encoding='utf-8')
        except Exception as e:
            print(f"严重错误: 无法打开日志文件 {self.log_file_path}: {e}")
            self.log_file = None
    
    def log(self, message, level='info'):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_data = {
            'timestamp': datetime.now().strftime('%H:%M:%S'), # 前端只显示时间
            'level': level,
            'message': str(message),
            'task_id': self.task_id  # 添加task_id，让前端知道消息来自哪个任务
        }
        
        # 格式化控制台和文件日志消息
        log_message_full = f"[{timestamp}] [{level.upper()}] [Task: {self.task_id}] {message}"
        
        print(log_message_full) # 打印到控制台
        self.socketio.emit('log_message', log_data, room=self.task_id) # 发送到前端

        # 写入文件
        if self.log_file:
            try:
                self.log_file.write(log_message_full + '\n')
                self.log_file.flush() # 确保立即写入
            except Exception as e:
                print(f"错误: 无法写入日志文件 {self.task_id}: {e}")
    
    def close(self):
        """关闭日志文件句柄"""
        if self.log_file:
            self.log_file.close()
            self.log_file = None

# BaseWebCrawler 类已经被移除，功能已集成到 demo/base_crawler.py 中的 BaseCrawler 类

# 所有WebXXXCrawler类已被删除，直接使用demo中的爬虫类

def update_task_progress(task_id, progress_data):
    """更新任务进度的回调函数"""
    if task_id in CRAWLER_TASKS:
        CRAWLER_TASKS[task_id]['progress'] = progress_data

def run_crawler_thread(task_id, crawler_type, max_pages, page_url=None):
    """独立的爬虫线程函数"""
    print(f"[DEBUG] 进入爬虫线程函数: task_id={task_id}, crawler_type={crawler_type}")
    
    task = CRAWLER_TASKS.get(task_id)
    if not task:
        print(f"错误：找不到任务 {task_id}")
        return

    logger = task['logger']
    try:
        print(f"[DEBUG] 爬虫线程已启动，准备创建爬虫实例...")
        logger.log("爬虫线程已启动...")
        
        # 直接使用demo中的爬虫类，传递task_id、socketio和progress_callback参数
        if crawler_type == 'gz' or crawler_type == 'mem_gz':
            print(f"[DEBUG] 创建 GzCrawler 实例...")
            download_path = "./应急部-规章" if crawler_type == 'mem_gz' else "./规章"
            crawler = GzCrawler(download_path=download_path, logger=logger, task_id=task_id, socketio=socketio, progress_callback=update_task_progress)
        elif crawler_type == 'memgov' or crawler_type == 'mem_flfg':
            print(f"[DEBUG] 创建 MemGovCrawler 实例...")
            download_path = "./应急部-法律法规" if crawler_type == 'mem_flfg' else "./法律法规"
            crawler = MemGovCrawler(download_path=download_path, logger=logger, task_id=task_id, socketio=socketio, progress_callback=update_task_progress)
        elif crawler_type == 'normative_file' or crawler_type == 'mem_gfxwj':
            print(f"[DEBUG] 创建 NormativeFileCrawler 实例...")
            download_path = "./应急部-规范性文件" if crawler_type == 'mem_gfxwj' else "./规范性文件"
            crawler = NormativeFileCrawler(download_path=download_path, logger=logger, task_id=task_id, socketio=socketio, progress_callback=update_task_progress)
        elif crawler_type == 'standard_text' or crawler_type == 'mem_bzwb':
            print(f"[DEBUG] 创建 StandardTextCrawler 实例...")
            download_path = "./应急部-标准文本" if crawler_type == 'mem_bzwb' else "./标准/标准文本"
            crawler = StandardTextCrawler(download_path=download_path, logger=logger, task_id=task_id, socketio=socketio, progress_callback=update_task_progress)
        elif crawler_type == 'system_file' or crawler_type == 'mem_zdwj':
            print(f"[DEBUG] 创建 SystemFileCrawler 实例...")
            download_path = "./应急部-制度文件" if crawler_type == 'mem_zdwj' else "./标准/制度文件"
            crawler = SystemFileCrawler(download_path=download_path, logger=logger, task_id=task_id, socketio=socketio, progress_callback=update_task_progress)
        elif crawler_type.startswith('flk_'):
            print(f"[DEBUG] 创建法规数据库爬虫实例: {crawler_type}")
            type_name = CRAWLER_TYPE_NAMES.get(crawler_type, '未知类型')
            download_path = f"./{type_name}"
            crawler = FlkCrawler(
                download_path=download_path, 
                flk_type=crawler_type,
                logger=logger, 
                task_id=task_id, 
                socketio=socketio, 
                progress_callback=update_task_progress
            )
        elif crawler_type == 'custom':
            print(f"[DEBUG] 自定义页面爬取: {page_url}")
            logger.log(f"开始爬取自定义页面: {page_url}")
            
            # 创建自定义页面爬虫实例（用于停止功能）
            save_dir = "./自定义页面"
            custom_crawler = CustomPageCrawler(
                download_path=save_dir,
                logger=logger,
                task_id=task_id,
                socketio=socketio,
                progress_callback=update_task_progress
            )
            
            # 将爬虫实例存储到任务中，以便停止功能使用
            task['crawler'] = custom_crawler
            task['status'] = 'running'
            
            # 向所有客户端发送任务状态更新
            socketio.emit('task_status_change', {
                'task_id': task_id,
                'status': 'running',
                'crawler_type': crawler_type
            })
            
            # 调用自定义页面处理函数
            custom_crawl_result = crawl_custom_page(task_id, page_url, logger, custom_crawler)
            task['status'] = 'completed'
            task['end_time'] = datetime.now()
            
            # 向所有客户端发送任务完成通知
            socketio.emit('task_status_change', {
                'task_id': task_id,
                'status': 'completed',
                'crawler_type': crawler_type
            })
            return
        else:
            print(f"[DEBUG] 未知的爬虫类型: {crawler_type}")
            logger.log(f"未知的爬虫类型: {crawler_type}", 'error')
            task['status'] = 'error'
            return

        print(f"[DEBUG] 爬虫实例创建成功，开始设置任务状态...")
        task['crawler'] = crawler
        task['status'] = 'running'
        
        # 向所有客户端发送任务状态更新
        socketio.emit('task_status_change', {
            'task_id': task_id,
            'status': 'running',
            'crawler_type': crawler_type
        })
        
        print(f"[DEBUG] 任务状态已更新为运行中，开始执行爬虫...")
        
        # 执行爬虫任务，统一使用多页面逻辑
        if crawler_type == 'gz' or crawler_type == 'mem_gz':
            print(f"[DEBUG] 开始执行规章爬虫...")
            base_url = "https://www.mem.gov.cn/gk/zfxxgkpt/fdzdgknr/gz11/"
            crawler.crawl_all_pages(base_url, max_pages=max_pages)
        elif crawler_type == 'memgov' or crawler_type == 'mem_flfg':
            print(f"[DEBUG] 开始执行法律法规爬虫...")
            base_url = "https://www.mem.gov.cn/fw/flfgbz/fg/"
            crawler.crawl_all_pages(base_url, max_pages=1)  # 单页面，max_pages=1
        elif crawler_type == 'normative_file' or crawler_type == 'mem_gfxwj':
            print(f"[DEBUG] 开始执行规范性文件爬虫...")
            base_url = "https://www.mem.gov.cn/fw/flfgbz/gfxwj/"
            crawler.crawl_all_pages(base_url, max_pages=1)  # 单页面，max_pages=1
        elif crawler_type == 'standard_text' or crawler_type == 'mem_bzwb':
            print(f"[DEBUG] 开始执行标准文本爬虫...")
            base_url = "https://www.mem.gov.cn/fw/flfgbz/bz/bzwb/"
            crawler.crawl_all_pages(base_url, max_pages=max_pages)
        elif crawler_type == 'system_file' or crawler_type == 'mem_zdwj':
            print(f"[DEBUG] 开始执行制度文件爬虫...")
            base_url = "https://www.mem.gov.cn/fw/flfgbz/bz/bzgg/"
            crawler.crawl_all_pages(base_url, max_pages=max_pages)
        elif crawler_type.startswith('flk_'):
            print(f"[DEBUG] 开始执行法规数据库爬虫: {crawler_type}")
            # 法规数据库爬虫通过API获取数据，不需要base_url
            base_url = "https://flk.npc.gov.cn/"
            crawler.crawl_all_pages(base_url, max_pages=max_pages)
        
        print(f"[DEBUG] 爬虫执行完成，设置任务状态为完成...")
        task['status'] = 'completed'
        task['end_time'] = datetime.now()
        
        # 直接保存总结报告到数据结构
        if 'crawler' in task and hasattr(task['crawler'], 'stats'):
            try:
                crawler = task['crawler']
                
                # 生成总结报告文本（与爬虫端完全相同的逻辑）
                summary_lines = []
                
                def add_line(txt):
                    summary_lines.append(txt)
                
                stats = crawler.stats
                add_line("\n" + "="*60)
                add_line("爬取任务总结报告")
                add_line("="*60)
                add_line("\n📊 基本统计信息:")
                add_line(f"   总页数: {stats.get('total_pages', 0)}")
                add_line(f"   总子链接数: {stats.get('total_sub_links', 0)}")
                add_line(f"   总文档数: {stats.get('total_documents', 0)}")
                add_line(f"   成功下载数: {stats.get('successful_downloads', 0)}")
                add_line(f"   失败下载数: {stats.get('failed_downloads', 0)}")
                
                total_docs = stats.get('total_documents', 0)
                successful_docs = stats.get('successful_downloads', 0)
                if total_docs > 0:
                    success_rate = (successful_docs / total_docs) * 100
                    add_line(f"   下载成功率: {success_rate:.1f}%")
                else:
                    add_line(f"   下载成功率: 0.0% (无文档)")
                
                add_line(f"\n📁 文件保存位置: {crawler.download_path}")
                
                add_line("\n📄 页面处理详情:")
                pages_processed = stats.get('pages_processed', [])
                if pages_processed:
                    for page_info in pages_processed:
                        page_num = page_info.get('page_num', '未知')
                        sub_links_count = page_info.get('sub_links_count', 0)
                        add_line(f"   第{page_num}页: {sub_links_count}个子链接")
                else:
                    add_line("   无页面被处理")
                
                add_line("\n❌ 失败链接详情:")
                failed_links = stats.get('failed_links', [])
                if failed_links:
                    for failed_link in failed_links:
                        title = failed_link.get('title', '未知标题')
                        reason = failed_link.get('reason', '未知原因')
                        url = failed_link.get('url', '未知URL')
                        add_line(f"   - {title}")
                        add_line(f"     原因: {reason}")
                        add_line(f"     URL: {url}")
                else:
                    add_line("   无失败链接")
                
                add_line("\n🎯 任务总结:")
                if successful_docs > 0:
                    add_line(f"   ✅ 成功下载了 {successful_docs} 个文档")
                if stats.get('failed_downloads', 0) > 0:
                    add_line(f"   ⚠️  有 {stats.get('failed_downloads', 0)} 个文档下载失败")
                if failed_links:
                    add_line(f"   ❌ 有 {len(failed_links)} 个链接处理失败")
                
                add_line("\n" + "="*60)
                add_line("爬取任务完成！")
                add_line("="*60)
                
                # 保存到TASK_SUMMARIES
                summary_text = "\n".join(summary_lines)
                
                # 获取爬虫类型的中文名称
                crawler_type_names = CRAWLER_TYPE_NAMES
                
                crawler_type_attr = getattr(crawler, 'crawler_type', crawler_type)
                
                TASK_SUMMARIES[task_id] = {
                    'task_id': task_id,
                    'summary': summary_text,
                    'stats': stats,
                    'end_time': task['end_time'].strftime('%Y-%m-%d %H:%M:%S'),
                    'crawler_type': crawler_type_attr,
                    'crawler_name': crawler_type_names.get(crawler_type_attr, '未知'),
                    'save_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # 同时保存到文件
                save_summary_to_file(task_id, TASK_SUMMARIES[task_id])
                
                print(f"[DEBUG] 已直接保存任务 {task_id} 的总结报告到数据结构")
                print(f"[DEBUG] TASK_SUMMARIES 现在包含: {list(TASK_SUMMARIES.keys())}")

            except Exception as e:
                print(f"[DEBUG] 直接保存总结报告时出错: {e}")
                import traceback
                print(f"[DEBUG] 错误详情: {traceback.format_exc()}")
        
        # 向所有客户端发送任务完成通知
        socketio.emit('task_status_change', {
            'task_id': task_id,
            'status': 'completed',
            'crawler_type': crawler_type
        })

    except Exception as e:
        print(f"[DEBUG] 爬虫执行出错: {str(e)}")
        print(f"[DEBUG] 错误详情: {traceback.format_exc()}")
        task['status'] = 'error'
        task['end_time'] = datetime.now()
        error_msg = f'爬虫执行出错: {str(e)}'
        logger.log(error_msg, 'error')
        logger.log(f"详细错误: {traceback.format_exc()}", 'error')
        
        # 向所有客户端发送任务错误通知
        socketio.emit('task_status_change', {
            'task_id': task_id,
            'status': 'error',
            'crawler_type': crawler_type,
            'error_message': error_msg
        })
    finally:
        print(f"[DEBUG] 清理任务资源...")
        if 'logger' in task and hasattr(task['logger'], 'close'):
            task['logger'].close()
            logger.log("日志文件已关闭。")
            
        if 'crawler' in task and hasattr(task['crawler'], 'driver') and task['crawler'].driver:
            try:
                task['crawler'].driver.quit()
                logger.log("浏览器已关闭")
            except: pass
        socketio.emit('crawler_completed', {'message': '爬虫任务结束'}, room=task_id)
        logger.log("爬虫线程已结束。", "info")
        print(f"[DEBUG] 爬虫线程已结束: {task_id}")

def cleanup_old_tasks():
    """后台线程，定期清理旧的已完成任务以释放内存"""
    while True:
        gevent.sleep(600)  # 每10分钟检查一次
        now = datetime.now()
        tasks_to_delete = []
        
        try:
            # 创建任务字典的副本进行迭代，避免在迭代时修改字典
            for task_id, task_data in list(CRAWLER_TASKS.items()):
                if task_data.get('end_time'):
                    # 如果任务已结束超过5分钟，则标记为待删除
                    if now - task_data['end_time'] > timedelta(minutes=5):
                        tasks_to_delete.append(task_id)
            
            if tasks_to_delete:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 清理 {len(tasks_to_delete)} 个旧任务...")
                for task_id in tasks_to_delete:
                    if task_id in CRAWLER_TASKS:
                        del CRAWLER_TASKS[task_id]
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 清理任务时发生错误: {e}")

# --- API 和 Socket.IO 路由 ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start_crawler', methods=['POST'])
def start_crawler():
    data = request.get_json()
    crawler_type = data.get('crawler_type')
    max_pages = data.get('max_pages', 10)
    page_url = data.get('page_url')  # 获取自定义页面URL
    
    task_id = "task-" + str(uuid.uuid4())
    logger = WebSocketLogger(socketio, task_id)

    # 添加更多任务信息
    CRAWLER_TASKS[task_id] = {
        'status': 'starting', 
        'logger': logger, 
        'crawler': None,
        'start_time': datetime.now(), 
        'end_time': None,
        'crawler_type': crawler_type,  # 爬虫类型
        'max_pages': max_pages,       # 最大页数
        'page_url': page_url,         # 自定义页面URL
        'progress': {'current': 0, 'total': 0, 'percentage': 0, 'task_id': task_id}  # 进度信息
    }
    logger.log(f"任务 {task_id} 已创建，准备启动...")
    
    # 启动gevent线程
    gevent.spawn(run_crawler_thread, task_id, crawler_type, max_pages, page_url)
    
    return jsonify({'success': True, 'message': '爬虫任务已创建', 'task_id': task_id})

@app.route('/api/stop_crawler', methods=['POST'])
def stop_crawler():
    task_id = request.get_json().get('task_id')
    task = CRAWLER_TASKS.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'})
    if task['status'] == 'running' and task.get('crawler'):
        task['crawler'].stop()
        task['status'] = 'stopping'  # 更新状态
        return jsonify({'success': True, 'message': '停止信号已发送'})
    return jsonify({'success': False, 'message': '任务不在运行状态，无法停止'})

# 新增：获取所有任务状态的API
@app.route('/api/get_all_tasks', methods=['GET'])
def get_all_tasks():
    """获取所有任务的状态信息"""
    tasks_info = []
    for task_id, task_data in CRAWLER_TASKS.items():
        # 计算运行时间
        if task_data['start_time']:
            if task_data['end_time']:
                duration = task_data['end_time'] - task_data['start_time']
            else:
                duration = datetime.now() - task_data['start_time']
            duration_str = str(duration).split('.')[0]  # 去掉微秒
        else:
            duration_str = "0:00:00"
        
        # 获取爬虫类型的中文名称
        crawler_type_names = CRAWLER_TYPE_NAMES
        
        task_info = {
            'task_id': task_id,
            'status': task_data['status'],
            'crawler_type': task_data.get('crawler_type', 'unknown'),
            'crawler_name': crawler_type_names.get(task_data.get('crawler_type', ''), '未知'),
            'start_time': task_data['start_time'].strftime('%Y-%m-%d %H:%M:%S') if task_data['start_time'] else None,
            'end_time': task_data['end_time'].strftime('%Y-%m-%d %H:%M:%S') if task_data['end_time'] else None,
            'duration': duration_str,
            'max_pages': task_data.get('max_pages'),
            'progress': task_data.get('progress', {'current': 0, 'total': 0, 'percentage': 0})
        }
        tasks_info.append(task_info)
    
    # 按开始时间排序，最新的在前面
    tasks_info.sort(key=lambda x: x['start_time'] if x['start_time'] else '', reverse=True)
    
    return jsonify({'tasks': tasks_info})

# 新增：获取单个任务详情的API
@app.route('/api/get_task_detail/<task_id>', methods=['GET'])
def get_task_detail(task_id):
    """获取单个任务的详细信息"""
    task = CRAWLER_TASKS.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    
    # 计算运行时间
    if task['start_time']:
        if task['end_time']:
            duration = task['end_time'] - task['start_time']
        else:
            duration = datetime.now() - task['start_time']
        duration_str = str(duration).split('.')[0]
    else:
        duration_str = "0:00:00"
    
    # 获取爬虫类型的中文名称
    crawler_type_names = CRAWLER_TYPE_NAMES
    
    task_detail = {
        'task_id': task_id,
        'status': task['status'],
        'crawler_type': task.get('crawler_type', 'unknown'),
        'crawler_name': crawler_type_names.get(task.get('crawler_type', ''), '未知'),
        'start_time': task['start_time'].strftime('%Y-%m-%d %H:%M:%S') if task['start_time'] else None,
        'end_time': task['end_time'].strftime('%Y-%m-%d %H:%M:%S') if task['end_time'] else None,
        'duration': duration_str,
        'max_pages': task.get('max_pages'),
        'progress': task.get('progress', {'current': 0, 'total': 0, 'percentage': 0})
    }
    
    return jsonify({'success': True, 'task': task_detail})

# 新增：删除已完成任务的API
@app.route('/api/delete_task/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除已完成的任务"""
    task = CRAWLER_TASKS.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    
    if task['status'] in ['running', 'starting']:
        return jsonify({'success': False, 'message': '不能删除正在运行的任务'}), 400
    
    # 关闭logger
    if 'logger' in task and hasattr(task['logger'], 'close'):
        task['logger'].close()
    
    # 删除任务
    del CRAWLER_TASKS[task_id]
    
    return jsonify({'success': True, 'message': '任务已删除'})

# 新增：获取任务统计信息的API
@app.route('/api/get_tasks_stats', methods=['GET'])
def get_tasks_stats():
    """获取任务统计信息"""
    stats = {
        'total': len(CRAWLER_TASKS),
        'running': 0,
        'completed': 0,
        'error': 0,
        'stopping': 0,
        'starting': 0
    }
    
    for task_data in CRAWLER_TASKS.values():
        status = task_data['status']
        if status in stats:
            stats[status] += 1
    
    return jsonify({'stats': stats})

# 获取任务总结报告的API
@app.route('/api/get_task_summaries', methods=['GET'])
def get_task_summaries():
    """获取所有任务的总结报告列表"""
    try:
        print(f"[DEBUG] 收到获取任务总结请求")
        print(f"[DEBUG] TASK_SUMMARIES 当前包含 {len(TASK_SUMMARIES)} 个总结报告")
        print(f"[DEBUG] TASK_SUMMARIES 内容: {list(TASK_SUMMARIES.keys())}")
        
        summaries = []
        for task_id, summary_data in TASK_SUMMARIES.items():
            summaries.append(summary_data)
        
        # 按保存时间排序，最新的在前面
        summaries.sort(key=lambda x: x.get('save_time', ''), reverse=True)
        
        print(f"[DEBUG] 返回 {len(summaries)} 个总结报告")
        return jsonify({'summaries': summaries})
    
    except Exception as e:
        print(f"获取任务总结时出错: {e}")
        return jsonify({'error': str(e), 'summaries': []}), 500

# 获取单个任务总结内容的API
@app.route('/api/get_summary_content/<task_id>', methods=['GET'])
def get_summary_content(task_id):
    """获取指定任务的总结内容"""
    try:
        if task_id in TASK_SUMMARIES:
            summary_data = TASK_SUMMARIES[task_id]
            return jsonify({
                'content': summary_data['summary'],
                'task_id': task_id,
                'name': f"任务总结 - {summary_data['crawler_name']}"
            })
        else:
            return jsonify({'error': f'任务 {task_id} 的总结不存在'}), 404
            
    except Exception as e:
        print(f"获取总结内容时出错: {e}")
        return jsonify({'error': str(e)}), 500

# 删除任务总结的API
@app.route('/api/delete_summary/<task_id>', methods=['DELETE'])
def delete_summary(task_id):
    """删除指定的任务总结"""
    try:
        if task_id in TASK_SUMMARIES:
            # 从内存中删除
            del TASK_SUMMARIES[task_id]
            # 同时删除文件
            delete_summary_file(task_id)
            return jsonify({'success': True, 'message': f'任务总结 {task_id} 已删除'})
        else:
            return jsonify({'success': False, 'message': f'任务总结 {task_id} 不存在'}), 404
    except Exception as e:
        print(f"删除任务总结时出错: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# 新增：批量启动多个爬虫任务的API
@app.route('/api/start_multiple_crawlers', methods=['POST'])
def start_multiple_crawlers():
    """批量启动多个爬虫任务"""
    data = request.get_json()
    crawler_configs = data.get('crawler_configs', [])
    
    if not crawler_configs:
        return jsonify({'success': False, 'message': '没有提供爬虫配置'}), 400
    
    created_tasks = []
    
    for config in crawler_configs:
        crawler_type = config.get('crawler_type')
        max_pages = config.get('max_pages', 10)
        
        if not crawler_type:
            continue
        
        task_id = "task-" + str(uuid.uuid4())
        logger = WebSocketLogger(socketio, task_id)
        
        CRAWLER_TASKS[task_id] = {
            'status': 'starting',
            'logger': logger,
            'crawler': None,
            'start_time': datetime.now(),
            'end_time': None,
            'crawler_type': crawler_type,
            'max_pages': max_pages,
            'progress': {'current': 0, 'total': 0, 'percentage': 0}
        }
        
        logger.log(f"批量任务 {task_id} 已创建，准备启动...")
        gevent.spawn(run_crawler_thread, task_id, crawler_type, max_pages)
        
        created_tasks.append({
            'task_id': task_id,
            'crawler_type': crawler_type,
            'max_pages': max_pages
        })
    
    return jsonify({
        'success': True, 
        'message': f'成功创建 {len(created_tasks)} 个爬虫任务',
        'tasks': created_tasks
    })

# 新增：批量停止多个爬虫任务的API
@app.route('/api/stop_multiple_crawlers', methods=['POST'])
def stop_multiple_crawlers():
    """批量停止多个爬虫任务"""
    data = request.get_json()
    task_ids = data.get('task_ids', [])
    
    if not task_ids:
        return jsonify({'success': False, 'message': '没有提供任务ID'}), 400
    
    results = []
    
    for task_id in task_ids:
        task = CRAWLER_TASKS.get(task_id)
        if not task:
            results.append({'task_id': task_id, 'success': False, 'message': '任务不存在'})
            continue
        
        if task['status'] == 'running' and task.get('crawler'):
            task['crawler'].stop()
            task['status'] = 'stopping'
            results.append({'task_id': task_id, 'success': True, 'message': '停止信号已发送'})
        else:
            results.append({'task_id': task_id, 'success': False, 'message': '任务不在运行状态'})
    
    successful_stops = sum(1 for r in results if r['success'])
    
    return jsonify({
        'success': True,
        'message': f'成功停止 {successful_stops} 个任务',
        'results': results
    })

@socketio.on('connect')
def handle_connect():
    print(f"客户端已连接: {request.sid}")
    emit('connected', {'data': '连接成功，请加入任务房间'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"客户端已断开连接: {request.sid}")

@socketio.on('join_task_room')
def handle_join_task_room(data):
    task_id = data.get('task_id')
    if task_id in CRAWLER_TASKS:
        join_room(task_id)
        print(f"[DEBUG] 客户端 {request.sid} 已加入任务房间: {task_id}")
        print(f"[DEBUG] 当前任务状态: {CRAWLER_TASKS.get(task_id, {}).get('status', 'unknown')}")
        # 发送确认消息到任务房间
        emit('joined_task_room', {'task_id': task_id, 'message': f'已加入任务 {task_id} 的房间'}, room=task_id)
    else:
        print(f"客户端 {request.sid} 尝试加入不存在的任务房间: {task_id}")
        emit('log_message', {
            'timestamp': datetime.now().strftime('%H:%M:%S'), 
            'level': 'error',
            'message': f'尝试加入一个不存在的任务房间: {task_id}',
            'task_id': task_id
        })

@socketio.on('join_global_room')
def handle_join_global_room():
    """客户端加入全局房间，用于接收所有任务的状态更新"""
    join_room('global')
    print(f"客户端 {request.sid} 已加入全局房间")
    emit('joined_global_room', {'message': '已加入全局房间，可以接收所有任务的状态更新'})

@socketio.on('save_task_summary')
def handle_save_task_summary(data):
    """保存任务总结报告到专门的数据结构"""
    try:
        print(f"[DEBUG] 收到save_task_summary事件")
        print(f"[DEBUG] 事件数据keys: {list(data.keys()) if data else 'None'}")
        
        task_id = data.get('task_id')
        summary = data.get('summary')
        stats = data.get('stats', {})
        end_time = data.get('end_time')
        crawler_type = data.get('crawler_type', 'unknown')
        
        print(f"[DEBUG] 解析的数据: task_id={task_id}, summary长度={len(summary) if summary else 0}, crawler_type={crawler_type}")
        
        if task_id and summary:
            # 获取爬虫类型的中文名称
            crawler_type_names = CRAWLER_TYPE_NAMES
            
            # 保存总结报告
            TASK_SUMMARIES[task_id] = {
                'task_id': task_id,
                'summary': summary,
                'stats': stats,
                'end_time': end_time,
                'crawler_type': crawler_type,
                'crawler_name': crawler_type_names.get(crawler_type, '未知'),
                'save_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 同时保存到文件
            save_summary_to_file(task_id, TASK_SUMMARIES[task_id])
            
            print(f"[DEBUG] 已保存任务 {task_id} 的总结报告到数据结构")
            print(f"[DEBUG] TASK_SUMMARIES 现在包含: {list(TASK_SUMMARIES.keys())}")
        else:
            print(f"[DEBUG] 数据不完整，无法保存。task_id={task_id}, summary存在={bool(summary)}")
            
    except Exception as e:
        print(f"[DEBUG] 保存总结报告时出错: {e}")
        import traceback
        print(f"[DEBUG] 错误详情: {traceback.format_exc()}")

@socketio.on('get_all_tasks_realtime')
def handle_get_all_tasks_realtime():
    """实时获取所有任务状态"""
    tasks_info = []
    for task_id, task_data in CRAWLER_TASKS.items():
        # 计算运行时间
        if task_data['start_time']:
            if task_data['end_time']:
                duration = task_data['end_time'] - task_data['start_time']
            else:
                duration = datetime.now() - task_data['start_time']
            duration_str = str(duration).split('.')[0]
        else:
            duration_str = "0:00:00"
        
        # 获取爬虫类型的中文名称
        crawler_type_names = CRAWLER_TYPE_NAMES
        
        task_info = {
            'task_id': task_id,
            'status': task_data['status'],
            'crawler_type': task_data.get('crawler_type', 'unknown'),
            'crawler_name': crawler_type_names.get(task_data.get('crawler_type', ''), '未知'),
            'start_time': task_data['start_time'].strftime('%Y-%m-%d %H:%M:%S') if task_data['start_time'] else None,
            'end_time': task_data['end_time'].strftime('%Y-%m-%d %H:%M:%S') if task_data['end_time'] else None,
            'duration': duration_str,
            'max_pages': task_data.get('max_pages'),
            'progress': task_data.get('progress', {'current': 0, 'total': 0, 'percentage': 0})
        }
        tasks_info.append(task_info)
    
    # 按开始时间排序
    tasks_info.sort(key=lambda x: x['start_time'] if x['start_time'] else '', reverse=True)
    
    emit('all_tasks_update', {'tasks': tasks_info})

@app.route('/api/get_files')
def get_files():
    """获取指定目录下的文件列表。如果未指定目录，则返回默认目录集合的所有文件。"""
    dir_param = request.args.get('dir')  # 相对于项目根目录的路径

    files_info = []
    base_dir = os.path.abspath(os.getcwd())

    def collect_files(target_dir, type_label=None):
        for root, _, files in os.walk(target_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                if not os.path.isfile(file_path):
                    continue
                rel_path = os.path.relpath(file_path, base_dir).replace('\\', '/')
                stat = os.stat(file_path)
                files_info.append({
                    'name': filename,
                    'path': rel_path,
                    'size': stat.st_size,
                    'mtime': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'type': type_label or os.path.basename(os.path.dirname(file_path))
                })

    if dir_param:
        abs_dir = os.path.abspath(os.path.join(base_dir, dir_param))
        if not abs_dir.startswith(base_dir) or not os.path.exists(abs_dir):
            return jsonify({'error': '非法目录'}), 400
        collect_files(abs_dir)
    else:
        # 汇总预定义目录
        download_dirs = DOWNLOAD_DIRS
        for type_label, path in download_dirs.items():
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                collect_files(abs_path, type_label)

    files_info.sort(key=lambda x: x['mtime'], reverse=True)
    return jsonify({'files': files_info})

@app.route('/api/download_file/<path:filepath>')
def download_file(filepath):
    # 构建安全的文件路径
    base_dir = os.path.abspath(os.path.dirname(__name__))
    safe_path = os.path.join(base_dir, filepath)
    # 检查路径是否仍然在项目目录内，防止目录遍历攻击
    if not safe_path.startswith(base_dir):
        return jsonify({'error': '非法路径'}), 400
    try:
        return send_file(safe_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/download_all')
def download_all():
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                download_dirs = DOWNLOAD_DIRS
                for type, path in download_dirs.items():
                    abs_path = os.path.abspath(path)
                    if not os.path.exists(abs_path): continue
                    for root, _, files in os.walk(abs_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            # 创建在zip文件中的相对路径
                            archive_name = os.path.join(type, os.path.relpath(file_path, abs_path))
                            zipf.write(file_path, archive_name)
            return send_file(temp_zip.name, as_attachment=True, download_name='爬虫下载文件.zip')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_logs')
def get_logs():
    log_files_info = []
    if not os.path.exists(LOGS_DIR):
        return jsonify({'logs': []})
    
    try:
        log_files = sorted(
            os.listdir(LOGS_DIR),
            key=lambda f: os.path.getmtime(os.path.join(LOGS_DIR, f)),
            reverse=True
        )
        
        for filename in log_files:
            if filename.endswith('.log'):
                file_path = os.path.join(LOGS_DIR, filename)
                stat = os.stat(file_path)
                log_files_info.append({
                    'name': filename,
                    'size': stat.st_size,
                    'mtime': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
        return jsonify({'logs': log_files_info})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_log_content/<path:filename>')
def get_log_content(filename):
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'error': '非法文件名'}), 400
    
    safe_path = os.path.join(LOGS_DIR, filename)
    
    try:
        if not os.path.abspath(safe_path).startswith(os.path.abspath(LOGS_DIR)):
            return jsonify({'error': '非法路径'}), 400
            
        with open(safe_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'name': filename, 'content': content})
    except FileNotFoundError:
        return jsonify({'error': '日志文件未找到'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_log/<path:filename>', methods=['DELETE'])
def delete_log(filename):
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'error': '非法文件名'}), 400
        
    safe_path = os.path.join(LOGS_DIR, filename)
    
    try:
        if not os.path.abspath(safe_path).startswith(os.path.abspath(LOGS_DIR)):
            return jsonify({'error': '非法路径'}), 400
        
        if os.path.exists(safe_path):
            os.remove(safe_path)
            return jsonify({'success': True, 'message': f'日志文件 {filename} 已删除'})
        else:
            return jsonify({'success': False, 'message': '文件不存在'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== 知识库相关API ====================

@app.route('/api/get_knowledge_bases', methods=['GET'])
def get_knowledge_bases():
    """获取知识库列表"""
    try:
        # 构建API URL
        config = KNOWLEDGE_BASE_CONFIG
        kb_api_url = config["base_url"] + config["list_api"]
        headers = get_knowledge_base_headers()
        
        # 请求参数
        params = {
            "page": 1,
            "page_size": 20,
            "keywords": ""
        }
        
        # 发送POST请求
        response = requests.post(
            kb_api_url, 
            headers=headers, 
            json={}, 
            params=params, 
            timeout=config["timeout"]["list"]
        )
        
        if response.status_code == 200:
            kb_data = response.json()
            if kb_data.get('code') == 0:
                kbs = kb_data.get('data', {}).get('kbs', [])
                return jsonify({
                    'success': True,
                    'kbs': kbs,
                    'total': len(kbs)
                })
            else:
                return jsonify({
                    'success': False,
                    'message': kb_data.get('message', '获取知识库列表失败')
                })
        else:
            return jsonify({
                'success': False,
                'message': f'API请求失败，状态码: {response.status_code}'
            })
            
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'message': '请求知识库API超时'
        })
    except Exception as e:
        print(f"获取知识库列表时出错: {e}")
        return jsonify({
            'success': False,
            'message': f'获取知识库列表时发生错误: {str(e)}'
        })

@app.route('/api/upload_to_knowledge_base', methods=['POST'])
def upload_to_knowledge_base():
    """上传文件到知识库"""
    try:
        data = request.get_json()
        kb_id = data.get('kb_id')
        file_path = data.get('file_path')
        file_name = data.get('file_name')
        
        if not kb_id or not file_path or not file_name:
            return jsonify({
                'success': False,
                'message': '缺少必要参数: kb_id, file_path, file_name'
            })
        
        # 构建完整的文件路径
        base_dir = os.path.abspath(os.getcwd())
        full_file_path = os.path.join(base_dir, file_path)
        
        # 安全检查：确保文件路径在项目目录内
        if not full_file_path.startswith(base_dir):
            return jsonify({
                'success': False,
                'message': '非法的文件路径'
            })
        
        # 检查文件是否存在
        if not os.path.exists(full_file_path):
            return jsonify({
                'success': False,
                'message': f'文件不存在: {file_path}'
            })
        
        # 获取配置
        config = KNOWLEDGE_BASE_CONFIG
        
        # 获取文件大小
        file_size = os.path.getsize(full_file_path)
        
        # 检查文件大小限制
        max_size = config["file_limits"]["max_size_mb"] * 1024 * 1024
        if file_size > max_size:
            return jsonify({
                'success': False,
                'message': f'文件过大，最大支持{config["file_limits"]["max_size_mb"]}MB'
            })
        
        # 检查文件类型是否支持
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in config["file_limits"]["allowed_types"]:
            return jsonify({
                'success': False,
                'message': f'不支持的文件类型: {ext}，支持的类型: {", ".join(config["file_limits"]["allowed_types"])}'
            })
        
        # 确定文件的MIME类型
        mime_type = get_mime_type(file_name)
        
        # 准备上传API请求
        upload_api_url = config["base_url"] + config["upload_api"]
        headers = get_knowledge_base_headers()
        # 移除Content-Type，让requests自动处理multipart/form-data
        if "Content-Type" in headers:
            del headers["Content-Type"]
        
        # 准备文件上传的multipart/form-data
        with open(full_file_path, 'rb') as file_content:
            files = {
                'file': (file_name, file_content, mime_type)
            }
            data_form = {
                'kb_id': kb_id
            }
            
            # 发送上传请求
            response = requests.post(
                upload_api_url,
                headers=headers,
                files=files,
                data=data_form,
                timeout=config["timeout"]["upload"]
            )
        
        if response.status_code == 200:
            upload_result = response.json()
            if upload_result.get('code') == 0:
                uploaded_docs = upload_result.get('data', [])
                return jsonify({
                    'success': True,
                    'message': f'文件 "{file_name}" 上传成功',
                    'data': uploaded_docs  # 返回包含文档ID的数据
                })
            else:
                return jsonify({
                    'success': False,
                    'message': upload_result.get('message', '上传失败')
                })
        else:
            return jsonify({
                'success': False,
                'message': f'上传API请求失败，状态码: {response.status_code}'
            })
            
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'message': '上传请求超时，请稍后重试'
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'message': f'找不到文件: {file_path}'
        })
    except Exception as e:
        print(f"上传文件到知识库时出错: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'上传文件时发生错误: {str(e)}'
        })

@app.route('/api/parse_documents', methods=['POST'])
def parse_documents():
    """解析已上传的文档"""
    try:
        data = request.get_json()
        doc_ids = data.get('doc_ids', [])
        
        if not doc_ids:
            return jsonify({
                'success': False,
                'message': '缺少文档ID列表'
            })
        
        if not isinstance(doc_ids, list):
            return jsonify({
                'success': False,
                'message': '文档ID必须是列表格式'
            })
        
        # 获取配置
        config = KNOWLEDGE_BASE_CONFIG
        
        # 准备解析API请求
        parse_api_url = config["base_url"] + config["parse_api"]
        headers = get_knowledge_base_headers()
        
        # 准备解析请求数据
        parse_data = {
            "doc_ids": doc_ids,
            "run": 1,
            "delete": False
        }
        
        # 发送解析请求
        response = requests.post(
            parse_api_url,
            headers=headers,
            json=parse_data,
            timeout=config["timeout"]["parse"]  # 使用解析专用的超时时间
        )
        
        if response.status_code == 200:
            parse_result = response.json()
            if parse_result.get('code') == 0:
                return jsonify({
                    'success': True,
                    'message': f'成功启动 {len(doc_ids)} 个文档的解析任务',
                    'data': parse_result.get('data', True)
                })
            else:
                return jsonify({
                    'success': False,
                    'message': parse_result.get('message', '解析请求失败')
                })
        else:
            return jsonify({
                'success': False,
                'message': f'解析API请求失败，状态码: {response.status_code}'
            })
            
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'message': '解析请求超时，请稍后重试'
        })
    except Exception as e:
        print(f"解析文档时出错: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'解析文档时发生错误: {str(e)}'
        })

# ==================== 知识库API结束 ====================

# ---------------------------------------------------------------------------
# 新增: 获取下载目录树结构 (多级文件夹导航)
# ---------------------------------------------------------------------------

def build_dir_tree(path, base_dir):
    """递归构建目录树"""
    node = {
        'name': os.path.basename(path),
        'path': os.path.relpath(path, base_dir).replace('\\', '/'),
        'children': []
    }
    try:
        for entry in os.scandir(path):
            if entry.is_dir():
                node['children'].append(build_dir_tree(entry.path, base_dir))
    except PermissionError:
        pass
    return node

@app.route('/api/get_dir_tree')
def get_dir_tree():
    """返回多级下载目录结构，用于前端下拉框导航"""
    base_dir = os.path.abspath(os.getcwd())
    
    # 获取所有配置的目录路径
    roots = []
    for dir_path in DOWNLOAD_DIRS.values():
        abs_path = os.path.abspath(dir_path)
        if abs_path not in roots:
            roots.append(abs_path)

    tree = []
    for root in roots:
        if os.path.exists(root):
            tree.append(build_dir_tree(root, base_dir))

    return jsonify({'tree': tree})

if __name__ == '__main__':
    # 启动后台清理线程
    if platform.system() == 'Linux':
        gevent.spawn(cleanup_old_tasks)
    
    # 加载已保存的任务总结
    print("正在加载已保存的任务总结...")
    load_summaries_from_files()
    
    # 从 run.py 移过来的启动逻辑
    print("============================================================")
    print("智能文档爬虫系统")
    print("============================================================")
    env = 'production' if not app.debug else 'development'
    print(f"环境: {env}")
    print(f"调试模式: {app.debug}")
    # 在生产环境中，可以考虑移除ip显示或显示0.0.0.0
    print(f"服务地址: http://0.0.0.0:5000")
    print("============================================================")
    print("按 Ctrl+C 停止服务")
    print("============================================================")
    
    # 临时修复：确保没有语法错误
    print("系统启动完成，所有功能已就绪")
    
    socketio.run(app, host='0.0.0.0', port=5000)