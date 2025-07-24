import time
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin
import requests

class MemGovCrawler:
    def __init__(self, download_path="./"):
        """
        初始化爬虫
        :param download_path: 下载文件保存路径
        """
        self.download_path = os.path.abspath(download_path)
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)
        
        # 设置Chrome选项
        self.chrome_options = Options()
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_experimental_option("prefs", {
            "download.default_directory": self.download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        })
        
        self.driver = None
        self.wait = None
    
    def start_driver(self):
        """启动浏览器驱动"""
        self.driver = webdriver.Chrome(options=self.chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        print("浏览器驱动已启动")
    
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
        
        print(f"\n等待超时，未检测到新文件")
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
    
    def get_sub_links(self, main_url):
        """
        获取主页面的子链接
        :param main_url: 主页面URL
        :return: 子链接列表
        """
        print(f"正在访问主页面: {main_url}")
        self.driver.get(main_url)
        time.sleep(3)
        
        sub_links = []
        try:
            # 根据您提供的具体XPath获取所有子链接
            # 主页面链接XPath: /html/body/div[1]/div[4]/div[5]/div[1]/div[2]/ul/li[1]/a
            print("尝试获取主页面链接...")
            link_elements = self.driver.find_elements(By.XPATH, "//div[4]//div[5]//div[1]//div//ul/li/a")
            
            # 如果上面的XPath没有找到元素，尝试更通用的路径
            if not link_elements:
                print("尝试备用XPath路径...")
                link_elements = self.driver.find_elements(By.XPATH, "//ul/li/a[contains(@href, '.shtml')]")
                
            # 如果还是没有找到，尝试最通用的路径
            if not link_elements:
                print("尝试最通用XPath路径...")
                link_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'fdzdgknr') or contains(@href, 'tzgg')]")
            
            for element in link_elements:
                href = element.get_attribute('href')
                text = element.text.strip()
                if href and text:
                    sub_links.append({
                        'url': href,
                        'title': text
                    })
                    print(f"找到子链接: {text} - {href}")
            
        except Exception as e:
            print(f"获取子链接时出错: {e}")
        
        print(f"共找到 {len(sub_links)} 个子链接")
        return sub_links
    
    def download_pdf_from_sublink(self, sub_link_info):
        """
        从子链接页面下载PDF附件
        :param sub_link_info: 包含url和title的字典
        """
        url = sub_link_info['url']
        title = sub_link_info['title']
        
        print(f"\n正在处理: {title}")
        print(f"访问URL: {url}")
        
        # 记录下载前的文件列表
        initial_files = self.get_files_in_directory()
        print(f"下载前文件数量: {len(initial_files)}")
        
        download_success = False
        
        try:
            self.driver.get(url)
            time.sleep(3)
            
            # 在详情页面查找所有PDF附件链接
            pdf_selectors = [
                "//a[contains(@href, '.pdf')]",
                "//a[contains(@href, 'P020')]",
                "//a[contains(@href, 'W020')]",
                "//p//span//font/a[contains(@href, '.pdf')]",
                "//div//a[contains(@href, '.pdf')]"
            ]
            
            pdf_links = []
            for selector in pdf_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        print(f"找到 {len(elements)} 个PDF链接，使用选择器: {selector}")
                        for elem in elements:
                            pdf_href = elem.get_attribute('href')
                            pdf_text = elem.text.strip() or elem.get_attribute('title') or '未知PDF文件'
                            if pdf_href and '.pdf' in pdf_href.lower():
                                pdf_links.append({
                                    'url': pdf_href,
                                    'text': pdf_text,
                                    'element': elem
                                })
                        break
                except Exception as e:
                    continue
            
            if not pdf_links:
                print("未找到PDF附件链接")
                return
            
            print(f"找到 {len(pdf_links)} 个PDF附件")
            
            # 逐个下载PDF文件
            for i, pdf_info in enumerate(pdf_links, 1):
                print(f"\n下载第 {i}/{len(pdf_links)} 个PDF: {pdf_info['text']}")
                print(f"PDF链接: {pdf_info['url']}")
                
                try:
                    # 方法1: 直接使用requests下载PDF
                    success = self.download_pdf_directly(pdf_info['url'], title, pdf_info['text'], i)
                    if success:
                        print(f"PDF下载成功: {pdf_info['text']}")
                        download_success = True
                        continue
                    
                    # 方法2: 如果直接下载失败，尝试点击元素
                    print("尝试点击PDF链接...")
                    element = pdf_info['element']
                    
                    # 滚动到元素位置
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(1)
                    
                    # 尝试多种点击方式
                    click_methods = [
                        lambda: element.click(),
                        lambda: self.driver.execute_script("arguments[0].click();", element),
                        lambda: self.driver.execute_script(f"window.open('{pdf_info['url']}', '_blank');")
                    ]
                    
                    clicked = False
                    for method in click_methods:
                        try:
                            method()
                            print("PDF链接点击成功")
                            clicked = True
                            time.sleep(2)
                            break
                        except Exception as e:
                            print(f"点击方法失败: {e}")
                            continue
                    
                    if clicked:
                        # 处理可能的新窗口或下载
                        original_window = self.driver.current_window_handle
                        
                        # 检查是否有新窗口
                        if len(self.driver.window_handles) > 1:
                            print("检测到新窗口，尝试处理...")
                            self.driver.switch_to.window(self.driver.window_handles[-1])
                            time.sleep(3)
                            
                            # 尝试下载按钮
                            self.try_download_buttons()
                            
                            # 关闭新窗口
                            self.driver.close()
                            self.driver.switch_to.window(original_window)
                        
                        download_success = True
                    else:
                        print("所有点击方法都失败了")
                    
                except Exception as e:
                    print(f"下载PDF时出错: {e}")
                    # 确保回到主窗口
                    try:
                        if len(self.driver.window_handles) > 1:
                            self.driver.close()
                            self.driver.switch_to.window(self.driver.window_handles[0])
                    except:
                        pass
                
                # 等待下载完成
                if download_success:
                    print("等待PDF下载完成...")
                    new_files = self.wait_for_download_complete(initial_files, timeout=15)
                    
                    if new_files:
                        for new_file in new_files:
                            pdf_title = f"{title}_{pdf_info['text']}_{i}"
                            renamed_path = self.rename_downloaded_file(new_file, pdf_title)
                            print(f"PDF已保存: {renamed_path}")
                        # 更新文件列表
                        initial_files = self.get_files_in_directory()
                    else:
                        print("未检测到新的PDF文件")
                
                time.sleep(1)
            
        except Exception as e:
            print(f"处理页面时出错: {e}")
            # 确保回到主窗口
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass
        
        print(f"已完成处理: {title}")
    
    def download_pdf_directly(self, pdf_url, title, pdf_text, index):
        """
        直接使用requests下载PDF文件
        :param pdf_url: PDF文件URL
        :param title: 文档标题
        :param pdf_text: PDF文本描述
        :param index: PDF序号
        :return: 是否下载成功
        """
        try:
            print(f"尝试直接下载PDF: {pdf_url}")
            
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
            pdf_title = f"{title}_{pdf_text}_{index}"
            clean_title = self.clean_filename(pdf_title)
            filename = f"{clean_title}.pdf"
            filepath = os.path.join(self.download_path, filename)
            
            # 如果文件已存在，添加序号
            counter = 1
            while os.path.exists(filepath):
                filename = f"{clean_title}_{counter}.pdf"
                filepath = os.path.join(self.download_path, filename)
                counter += 1
            
            # 保存文件
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"PDF直接下载成功: {filename}")
            return True
            
        except Exception as e:
            print(f"直接下载PDF失败: {e}")
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
            "//main//button[3]",
            "//button[3]"  # 根据您之前提供的XPath
        ]
        
        for selector in download_button_selectors:
            try:
                download_btn = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                download_btn.click()
                print(f"成功点击下载按钮: {selector}")
                time.sleep(2)
                return True
            except Exception as e:
                continue
        
        # 如果都失败了，尝试键盘快捷键
        try:
            print("尝试使用Ctrl+S快捷键...")
            from selenium.webdriver.common.keys import Keys
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.CONTROL + 's')
            time.sleep(2)
            return True
        except Exception as e:
            print(f"快捷键下载失败: {e}")
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
    
    def crawl_all_pages(self, base_url, max_pages=50):
        """
        爬取所有页面（支持翻页）
        :param base_url: 基础URL
        :param max_pages: 最大页面数，防止无限循环
        """
        page_count = 0
        
        try:
            self.start_driver()
            
            while page_count < max_pages:
                # 构造当前页面URL
                if page_count == 0:
                    current_url = base_url + "index.shtml"
                else:
                    current_url = base_url + f"index_{page_count}.shtml"
                
                print(f"\n{'='*60}")
                print(f"正在处理第 {page_count + 1} 页")
                print(f"页面URL: {current_url}")
                print(f"{'='*60}")
                
                # 检查页面是否存在
                if not self.check_page_exists(current_url):
                    print(f"第 {page_count + 1} 页不存在，停止翻页")
                    break
                
                print(f"第 {page_count + 1} 页存在，开始爬取...")
                
                # 获取当前页面的所有子链接
                sub_links = self.get_sub_links(current_url)
                
                if not sub_links:
                    print(f"第 {page_count + 1} 页未找到任何子链接")
                    page_count += 1
                    continue
                
                print(f"第 {page_count + 1} 页找到 {len(sub_links)} 个子链接")
                
                # 逐个处理子链接
                for i, sub_link in enumerate(sub_links, 1):
                    print(f"\n第 {page_count + 1} 页 - 进度: {i}/{len(sub_links)}")
                    self.download_pdf_from_sublink(sub_link)
                    time.sleep(2)  # 避免请求过于频繁
                
                print(f"第 {page_count + 1} 页处理完成")
                page_count += 1
                time.sleep(3)  # 页面间隔时间
            
            print(f"\n所有页面处理完成！共处理了 {page_count} 页")
            print(f"文件已保存到: {self.download_path}")
            
        except Exception as e:
            print(f"翻页爬取过程中出错: {e}")
        finally:
            self.close_driver()

    def crawl_all(self, main_url, max_links=None):
        """
        爬取单个页面的所有内容
        :param main_url: 主页面URL
        :param max_links: 最大处理链接数，None表示处理所有链接
        """
        try:
            if not self.driver:
                self.start_driver()
            
            # 获取所有子链接
            sub_links = self.get_sub_links(main_url)
            
            if not sub_links:
                print("未找到任何子链接")
                return
            
            # 限制处理的链接数量
            if max_links:
                sub_links = sub_links[:max_links]
                print(f"将处理前 {max_links} 个链接")
            
            # 逐个处理子链接
            for i, sub_link in enumerate(sub_links, 1):
                print(f"\n{'='*50}")
                print(f"进度: {i}/{len(sub_links)}")
                self.download_pdf_from_sublink(sub_link)
                time.sleep(2)  # 避免请求过于频繁
            
            print(f"\n当前页面任务完成！文件已保存到: {self.download_path}")
            
        except Exception as e:
            print(f"爬取过程中出错: {e}")

def main():
    """主函数"""
    main_url = "https://www.mem.gov.cn/fw/flfgbz/bz/bzgg/"
    
    # 创建爬虫实例，将下载路径改为"标准"文件夹
    crawler = MemGovCrawler(download_path="./标准/制度文件")
    
    # 直接开始爬取所有页面（自动翻页）
    print("开始爬取所有页面...")
    max_pages = 50  # 默认最大页面数
    
    try:
        crawler.crawl_all_pages(main_url, max_pages=max_pages)
    except KeyboardInterrupt:
        print("\n用户中断爬取")
    except Exception as e:
        print(f"\n爬取过程中出错: {e}")

if __name__ == "__main__":
    main() 