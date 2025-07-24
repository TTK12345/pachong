from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import os
import time
import threading
import json
from datetime import datetime
import zipfile
import tempfile
import traceback
import platform

# 导入爬虫类
import sys
sys.path.append('./demo')
from gz_crawler_final import GzCrawler
from mem_gov_crawler_final import MemGovCrawler

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'

# 根据系统选择不同的异步模式
if platform.system() == 'Linux':
    # Linux环境使用gevent
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')
else:
    # Windows环境使用eventlet
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 全局变量存储爬虫状态
crawler_status = {
    'is_running': False,
    'current_crawler': None,
    'progress': 0,
    'total': 0,
    'current_file': '',
    'start_time': None
}

class WebSocketLogger:
    """用于向前端发送日志的类"""
    def __init__(self, socketio):
        self.socketio = socketio
    
    def log(self, message, level='info'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_data = {
            'timestamp': timestamp,
            'level': level,
            'message': str(message)
        }
        print(f"[{timestamp}] {level.upper()}: {message}")  # 同时输出到控制台
        self.socketio.emit('log_message', log_data)

# 修改后的爬虫类，专门为Linux环境优化
class WebGzCrawler(GzCrawler):
    def __init__(self, download_path="./规章", logger=None):
        self.logger = logger or WebSocketLogger(socketio)
        self.is_stopped = False
        
        # 不在初始化时调用父类构造函数，避免提前启动driver
        self.download_path = os.path.abspath(download_path)
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)
            self.logger.log(f"已创建规章文件夹: {self.download_path}")
    
    def log(self, message, level='info'):
        if self.logger:
            self.logger.log(message, level)
    
    def stop(self):
        self.is_stopped = True
        self.log("收到停止信号，正在停止爬虫...", 'warning')
    
    def update_progress(self, current, total, current_file=''):
        if self.is_stopped:
            return False
        
        progress_data = {
            'current': current,
            'total': total,
            'percentage': round((current / total) * 100, 1) if total > 0 else 0,
            'current_file': current_file
        }
        socketio.emit('progress_update', progress_data)
        return True
    
    def setup_driver(self):
        """设置并启动浏览器驱动 - Linux优化版本"""
        try:
            self.log("正在配置Chrome选项...")
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            
            # Linux环境下的Chrome选项
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # Linux服务器通常无图形界面
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--remote-debugging-port=9222')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # 下载相关配置
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("prefs", {
                "download.default_directory": self.download_path,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                "plugins.always_open_pdf_externally": True
            })
            
            self.log("正在启动Chrome浏览器...")
            
            # Selenium 4+ 会自动在系统PATH中查找并管理ChromeDriver。
            # 既然环境已配置好，我们直接让Selenium自动处理即可，无需指定路径。
            # 这会消除所有不必要的警告日志，并使代码更简洁。
            self.driver = webdriver.Chrome(options=chrome_options)
            
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            from selenium.webdriver.support.ui import WebDriverWait
            self.wait = WebDriverWait(self.driver, 20)
            
            self.log("浏览器驱动已成功启动", 'success')
            return True
            
        except Exception as e:
            error_msg = f"启动浏览器驱动失败: {str(e)}"
            self.log(error_msg, 'error')
            self.log(f"详细错误: {traceback.format_exc()}", 'error')
            return False
    
    def crawl_all(self, main_url=None, max_docs=None, max_pages=10):
        global crawler_status
        
        try:
            crawler_status['is_running'] = True
            crawler_status['start_time'] = datetime.now()
            
            self.log("开始初始化爬虫...")
            
            # 设置Chrome选项和启动driver
            if not self.setup_driver():
                self.log("无法启动浏览器，爬虫终止", 'error')
                return
            
            if self.is_stopped:
                self.log("爬虫已被停止", 'warning')
                return
            
            self.log(f"开始爬取页面，最大页面数: {max_pages}")
            all_documents = self.get_all_documents(max_pages)
            
            if not all_documents:
                self.log("未找到任何规章文档", 'warning')
                return
            
            if max_docs:
                all_documents = all_documents[:max_docs]
                self.log(f"将处理前 {max_docs} 个文档")
            
            total_docs = len(all_documents)
            self.log(f"找到 {total_docs} 个文档，开始下载...")
            
            success_count = 0
            fail_count = 0
            
            for i, doc_info in enumerate(all_documents, 1):
                if self.is_stopped:
                    self.log("爬虫已停止", 'warning')
                    break
                
                # 更新进度
                if not self.update_progress(i, total_docs, doc_info['name']):
                    break
                
                self.log(f"进度: {i}/{total_docs} - 第{doc_info.get('page_num', '?')}页")
                
                try:
                    success = self.download_document(doc_info)
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    self.log(f"下载文档时出错: {str(e)}", 'error')
                    fail_count += 1
                
                time.sleep(3)
            
            self.log(f"爬取完成！成功: {success_count}, 失败: {fail_count}", 'success')
            
        except Exception as e:
            error_msg = f"爬取过程中出错: {str(e)}"
            self.log(error_msg, 'error')
            self.log(f"详细错误信息: {traceback.format_exc()}", 'error')
        finally:
            try:
                if hasattr(self, 'driver') and self.driver:
                    self.driver.quit()
                    self.log("浏览器已关闭")
            except:
                pass
            
            crawler_status['is_running'] = False
            crawler_status['current_crawler'] = None
            socketio.emit('crawler_completed', {'message': '爬虫任务结束'})

class WebMemGovCrawler(MemGovCrawler):
    def __init__(self, download_path="./法律法规", logger=None):
        self.logger = logger or WebSocketLogger(socketio)
        self.is_stopped = False
        
        # 不在初始化时调用父类构造函数
        self.download_path = os.path.abspath(download_path)
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)
            self.logger.log(f"已创建法律法规文件夹: {self.download_path}")
    
    def log(self, message, level='info'):
        if self.logger:
            self.logger.log(message, level)
    
    def stop(self):
        self.is_stopped = True
        self.log("收到停止信号，正在停止爬虫...", 'warning')
    
    def update_progress(self, current, total, current_file=''):
        if self.is_stopped:
            return False
        
        progress_data = {
            'current': current,
            'total': total,
            'percentage': round((current / total) * 100, 1) if total > 0 else 0,
            'current_file': current_file
        }
        socketio.emit('progress_update', progress_data)
        return True
    
    def setup_driver(self):
        """设置并启动浏览器驱动 - Linux优化版本"""
        try:
            self.log("正在配置Chrome选项...")
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # Linux服务器通常无图形界面
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_experimental_option("prefs", {
                "download.default_directory": self.download_path,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            })
            
            self.log("正在启动Chrome浏览器...")
            
            # 同样，此处我们也让Selenium自动管理驱动，
            # 删除所有硬编码路径和try-except回退逻辑。
            self.driver = webdriver.Chrome(options=chrome_options)

            # 设置页面加载超时，防止 driver.get() 无限期等待
            self.driver.set_page_load_timeout(60)
            
            from selenium.webdriver.support.ui import WebDriverWait
            self.wait = WebDriverWait(self.driver, 30)
            
            self.log("浏览器驱动已成功启动", 'success')
            return True
            
        except Exception as e:
            error_msg = f"启动浏览器驱动失败: {str(e)}"
            self.log(error_msg, 'error')
            self.log(f"详细错误: {traceback.format_exc()}", 'error')
            return False
    
    def crawl_all(self, main_url, max_links=None):
        global crawler_status
        
        try:
            crawler_status['is_running'] = True
            crawler_status['start_time'] = datetime.now()
            
            self.log("开始初始化爬虫...")
            
            # 设置Chrome选项和启动driver
            if not self.setup_driver():
                self.log("无法启动浏览器，爬虫终止", 'error')
                return
            
            if self.is_stopped:
                self.log("爬虫已被停止", 'warning')
                return
            
            self.log(f"准备访问主页面: {main_url}")
            sub_links = []
            try:
                self.log("正在获取所有子链接，此过程可能需要一些时间...")
                sub_links = self.get_sub_links(main_url)
                self.log("成功获取所有子链接。")
            except Exception as e:
                self.log(f"获取子链接列表时出错: {e}", 'error')
                self.log(f"请检查网络连接或目标网站 '{main_url}' 是否可访问。", 'error')
                self.log(f"详细错误: {traceback.format_exc()}", 'error')
                # 出错后也需要执行 finally
                raise
            
            if not sub_links:
                self.log("未找到任何子链接", 'warning')
                return
            
            if max_links:
                sub_links = sub_links[:max_links]
                self.log(f"将处理前 {max_links} 个链接")
            
            total_links = len(sub_links)
            self.log(f"找到 {total_links} 个链接，开始下载...")
            
            for i, sub_link in enumerate(sub_links, 1):
                if self.is_stopped:
                    self.log("爬虫已停止", 'warning')
                    break
                
                # 更新进度
                if not self.update_progress(i, total_links, sub_link['title']):
                    break
                
                self.log(f"进度: {i}/{total_links}")
                try:
                    self.download_pdf_from_sublink(sub_link)
                except Exception as e:
                    self.log(f"下载文档时出错: {str(e)}", 'error')
                
                time.sleep(2)
            
            self.log("爬取完成！", 'success')
            
        except Exception as e:
            error_msg = f"爬取过程中出错: {str(e)}"
            self.log(error_msg, 'error')
            self.log(f"详细错误信息: {traceback.format_exc()}", 'error')
        finally:
            try:
                if hasattr(self, 'driver') and self.driver:
                    self.driver.quit()
                    self.log("浏览器已关闭")
            except:
                pass
            
            crawler_status['is_running'] = False
            crawler_status['current_crawler'] = None
            socketio.emit('crawler_completed', {'message': '爬虫任务结束'})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start_crawler', methods=['POST'])
def start_crawler():
    global crawler_status
    
    if crawler_status['is_running']:
        return jsonify({'success': False, 'message': '爬虫正在运行中'})
    
    data = request.get_json()
    crawler_type = data.get('crawler_type')
    max_docs = data.get('max_docs')
    max_pages = data.get('max_pages', 10)
    
    def run_crawler():
        global crawler_status
        
        try:
            logger = WebSocketLogger(socketio)
            logger.log("正在启动爬虫线程...")
            
            if crawler_type == 'gz':
                crawler = WebGzCrawler(logger=logger)
                crawler_status['current_crawler'] = crawler
                crawler.crawl_all(max_docs=max_docs, max_pages=max_pages)
            elif crawler_type == 'memgov':
                crawler = WebMemGovCrawler(logger=logger)
                crawler_status['current_crawler'] = crawler
                main_url = "https://www.mem.gov.cn/fw/flfgbz/fg/"
                crawler.crawl_all(main_url, max_links=max_docs)
            else:
                logger.log(f"未知的爬虫类型: {crawler_type}", 'error')
                
        except Exception as e:
            error_msg = f'爬虫执行出错: {str(e)}'
            print(f"爬虫线程异常: {error_msg}")
            print(f"详细错误: {traceback.format_exc()}")
            socketio.emit('log_message', {
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'level': 'error',
                'message': error_msg
            })
        finally:
            crawler_status['is_running'] = False
            crawler_status['current_crawler'] = None
    
    # 在新线程中运行爬虫
    thread = threading.Thread(target=run_crawler, daemon=True)
    thread.start()
    
    return jsonify({'success': True, 'message': '爬虫已启动'})

@app.route('/api/stop_crawler', methods=['POST'])
def stop_crawler():
    global crawler_status
    
    if not crawler_status['is_running']:
        return jsonify({'success': False, 'message': '没有正在运行的爬虫'})
    
    if crawler_status['current_crawler']:
        crawler_status['current_crawler'].stop()
    
    return jsonify({'success': True, 'message': '停止信号已发送'})

@app.route('/api/get_files')
def get_files():
    """获取已下载的文件列表"""
    files_info = []
    
    # 检查规章文件夹
    gz_path = os.path.abspath("./规章")
    if os.path.exists(gz_path):
        for filename in os.listdir(gz_path):
            if os.path.isfile(os.path.join(gz_path, filename)):
                file_path = os.path.join(gz_path, filename)
                file_stat = os.stat(file_path)
                files_info.append({
                    'name': filename,
                    'path': f'规章/{filename}',
                    'size': file_stat.st_size,
                    'mtime': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'type': '规章'
                })
    
    # 检查法律法规文件夹
    law_path = os.path.abspath("./法律法规")
    if os.path.exists(law_path):
        for filename in os.listdir(law_path):
            if os.path.isfile(os.path.join(law_path, filename)):
                file_path = os.path.join(law_path, filename)
                file_stat = os.stat(file_path)
                files_info.append({
                    'name': filename,
                    'path': f'法律法规/{filename}',
                    'size': file_stat.st_size,
                    'mtime': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'type': '法律法规'
                })
    
    # 按修改时间排序
    files_info.sort(key=lambda x: x['mtime'], reverse=True)
    
    return jsonify({'files': files_info})

@app.route('/api/download_file/<path:filepath>')
def download_file(filepath):
    """下载单个文件"""
    try:
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/download_all')
def download_all():
    """打包下载所有文件"""
    try:
        # 创建临时zip文件
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加规章文件
            gz_path = os.path.abspath("./规章")
            if os.path.exists(gz_path):
                for filename in os.listdir(gz_path):
                    file_path = os.path.join(gz_path, filename)
                    if os.path.isfile(file_path):
                        zipf.write(file_path, f'规章/{filename}')
            
            # 添加法律法规文件
            law_path = os.path.abspath("./法律法规")
            if os.path.exists(law_path):
                for filename in os.listdir(law_path):
                    file_path = os.path.join(law_path, filename)
                    if os.path.isfile(file_path):
                        zipf.write(file_path, f'法律法规/{filename}')
        
        return send_file(temp_zip.name, as_attachment=True, 
                        download_name='爬虫下载文件.zip',
                        mimetype='application/zip')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    print('客户端已连接')
    emit('connected', {'data': '连接成功'})

@socketio.on('disconnect')
def handle_disconnect():
    print('客户端已断开连接')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000) 
