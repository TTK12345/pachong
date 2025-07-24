import time
import os
import re
from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
import requests
from datetime import datetime

class BaseCrawler(ABC):
    """
    基础爬虫类，包含所有爬虫的共同功能
    """
    
    def __init__(self, download_path, logger=None, task_id=None, socketio=None, progress_callback=None):
        """
        初始化爬虫
        :param download_path: 下载文件保存路径
        :param logger: 日志记录器
        :param task_id: 任务ID（Web版本使用）
        :param socketio: SocketIO实例（Web版本使用）
        :param progress_callback: 进度更新回调函数
        """
        self.download_path = os.path.abspath(download_path)
        self.logger = logger
        self.task_id = task_id
        self.socketio = socketio
        self.progress_callback = progress_callback
        self.is_stopped = False  # 停止标志
        
        # 创建下载目录
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)
            self.log(f"已创建下载文件夹: {self.download_path}")
        
        # 浏览器相关
        self.driver = None
        self.wait = None
        self.chrome_options = self._setup_chrome_options()
        
        # 统计信息
        self.stats = {
            'total_pages': 0,
            'total_sub_links': 0,
            'total_documents': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'pages_processed': [],
            'failed_links': []
        }
        
        # 进度统计
        self.total_sub_links_count = 0  # 总子链接数量
        self.completed_sub_links_count = 0  # 已完成子链接数量
    
    def _setup_chrome_options(self):
        """设置Chrome浏览器选项"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("prefs", {
            "download.default_directory": self.download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "plugins.always_open_pdf_externally": True
        })
        return options

    def log(self, message, level='info'):
        """记录日志信息"""
        if self.logger:
            self.logger.log(message, level)

    def update_progress(self, current, total, current_file=''):
        """
        更新进度信息
        :param current: 当前进度
        :param total: 总数
        :param current_file: 当前处理的文件（可选）
        """
        # 如果任务被停止，返回False
        if self.is_stopped:
            return False
            
        # 如果是Web版本，发送WebSocket更新
        if self.task_id and self.socketio:
            progress_data = {
                'current': current,
                'total': total,
                'percentage': round((current / total) * 100, 1) if total > 0 else 0,
                'current_file': current_file,
                'task_id': self.task_id
            }
            
            # 使用回调函数更新CRAWLER_TASKS
            if self.progress_callback:
                self.progress_callback(self.task_id, progress_data)
            
            # 发送WebSocket更新
            self.socketio.emit('progress_update', progress_data, room=self.task_id)
            
        return True

    def stop(self):
        """停止爬虫"""
        self.is_stopped = True
        self.log("收到停止信号，正在停止爬虫...", 'warning')
    
    def count_all_sub_links(self, base_url, max_pages=None):
        """
        统计所有页面的子链接数量（统一多页面逻辑）
        :param base_url: 基础URL
        :param max_pages: 最大页数
        :return: 总子链接数量
        """
        try:
            if not self.driver:
                self.start_driver()
            
            total_count = 0
            page_count = 0
            # 当max_pages为0时表示无限制，设为很大的数
            if max_pages == 0:
                max_pages = 999999
            elif max_pages is None:
                max_pages = 10
            
            while page_count < max_pages:
                current_url = self.generate_page_url(base_url, page_count)
                
                # 检查页面是否存在
                if not self.check_page_exists(current_url):
                    if page_count == 0:
                        self.log(f"第一页不存在: {current_url}", 'error')
                    else:
                        self.log(f"第 {page_count + 1} 页不存在，停止统计", 'info')
                    break
                
                # 获取当前页面的子链接
                sub_links = self.get_sub_links(current_url)
                
                if sub_links:
                    page_link_count = len(sub_links)
                    total_count += page_link_count
                    self.log(f"第 {page_count + 1} 页: {page_link_count} 个子链接", 'info')
                else:
                    self.log(f"第 {page_count + 1} 页: 0 个子链接", 'info')
                
                page_count += 1
                
                # 如果连续几页都没有子链接，则停止
                if not sub_links and page_count > 2:
                    self.log("连续页面无子链接，停止统计", 'info')
                    break
            
            self.log(f"统计完成：共 {page_count} 页，总计 {total_count} 个子链接", 'info')
            return total_count
            
        except Exception as e:
            self.log(f"统计子链接数量时出错: {e}", 'error')
            return 0
    
    def update_sub_link_progress(self, increment=1):
        """
        更新子链接进度
        :param increment: 增加的完成数量
        """
        self.completed_sub_links_count += increment
        self.update_progress(
            current=self.completed_sub_links_count,
            total=self.total_sub_links_count,
            current_file=f"已完成 {self.completed_sub_links_count}/{self.total_sub_links_count} 个链接"
        )
    
    def start_driver(self):
        """启动浏览器驱动"""
        try:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 20)
            self.log("浏览器驱动已启动")
        except Exception as e:
            self.log(f"启动浏览器驱动失败: {e}", 'error')
            raise
    
    def close_driver(self):
        """关闭浏览器驱动"""
        if self.driver:
            self.driver.quit()
            self.log("浏览器驱动已关闭")
    
    def clean_filename(self, filename):
        """
        清理文件名，移除不合法的字符
        :param filename: 原始文件名
        :return: 清理后的文件名
        """
        # 移除或替换不合法的字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 移除多余的空格
        filename = re.sub(r'\s+', '_', filename.strip())
        # 移除多余的下划线
        filename = re.sub(r'_+', '_', filename)
        filename = filename.strip('_')
        # 限制文件名长度
        if len(filename) > 100:
            filename = filename[:100]
        return filename
    
    def get_files_in_directory(self):
        """
        获取下载目录中的所有文件
        :return: 文件列表（文件名和修改时间）
        """
        files = []
        try:
            for filename in os.listdir(self.download_path):
                if os.path.isfile(os.path.join(self.download_path, filename)):
                    file_path = os.path.join(self.download_path, filename)
                    files.append({
                        'name': filename,
                        'path': file_path,
                        'mtime': os.path.getmtime(file_path)
                    })
        except Exception as e:
            self.log(f"获取文件列表时出错: {e}", 'error')
        return files
    
    def wait_for_download_complete(self, initial_files, timeout=30):
        """
        等待下载完成，并返回新下载的文件
        :param initial_files: 下载前的文件列表
        :param timeout: 超时时间（秒）
        :return: 新下载的文件信息
        """
        start_time = time.time()
        self.log(f"开始等待下载完成，超时时间: {timeout}秒")
        
        while time.time() - start_time < timeout:
            current_files = self.get_files_in_directory()
            
            # 查找新文件
            new_files = []
            for current_file in current_files:
                is_new = True
                for initial_file in initial_files:
                    if current_file['name'] == initial_file['name']:
                        is_new = False
                        break
                if is_new:
                    new_files.append(current_file)
            
            # 检查是否有新文件且文件不再变化（下载完成）
            if new_files:
                self.log(f"检测到 {len(new_files)} 个新文件")
                # 等待一段时间确保文件下载完成
                time.sleep(3)
                stable_files = []
                for new_file in new_files:
                    # 检查文件是否不再变化（下载完成）
                    if not new_file['name'].endswith('.crdownload') and not new_file['name'].endswith('.tmp'):
                        stable_files.append(new_file)
                        self.log(f"发现稳定文件: {new_file['name']}")
                
                if stable_files:
                    return stable_files
            
            time.sleep(1)
        
        self.log(f"等待超时，未检测到新文件", 'warning')
        return []
    
    def rename_downloaded_file(self, file_info, new_name):
        """
        重命名下载的文件
        :param file_info: 文件信息字典
        :param new_name: 新的文件名（不包含扩展名）
        """
        try:
            old_path = file_info['path']
            old_name = file_info['name']
            
            # 获取文件扩展名
            _, ext = os.path.splitext(old_name)
            if not ext:
                # 根据文件内容或名称判断扩展名
                if 'pdf' in old_name.lower():
                    ext = '.pdf'
                elif 'doc' in old_name.lower():
                    ext = '.doc'
                elif 'wps' in old_name.lower():
                    ext = '.wps'
                else:
                    ext = '.pdf'  # 默认为PDF格式
            
            # 清理新文件名
            clean_name = self.clean_filename(new_name)
            
            # 构造新文件路径
            new_filename = f"{clean_name}{ext}"
            new_path = os.path.join(self.download_path, new_filename)
            
            # 如果文件已存在，直接覆盖
            if os.path.exists(new_path):
                self.log(f"文件已存在，将覆盖: {new_filename}")
                os.remove(new_path)
            
            # 重命名文件
            os.rename(old_path, new_path)
            self.log(f"文件已重命名: {old_name} -> {new_filename}")
            return new_path
            
        except Exception as e:
            self.log(f"重命名文件时出错: {e}", 'error')
            return file_info['path']
    
    def download_pdf_directly_from_url(self, pdf_url, title, additional_info=""):
        """
        直接从URL下载PDF文件
        :param pdf_url: PDF文件URL
        :param title: 文档标题
        :param additional_info: 额外信息
        :return: 是否下载成功
        """
        try:
            self.log(f"尝试直接下载PDF: {pdf_url}")
            
            # 设置请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(pdf_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 生成文件名
            filename_parts = [title]
            if additional_info:
                filename_parts.append(additional_info)
            
            clean_title = self.clean_filename("_".join(filename_parts))
            filename = f"{clean_title}.pdf"
            filepath = os.path.join(self.download_path, filename)
            
            # 如果文件已存在，直接覆盖
            if os.path.exists(filepath):
                self.log(f"文件已存在，将覆盖: {filename}")
                os.remove(filepath)
            
            # 保存文件
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            self.log(f"PDF下载成功: {filename}", 'success')
            return True
            
        except Exception as e:
            self.log(f"直接下载PDF失败: {e}", 'error')
            return False
    
    def try_download_buttons(self):
        """
        尝试点击各种可能的下载按钮
        """
        download_button_selectors = [
            "//button[contains(text(), '下载')]",
            "//a[contains(text(), '下载')]",
            "//button[contains(@class, 'download')]",
            "//a[contains(@class, 'download')]",
            "//button//span[contains(text(), '下载')]",
            "//div[contains(@class, 'download')]//button",
            "//a[contains(text(), 'PDF')]",
            "//a[contains(text(), '附件')]",
            "//span[contains(text(), '下载')]/parent::a",
            "//div[contains(@class, 'download')]//a"
        ]
        
        for selector in download_button_selectors:
            try:
                download_btn = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                download_btn.click()
                self.log(f"成功点击下载按钮: {selector}")
                time.sleep(2)
                return True
            except Exception:
                continue
        
        # 如果都失败了，尝试键盘快捷键
        try:
            self.log("尝试使用Ctrl+S快捷键...")
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.CONTROL + 's')
            time.sleep(2)
            return True
        except Exception as e:
            self.log(f"快捷键下载失败: {e}", 'error')
            return False
    
    def check_page_exists(self, url):
        """
        检查页面是否存在
        :param url: 页面URL
        :return: 页面是否存在
        """
        try:
            response = requests.get(url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def save_page_content(self, url, title):
        """
        保存页面内容为HTML文件
        :param url: 页面URL
        :param title: 页面标题
        :return: 是否保存成功
        """
        try:
            self.log("保存页面内容为HTML文件...")
            
            # 获取页面源码
            page_source = self.driver.page_source
            
            # 生成文件名
            clean_title = self.clean_filename(title)
            filename = f"{clean_title}.html"
            filepath = os.path.join(self.download_path, filename)
            
            # 如果文件已存在，直接覆盖
            if os.path.exists(filepath):
                self.log(f"文件已存在，将覆盖: {filename}")
            
            # 保存文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(page_source)
            
            self.log(f"页面内容保存成功: {filename}", 'success')
            return True
            
        except Exception as e:
            self.log(f"保存页面内容失败: {e}", 'error')
            return False
    
    def print_summary_report(self):
        """
        输出详细的总结报告
        """
        self.log("开始生成总结报告...", 'info')
        summary_lines = []
        
        def add_line(txt):
            summary_lines.append(txt)
            self.log(txt)
        
        try:
            add_line("\n" + "="*60)
            add_line("爬取任务总结报告")
            add_line("="*60)
            
            add_line("\n📊 基本统计信息:")
            add_line(f"   总页数: {self.stats.get('total_pages', 0)}")
            add_line(f"   总子链接数: {self.stats.get('total_sub_links', 0)}")
            add_line(f"   总文档数: {self.stats.get('total_documents', 0)}")
            add_line(f"   成功下载数: {self.stats.get('successful_downloads', 0)}")
            add_line(f"   失败下载数: {self.stats.get('failed_downloads', 0)}")
            
            total_docs = self.stats.get('total_documents', 0)
            successful_docs = self.stats.get('successful_downloads', 0)
            if total_docs > 0:
                success_rate = (successful_docs / total_docs) * 100
                add_line(f"   下载成功率: {success_rate:.1f}%")
            else:
                add_line(f"   下载成功率: 0.0% (无文档)")
            
            add_line(f"\n📁 文件保存位置: {self.download_path}")
            
            add_line("\n📄 页面处理详情:")
            pages_processed = self.stats.get('pages_processed', [])
            if pages_processed:
                for page_info in pages_processed:
                    page_num = page_info.get('page_num', '未知')
                    sub_links_count = page_info.get('sub_links_count', 0)
                    add_line(f"   第{page_num}页: {sub_links_count}个子链接")
            else:
                add_line("   无页面被处理")
            
            add_line("\n❌ 失败链接详情:")
            failed_links = self.stats.get('failed_links', [])
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
            if self.stats.get('failed_downloads', 0) > 0:
                add_line(f"   ⚠️  有 {self.stats.get('failed_downloads', 0)} 个文档下载失败")
            if failed_links:
                add_line(f"   ❌ 有 {len(failed_links)} 个链接处理失败")
            
            add_line("\n" + "="*60)
            add_line("爬取任务完成！")
            add_line("="*60)
             
            # 总结报告生成完成
            summary_text = "\n".join(summary_lines)
            
            # 将总结报告保存到专门的数据结构中
            if self.logger and hasattr(self.logger, 'socketio'):
                try:
                    self.log(f"准备发送总结报告事件，task_id: {self.task_id}", 'info')
                    self.log(f"爬虫类型: {getattr(self, 'crawler_type', 'unknown')}", 'info')
                    self.log(f"总结报告长度: {len(summary_text)}", 'info')
                    
                    # 通过SocketIO事件将总结报告保存到后端数据结构
                    event_data = {
                        'task_id': self.task_id,
                        'summary': summary_text,
                        'stats': self.stats,
                        'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'crawler_type': getattr(self, 'crawler_type', 'unknown')
                    }
                    
                    self.logger.socketio.emit('save_task_summary', event_data)
                    self.log("总结报告事件已发送", 'info')
                    
                    # 等待一下确保事件被处理
                    import time
                    time.sleep(1)
                    self.log("总结报告保存完毕", 'info')
                    
                except Exception as e:
                    self.log(f"保存总结报告时出错: {e}", 'error')
                    import traceback
                    self.log(f"错误详情: {traceback.format_exc()}", 'error')
            else:
                self.log("警告: 无法发送总结报告，logger或socketio不可用", 'warning')
                    
        except Exception as e:
            self.log(f"生成总结报告时出错: {e}", 'error')
            # 输出简单的统计信息作为备用
            self.log(f"\n简单统计:")
            self.log(f"总页数: {self.stats.get('total_pages', 0)}")
            self.log(f"总子链接数: {self.stats.get('total_sub_links', 0)}")
            self.log(f"总文档数: {self.stats.get('total_documents', 0)}")
            self.log(f"成功下载数: {self.stats.get('successful_downloads', 0)}")
            self.log(f"失败下载数: {self.stats.get('failed_downloads', 0)}")
    
    # 抽象方法，由子类实现
    @abstractmethod
    def get_sub_links(self, main_url):
        """
        获取主页面的子链接
        :param main_url: 主页面URL
        :return: 子链接列表
        """
        pass
    
    @abstractmethod
    def download_from_sublink(self, sub_link_info):
        """
        从子链接下载内容
        :param sub_link_info: 子链接信息
        """
        pass
    def generate_page_url(self, base_url, page_num):
        """
        生成指定页面的URL（默认实现）
        :param base_url: 基础URL
        :param page_num: 页面编号（0表示第一页）
        :return: 页面URL
        """
        if page_num == 0:
            return f"{base_url}index.shtml"
        else:
            return f"{base_url}index_{page_num}.shtml"
    
    def crawl_all_pages(self, base_url, max_pages=10):
        """
        爬取所有页面（支持翻页）
        :param base_url: 基础URL
        :param max_pages: 最大页面数，防止无限循环，0表示无限制
        """
        try:
            # 处理max_pages=0的情况（表示无限制）
            if max_pages == 0:
                max_pages = 999999
                self.log("设置为无限制页数模式")
            
            if not self.driver:
                self.start_driver()
            
            # 第一步：统计所有页面的子链接总数
            self.log("正在统计所有页面的子链接数量...")
            self.total_sub_links_count = self.count_all_sub_links(base_url, max_pages)
            
            if self.total_sub_links_count == 0:
                self.log("未找到任何子链接", 'warning')
                return
            
            self.log(f"共找到 {self.total_sub_links_count} 个子链接，开始爬取...")
            
            # 第二步：逐页处理子链接
            page_count = 0
            
            while page_count < max_pages:
                if self.is_stopped:
                    self.log("爬虫已停止", 'warning')
                    break
                
                current_url = self.generate_page_url(base_url, page_count)
                
                self.log(f"\n{'='*60}")
                self.log(f"正在处理第 {page_count + 1} 页")
                self.log(f"页面URL: {current_url}")
                self.log(f"{'='*60}")
                
                # 检查页面是否存在
                if not self.check_page_exists(current_url):
                    self.log(f"第 {page_count + 1} 页不存在，停止翻页", 'warning')
                    break
                
                self.log(f"第 {page_count + 1} 页存在，开始爬取...")
                
                # 获取当前页面的所有子链接
                sub_links = self.get_sub_links(current_url)
                
                if not sub_links:
                    self.log(f"第 {page_count + 1} 页未找到任何子链接", 'warning')
                    page_count += 1
                    continue
                
                self.log(f"第 {page_count + 1} 页找到 {len(sub_links)} 个子链接")
                
                # 记录已处理的页面
                self.stats['pages_processed'].append({
                    'page_num': page_count + 1,
                    'url': current_url,
                    'sub_links_count': len(sub_links)
                })
                
                # 逐个处理子链接
                for i, sub_link in enumerate(sub_links, 1):
                    if self.is_stopped:
                        self.log("爬虫已停止", 'warning')
                        break
                        
                    self.log(f"\n第 {page_count + 1} 页 - 处理链接 {i}/{len(sub_links)}: {sub_link.get('title', '')}")
                    
                    self.download_from_sublink(sub_link)
                    
                    # 更新进度
                    self.update_sub_link_progress(1)
                    
                    time.sleep(2)  # 避免请求过于频繁
                
                self.log(f"第 {page_count + 1} 页处理完成")
                page_count += 1
                time.sleep(3)  # 页面间隔时间
            
            # 更新总页数
            self.stats['total_pages'] = page_count
            
        except Exception as e:
            self.log(f"翻页爬取过程中出错: {e}", 'error')
        finally:
            try:
                self.print_summary_report()
            except Exception as report_error:
                self.log(f"输出总结报告时出错: {report_error}", 'error')
            finally:
                self.close_driver()
    
    def crawl_all(self, main_url, max_links=None):
        """
        爬取内容（兼容方法，内部调用多页面逻辑）
        :param main_url: 主页面URL（会被转换为base_url）
        :param max_links: 最大处理链接数，None表示处理所有链接
        """
        # 将main_url转换为base_url格式
        # 移除文件名部分，保留目录路径
        if main_url.endswith('/'):
            base_url = main_url
        else:
            # 移除最后一个/之后的部分
            base_url = '/'.join(main_url.split('/')[:-1]) + '/'
        
        # 调用统一的多页面逻辑
        self.crawl_all_pages(base_url, max_pages=10)  # 使用默认的最大页数 