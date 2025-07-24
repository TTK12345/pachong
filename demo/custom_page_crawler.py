from base_crawler import BaseCrawler
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import requests
from urllib.parse import urljoin, urlparse
import mimetypes
import os

class CustomPageCrawler(BaseCrawler):
    """自定义页面爬虫 - 继承自BaseCrawler，专门处理附件下载"""
    
    def __init__(self, download_path="./自定义页面", logger=None, task_id=None, socketio=None, progress_callback=None):
        super().__init__(download_path, logger, task_id, socketio, progress_callback)
        self.crawler_type = 'custom_page'
        self.base_page_url = None  # 保存页面的基础URL，用于处理相对链接
        self.attachment_counter = 0  # 附件计数器，用于文件命名
    
    def set_base_url(self, url):
        """设置基础URL，用于处理相对链接"""
        self.base_page_url = url
        self.log(f"设置基础URL: {url}")
    
    def get_sub_links(self, main_url):
        """
        获取页面中的所有可下载附件链接
        :param main_url: 主页面URL
        :return: 附件链接列表
        """
        self.log(f"正在分析页面附件: {main_url}")
        self.driver.get(main_url)
        time.sleep(3)
        
        attachments = []
        
        # 常见的附件文件扩展名
        attachment_extensions = [
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.zip', '.rar', '.7z', '.tar', '.gz',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg',
            '.mp4', '.avi', '.mov', '.wmv', '.flv',
            '.mp3', '.wav', '.wma', '.aac',
            '.txt', '.rtf', '.csv'
        ]
        
        try:
            # 方法1: 查找所有带href的链接
            links = self.driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                try:
                    href = link.get_attribute("href")
                    if not href:
                        continue
                    
                    # 转换为绝对URL
                    absolute_url = urljoin(main_url, href)
                    
                    # 检查是否是附件链接
                    if self._is_attachment_link(absolute_url, attachment_extensions):
                        title = link.text.strip() or link.get_attribute("title") or "未知附件"
                        attachments.append({
                            'url': absolute_url,
                            'title': title,
                            'type': 'link'
                        })
                        self.log(f"发现附件链接: {title} - {absolute_url}")
                
                except Exception as e:
                    continue
            
            # 方法2: 查找下载按钮（通过文本内容识别）
            download_buttons = self._find_download_buttons()
            for button_info in download_buttons:
                attachments.append(button_info)
            
            # 方法3: 查找嵌入的文件链接（iframe、embed等）
            embedded_files = self._find_embedded_files()
            for file_info in embedded_files:
                attachments.append(file_info)
                
        except Exception as e:
            self.log(f"搜索附件时出错: {str(e)}", 'error')
        
        self.log(f"共发现 {len(attachments)} 个附件")
        return attachments
    
    def _is_attachment_link(self, url, extensions):
        """
        判断URL是否为附件链接
        :param url: 要检查的URL
        :param extensions: 附件扩展名列表
        :return: bool
        """
        # 检查URL路径的扩展名
        path = urlparse(url).path.lower()
        for ext in extensions:
            if path.endswith(ext):
                return True
        
        # 检查URL中是否包含下载相关参数
        download_indicators = ['download', 'attachment', 'file', 'doc', 'pdf']
        url_lower = url.lower()
        for indicator in download_indicators:
            if indicator in url_lower:
                return True
        
        return False
    
    def _find_download_buttons(self):
        """查找页面中的下载按钮"""
        buttons = []
        
        # 查找包含下载相关文字的按钮或链接
        download_keywords = ['下载', 'download', '附件', '文件', 'attachment']
        
        try:
            # 查找按钮元素
            for keyword in download_keywords:
                elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{keyword}')]")
                for element in elements:
                    try:
                        # 检查是否可点击
                        if element.is_enabled() and element.is_displayed():
                            onclick = element.get_attribute("onclick")
                            href = element.get_attribute("href")
                            
                            if onclick or href:
                                title = element.text.strip() or f"下载按钮_{len(buttons)+1}"
                                buttons.append({
                                    'element': element,
                                    'title': title,
                                    'type': 'button',
                                    'onclick': onclick,
                                    'href': href
                                })
                                self.log(f"发现下载按钮: {title}")
                    except Exception as e:
                        continue
                        
        except Exception as e:
            self.log(f"查找下载按钮时出错: {str(e)}", 'warning')
        
        return buttons
    
    def _find_embedded_files(self):
        """查找嵌入的文件（iframe、embed等）"""
        embedded = []
        
        try:
            # 查找iframe中的文件
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                src = iframe.get_attribute("src")
                if src and self._is_attachment_link(src, ['.pdf', '.doc', '.docx']):
                    title = iframe.get_attribute("title") or f"嵌入文件_{len(embedded)+1}"
                    embedded.append({
                        'url': urljoin(self.base_page_url or "", src),
                        'title': title,
                        'type': 'embedded'
                    })
            
            # 查找embed元素
            embeds = self.driver.find_elements(By.TAG_NAME, "embed")
            for embed in embeds:
                src = embed.get_attribute("src")
                if src:
                    title = f"嵌入对象_{len(embedded)+1}"
                    embedded.append({
                        'url': urljoin(self.base_page_url or "", src),
                        'title': title,
                        'type': 'embedded'
                    })
                    
        except Exception as e:
            self.log(f"查找嵌入文件时出错: {str(e)}", 'warning')
        
        return embedded
    
    def download_from_sublink(self, attachment_info):
        """
        从附件信息下载文件
        :param attachment_info: 附件信息字典
        :return: 下载结果
        """
        attachment_type = attachment_info.get('type', 'link')
        title = attachment_info.get('title', '未知附件')
        
        try:
            if attachment_type == 'link' or attachment_type == 'embedded':
                # 直接URL下载
                url = attachment_info['url']
                return self._download_from_url(url, title)
                
            elif attachment_type == 'button':
                # 按钮点击下载
                return self._download_from_button(attachment_info)
                
        except Exception as e:
            self.log(f"下载附件 '{title}' 时出错: {str(e)}", 'error')
            self.stats['failed_downloads'] += 1
            self.stats['failed_links'].append({
                'title': title,
                'url': attachment_info.get('url', ''),
                'error': str(e)
            })
            return False
    
    def _download_from_url(self, url, title):
        """从URL直接下载文件"""
        try:
            self.log(f"开始下载: {title}")
            
            # 使用requests下载
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # 增加附件计数器
            self.attachment_counter += 1
            
            # 确定文件名和扩展名
            filename = self._get_filename_from_response(response, title, url, self.attachment_counter)
            filename = self.clean_filename(filename)
            
            # 保存文件
            file_path = os.path.join(self.download_path, filename)
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(file_path)
            self.log(f"下载完成: {filename} ({file_size} bytes)")
            
            self.stats['successful_downloads'] += 1
            self.stats['total_documents'] += 1
            
            return True
            
        except Exception as e:
            self.log(f"URL下载失败 '{title}': {str(e)}", 'error')
            return False
    
    def _download_from_button(self, button_info):
        """通过点击按钮下载文件"""
        try:
            element = button_info['element']
            title = button_info['title']
            
            self.log(f"尝试点击下载按钮: {title}")
            
            # 增加附件计数器
            self.attachment_counter += 1
            
            # 记录下载前的文件
            files_before = self.get_files_in_directory()
            
            # 点击按钮
            self.driver.execute_script("arguments[0].click();", element)
            time.sleep(2)
            
            # 等待下载完成
            if self.wait_for_download_complete(timeout=30):
                # 检查新文件
                files_after = self.get_files_in_directory()
                new_files = files_after - files_before
                
                if new_files:
                    new_file = list(new_files)[0]
                    
                    # 重命名下载的文件，使用更清晰的命名
                    old_file_path = os.path.join(self.download_path, new_file)
                    
                    # 清理title
                    clean_title = re.sub(r'[^\w\s\-\u4e00-\u9fff]', '', title).strip()
                    if not clean_title or clean_title == '未知附件':
                        clean_title = '按钮下载'
                    
                    # 限制文件名长度
                    if len(clean_title) > 50:
                        clean_title = clean_title[:50]
                    
                    # 获取原文件扩展名
                    original_ext = os.path.splitext(new_file)[1]
                    
                    # 构建新文件名
                    new_filename = f"附件{self.attachment_counter:02d}_{clean_title}_{new_file}"
                    new_file_path = os.path.join(self.download_path, new_filename)
                    
                    # 重命名文件
                    try:
                        os.rename(old_file_path, new_file_path)
                        self.log(f"按钮下载完成并重命名: {new_filename}")
                    except Exception as rename_error:
                        self.log(f"重命名文件失败，保持原名: {new_file} - {str(rename_error)}", 'warning')
                    
                    self.stats['successful_downloads'] += 1
                    self.stats['total_documents'] += 1
                    return True
                else:
                    self.log(f"未检测到新下载的文件: {title}", 'warning')
                    return False
            else:
                self.log(f"下载超时: {title}", 'warning')
                return False
                
        except Exception as e:
            self.log(f"按钮下载失败 '{title}': {str(e)}", 'error')
            return False
    
    def _get_filename_from_response(self, response, title, url, attachment_number):
        """从响应中获取文件名"""
        # 尝试从Content-Disposition头获取原始文件名
        original_filename = None
        content_disposition = response.headers.get('content-disposition')
        if content_disposition:
            filename_match = re.search(r'filename[*]?=([^;]+)', content_disposition)
            if filename_match:
                original_filename = filename_match.group(1).strip('"\'')
        
        # 如果没有找到，尝试从URL路径获取
        if not original_filename:
            path = urlparse(url).path
            if path:
                original_filename = os.path.basename(path)
        
        # 确定文件扩展名
        extension = ''
        if original_filename and '.' in original_filename:
            extension = os.path.splitext(original_filename)[1]
        else:
            # 根据Content-Type推测扩展名
            content_type = response.headers.get('content-type', '').lower()
            extension = mimetypes.guess_extension(content_type.split(';')[0]) or ''
        
        # 清理title作为基础文件名
        clean_title = re.sub(r'[^\w\s\-\u4e00-\u9fff]', '', title).strip()
        if not clean_title or clean_title == '未知附件':
            clean_title = '附件'
        
        # 限制文件名长度
        if len(clean_title) > 50:
            clean_title = clean_title[:50]
        
        # 构建最终文件名：附件序号_标题_原始文件名（如果有）
        if original_filename and original_filename != os.path.basename(url):
            # 清理原始文件名
            clean_original = re.sub(r'[^\w\s\-\u4e00-\u9fff\.]', '', original_filename).strip()
            if len(clean_original) > 30:
                clean_original = clean_original[:30]
            final_filename = f"附件{attachment_number:02d}_{clean_title}_{clean_original}"
        else:
            final_filename = f"附件{attachment_number:02d}_{clean_title}{extension}"
        
        return final_filename
    
    def generate_page_url(self, base_url, page_num):
        """
        自定义页面爬虫只处理单个页面
        """
        if page_num == 0:
            return base_url
        else:
            return None  # 只有一个页面
    
    def stop(self):
        """
        停止爬虫任务
        """
        self.log("收到停止信号，正在停止自定义页面爬虫...")
        self.is_stopped = True
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                self.log("浏览器驱动已关闭")
            except Exception as e:
                self.log(f"关闭浏览器驱动时出错: {str(e)}", 'warning') 