import time
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
import requests

class GzCrawler:
    def __init__(self, download_path="./规章"):
        """
        初始化规章爬虫
        :param download_path: 下载文件保存路径
        """
        self.download_path = os.path.abspath(download_path)
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)
            print(f"已创建规章文件夹: {self.download_path}")
        
        # 设置Chrome选项
        self.chrome_options = Options()
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        self.chrome_options.add_experimental_option("prefs", {
            "download.default_directory": self.download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "plugins.always_open_pdf_externally": True
        })
        
        self.driver = None
        self.wait = None
    
    def start_driver(self):
        """启动浏览器驱动"""
        try:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 20)
            print("浏览器驱动已启动")
        except Exception as e:
            print(f"启动浏览器驱动失败: {e}")
            raise
    
    def close_driver(self):
        """关闭浏览器驱动"""
        if self.driver:
            self.driver.quit()
            print("浏览器驱动已关闭")
    
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
            print(f"获取文件列表时出错: {e}")
        return files
    
    def wait_for_download_complete(self, initial_files, timeout=30):
        """
        等待下载完成，并返回新下载的文件
        :param initial_files: 下载前的文件列表
        :param timeout: 超时时间（秒）
        :return: 新下载的文件信息
        """
        start_time = time.time()
        print(f"开始等待下载完成，超时时间: {timeout}秒")
        
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
                print(f"检测到 {len(new_files)} 个新文件")
                # 等待一段时间确保文件下载完成
                time.sleep(3)
                stable_files = []
                for new_file in new_files:
                    # 检查文件是否不再变化（下载完成）
                    if not new_file['name'].endswith('.crdownload') and not new_file['name'].endswith('.tmp'):
                        stable_files.append(new_file)
                        print(f"发现稳定文件: {new_file['name']}")
                
                if stable_files:
                    return stable_files
            
            print(".", end="", flush=True)  # 显示等待进度
            time.sleep(1)
        
        print(f"\n等待超时，检查是否有文件变化...")
        
        # 超时后再检查一次是否有新文件
        final_files = self.get_files_in_directory()
        new_files = []
        for current_file in final_files:
            is_new = True
            for initial_file in initial_files:
                if current_file['name'] == initial_file['name']:
                    is_new = False
                    break
            if is_new:
                new_files.append(current_file)
        
        if new_files:
            print(f"超时后发现 {len(new_files)} 个新文件")
            return new_files
        
        print("确实未检测到新文件")
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
                # 根据文件内容或URL判断扩展名
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
            
            # 如果文件已存在，添加序号
            counter = 1
            while os.path.exists(new_path):
                new_filename = f"{clean_name}_{counter}{ext}"
                new_path = os.path.join(self.download_path, new_filename)
                counter += 1
            
            # 重命名文件
            os.rename(old_path, new_path)
            print(f"文件已重命名: {old_name} -> {new_filename}")
            return new_path
            
        except Exception as e:
            print(f"重命名文件时出错: {e}")
            return file_info['path']
    
    def generate_page_url(self, page_num):
        """
        生成指定页面的URL
        :param page_num: 页面编号（0表示第一页，1表示第二页，以此类推）
        :return: 页面URL
        """
        base_url = "https://www.mem.gov.cn/gk/zfxxgkpt/fdzdgknr/gz11/"
        if page_num == 0:
            return f"{base_url}index.shtml"
        else:
            return f"{base_url}index_{page_num}.shtml"
    
    def get_document_info_from_page(self, page_url, page_num):
        """
        从单个页面获取文档信息
        :param page_url: 页面URL
        :param page_num: 页面编号
        :return: 文档信息列表
        """
        print(f"\n{'='*60}")
        print(f"正在爬取第 {page_num + 1} 页: {page_url}")
        
        # 直接访问iframe页面
        self.driver.get(page_url)
        
        # 等待页面加载
        print("等待页面加载...")
        time.sleep(8)
        
        documents = []
        
        try:
            # 等待表格加载
            try:
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
                print("表格已加载")
            except:
                print("等待表格超时")
                return documents
            
            # 查找表格
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            print(f"找到 {len(tables)} 个表格")
            
            if tables:
                table = tables[0]
                rows = table.find_elements(By.TAG_NAME, "tr")
                print(f"表格有 {len(rows)} 行")
                
                # 从第2行开始遍历（跳过表头）
                for row_num in range(2, len(rows) + 1):
                    try:
                        print(f"检查第 {row_num} 行...")
                        
                        # 使用相对xpath（更稳定）
                        title_xpath = f"//table//tr[{row_num}]/td[2]//a"
                        download_xpath = f"//table//tr[{row_num}]/td[3]//a[1]"
                        
                        title_element = None
                        download_element = None
                        
                        # 查找标题元素
                        try:
                            title_elements = self.driver.find_elements(By.XPATH, title_xpath)
                            if title_elements:
                                title_element = title_elements[0]
                                print(f"  找到标题元素")
                        except Exception as e:
                            print(f"  查找标题元素时出错: {e}")
                        
                        # 查找下载元素
                        try:
                            download_elements = self.driver.find_elements(By.XPATH, download_xpath)
                            if download_elements:
                                download_element = download_elements[0]
                                print(f"  找到下载元素")
                        except Exception as e:
                            print(f"  查找下载元素时出错: {e}")
                        
                        if title_element and download_element:
                            file_name = title_element.text.strip()
                            download_url = download_element.get_attribute('href')
                            
                            if file_name and download_url:
                                documents.append({
                                    'name': file_name,
                                    'download_element': download_element,
                                    'download_url': download_url,
                                    'row_index': row_num,
                                    'page_num': page_num + 1
                                })
                                print(f"  成功找到文档: {file_name}")
                                print(f"  下载链接: {download_url}")
                            else:
                                print(f"  第 {row_num} 行：文件名或下载链接为空")
                        else:
                            print(f"  第 {row_num} 行：未找到必要元素")
                            # 如果连续多行都没有元素，可能到了表格末尾
                            if row_num > 5:  # 给一些容错空间
                                break
                    
                    except Exception as e:
                        print(f"  处理第 {row_num} 行时出错: {e}")
                        continue
                
        except Exception as e:
            print(f"获取第 {page_num + 1} 页文档信息时出错: {e}")
        
        print(f"第 {page_num + 1} 页找到 {len(documents)} 个规章文档")
        return documents
    
    def get_all_documents(self, max_pages=10):
        """
        获取所有页面的文档信息
        :param max_pages: 最大页面数限制
        :return: 所有文档信息列表
        """
        all_documents = []
        
        for page_num in range(max_pages):
            page_url = self.generate_page_url(page_num)
            
            try:
                # 先检查页面是否存在
                self.driver.get(page_url)
                time.sleep(3)
                
                # 检查页面是否正常加载（没有404错误等）
                page_title = self.driver.title
                if "404" in page_title or "错误" in page_title or len(page_title) < 5:
                    print(f"第 {page_num + 1} 页不存在或加载失败，停止爬取")
                    break
                
                # 检查是否有表格内容
                tables = self.driver.find_elements(By.TAG_NAME, "table")
                if not tables:
                    print(f"第 {page_num + 1} 页没有表格，停止爬取")
                    break
                
                # 获取该页面的文档信息
                page_documents = self.get_document_info_from_page(page_url, page_num)
                
                if not page_documents:
                    print(f"第 {page_num + 1} 页没有找到文档，停止爬取")
                    break
                
                all_documents.extend(page_documents)
                print(f"第 {page_num + 1} 页完成，累计找到 {len(all_documents)} 个文档")
                
                # 避免请求过于频繁
                time.sleep(2)
                
            except Exception as e:
                print(f"访问第 {page_num + 1} 页时出错: {e}")
                break
        
        print(f"\n所有页面爬取完成，共找到 {len(all_documents)} 个规章文档")
        return all_documents
    
    def download_document_by_url(self, doc_info):
        """
        通过直接访问URL下载文档
        :param doc_info: 文档信息字典
        """
        name = doc_info['name']
        download_url = doc_info['download_url']
        page_num = doc_info.get('page_num', 1)
        
        print(f"\n正在处理: {name} (第{page_num}页)")
        print(f"下载URL: {download_url}")
        
        # 记录下载前的文件列表
        initial_files = self.get_files_in_directory()
        print(f"下载前文件数量: {len(initial_files)}")
        
        download_success = False
        
        try:
            # 直接访问下载链接
            self.driver.get(download_url)
            print("已访问下载链接")
            time.sleep(8)  # 增加等待时间
            
            # 获取当前URL
            current_url = self.driver.current_url
            print(f"当前URL: {current_url}")
            
            # 无论URL是什么，都认为下载可能已经开始
            download_success = True
            print("假设下载已开始...")
                
        except Exception as e:
            print(f"访问下载链接时出错: {e}")
            download_success = True  # 即使出错也检查文件
        
        # 等待下载完成并重命名
        if download_success:
            print("等待下载完成...")
            new_files = self.wait_for_download_complete(initial_files, timeout=30)
            
            if new_files:
                print(f"检测到 {len(new_files)} 个新下载的文件")
                for new_file in new_files:
                    # 重命名文件
                    renamed_path = self.rename_downloaded_file(new_file, name)
                    print(f"文件已保存并重命名: {renamed_path}")
                return True
            else:
                print("未检测到新下载的文件")
                return False
        
        return False
    
    def download_document(self, doc_info):
        """
        下载单个文档
        :param doc_info: 文档信息字典
        """
        name = doc_info['name']
        
        # 直接使用URL下载方式
        success = self.download_document_by_url(doc_info)
        
        if success:
            print(f"✓ 成功下载并重命名: {name}")
        else:
            print(f"✗ 下载失败: {name}")
        
        return success
    
    def rename_existing_files(self, documents):
        """
        重命名已存在的文件
        :param documents: 文档信息列表
        """
        print("\n检查并重命名已下载的文件...")
        
        # 获取当前目录中的所有文件
        current_files = self.get_files_in_directory()
        
        # 如果文件数量与文档数量匹配，尝试重命名
        if len(current_files) >= len(documents):
            print(f"发现 {len(current_files)} 个文件，尝试重命名...")
            
            # 按修改时间排序（最新的文件在前）
            current_files.sort(key=lambda x: x['mtime'], reverse=True)
            
            # 取最新的几个文件进行重命名
            files_to_rename = current_files[:len(documents)]
            
            for i, (file_info, doc_info) in enumerate(zip(files_to_rename, documents)):
                try:
                    # 检查文件是否已经是正确的名称
                    clean_name = self.clean_filename(doc_info['name'])
                    if clean_name not in file_info['name']:
                        renamed_path = self.rename_downloaded_file(file_info, doc_info['name'])
                        print(f"重命名文件 {i+1}: {renamed_path}")
                    else:
                        print(f"文件 {i+1} 已经是正确名称: {file_info['name']}")
                except Exception as e:
                    print(f"重命名文件 {i+1} 时出错: {e}")
    
    def crawl_all(self, main_url=None, max_docs=None, max_pages=10):
        """
        爬取所有规章文档
        :param main_url: 主页面URL（保留兼容性，实际不使用）
        :param max_docs: 最大处理文档数，None表示处理所有文档
        :param max_pages: 最大页面数
        """
        try:
            self.start_driver()
            
            # 获取所有页面的文档信息
            print(f"开始爬取所有页面，最大页面数: {max_pages}")
            all_documents = self.get_all_documents(max_pages)
            
            if not all_documents:
                print("未找到任何规章文档")
                return
            
            # 限制处理的文档数量
            if max_docs:
                all_documents = all_documents[:max_docs]
                print(f"将处理前 {max_docs} 个文档")
            
            print(f"\n开始下载 {len(all_documents)} 个文档...")
            
            # 先检查是否已有文件需要重命名
            self.rename_existing_files(all_documents)
            
            # 统计信息
            success_count = 0
            fail_count = 0
            
            # 逐个处理文档
            for i, doc_info in enumerate(all_documents, 1):
                print(f"\n{'='*60}")
                print(f"进度: {i}/{len(all_documents)} - 第{doc_info.get('page_num', '?')}页")
                
                success = self.download_document(doc_info)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                
                time.sleep(3)  # 避免请求过于频繁
                
                # 每10个文档显示一次进度统计
                if i % 10 == 0:
                    print(f"\n当前进度统计：成功 {success_count} 个，失败 {fail_count} 个")
            
            # 处理完成后再次尝试重命名
            print("\n最终检查和重命名...")
            self.rename_existing_files(all_documents)
            
            print(f"\n{'='*60}")
            print(f"所有任务完成！")
            print(f"总共处理: {len(all_documents)} 个文档")
            print(f"成功下载: {success_count} 个")
            print(f"下载失败: {fail_count} 个")
            print(f"文件保存位置: {self.download_path}")
            
        except Exception as e:
            print(f"爬取过程中出错: {e}")
        finally:
            self.close_driver()

def main():
    """主函数"""
    # 创建规章爬虫实例
    crawler = GzCrawler(download_path="./规章")
    
    # 开始爬取所有页面的所有文档
    # max_pages=10 表示最多检查10页，max_docs=None 表示下载所有找到的文档
    crawler.crawl_all(max_pages=10, max_docs=None)

if __name__ == "__main__":
    main() 