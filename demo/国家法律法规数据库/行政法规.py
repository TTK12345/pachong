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
    def __init__(self, download_path=""):
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
            # 获取页面上所有包含onclick属性的li元素
            print("尝试获取所有包含onclick属性的li元素...")
            link_elements = self.driver.find_elements(By.XPATH, "//li[contains(@onclick, 'showDetail')]")
            
            # 如果上面的XPath没有找到元素，尝试更通用的路径
            if not link_elements:
                print("尝试备用XPath路径...")
                link_elements = self.driver.find_elements(By.XPATH, "//ul/li[contains(@onclick, 'showDetail')]")
                
            # 如果还是没有找到，尝试更通用的路径
            if not link_elements:
                print("尝试更通用XPath路径...")
                link_elements = self.driver.find_elements(By.XPATH, "//*[contains(@onclick, 'showDetail')]")
            
            print(f"找到 {len(link_elements)} 个包含onclick的元素")
            
            for i, element in enumerate(link_elements, 1):
                try:
                    # 获取onclick属性
                    onclick_attr = element.get_attribute('onclick')
                    if onclick_attr and 'showDetail' in onclick_attr:
                        # 提取网址后缀
                        # onclick="showDetail('./detail2.html?ZmY4MDgxODE5NDQwNjk3MjAxOTU4NTRkNjY3Nzc2YzA%3D')"
                        # 需要提取 detail2.html?ZmY4MDgxODE5NDQwNjk3MjAxOTU4NTRkNjY3Nzc2YzA%3D
                        import re
                        match = re.search(r"showDetail\('\./([^']+)'\)", onclick_attr)
                        if match:
                            url_suffix = match.group(1)
                            # 组合完整URL
                            full_url = "https://flk.npc.gov.cn/" + url_suffix
                            
                            # 获取链接文本
                            text = element.text.strip()
                            if not text:
                                # 如果没有文本，尝试获取子元素的文本
                                child_elements = element.find_elements(By.XPATH, ".//*")
                                for child in child_elements:
                                    child_text = child.text.strip()
                                    if child_text:
                                        text = child_text
                                        break
                            
                            # 如果还是没有文本，使用URL后缀作为标题
                            if not text:
                                text = url_suffix
                            
                            sub_links.append({
                                'url': full_url,
                                'title': text
                            })
                            print(f"找到子链接 {i}: {text} - {full_url}")
                        else:
                            print(f"无法从onclick属性中提取URL: {onclick_attr}")
                    else:
                        print(f"元素 {i} 没有onclick属性或不是showDetail: {onclick_attr}")
                        
                except Exception as e:
                    print(f"处理第 {i} 个元素时出错: {e}")
                    continue
            
        except Exception as e:
            print(f"获取子链接时出错: {e}")
        
        print(f"共找到 {len(sub_links)} 个有效子链接")
        return sub_links
    
    def download_pdf_from_sublink(self, sub_link_info):
        """
        从子链接页面直接下载内容
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
            
            # 方法1: 尝试直接下载页面内容（如果是PDF页面）
            current_url = self.driver.current_url
            if '.pdf' in current_url.lower():
                print("检测到PDF页面，直接下载...")
                success = self.download_pdf_directly_from_url(current_url, title)
                if success:
                    print("PDF页面下载成功")
                    return
            
            # 方法2: 点击指定的下载按钮
            print("尝试点击指定的下载按钮...")
            download_button_selectors = [
                "/html/body/div[6]/div/div",  # 您指定的XPath
                "//div[6]//div//div",  # 备用路径
                "//div[contains(@class, 'download')]",  # 通用下载按钮
                "//button[contains(text(), '下载')]",
                "//a[contains(text(), '下载')]",
                "//button[contains(@class, 'download')]",
                "//a[contains(@class, 'download')]",
                "//a[contains(text(), 'PDF')]",
                "//a[contains(text(), '附件')]",
                "//span[contains(text(), '下载')]/parent::a",
                "//div[contains(@class, 'download')]//a"
            ]
            
            download_button = None
            for selector in download_button_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        download_button = elements[0]  # 取第一个找到的下载按钮
                        print(f"找到下载按钮，使用选择器: {selector}")
                        break
                except:
                    continue
            
            if download_button:
                try:
                    # 滚动到下载按钮位置
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
                    time.sleep(1)
                    
                    # 尝试点击下载按钮
                    download_button.click()
                    print("已点击下载按钮")
                    time.sleep(3)
                    download_success = True
                    
                    # 处理可能的新窗口
                    original_window = self.driver.current_window_handle
                    if len(self.driver.window_handles) > 1:
                        print("检测到新窗口")
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                        time.sleep(2)
                        
                        # 在新窗口中尝试下载
                        new_url = self.driver.current_url
                        if '.pdf' in new_url.lower():
                            print("新窗口是PDF，直接下载...")
                            self.download_pdf_directly_from_url(new_url, title)
                        else:
                            # 在新窗口中查找下载按钮
                            self.try_download_buttons()
                        
                        # 关闭新窗口
                        self.driver.close()
                        self.driver.switch_to.window(original_window)
                    
                except Exception as e:
                    print(f"点击下载按钮失败: {e}")
            
            # 方法3: 如果没有找到下载按钮，尝试使用快捷键下载页面
            if not download_success:
                print("未找到下载按钮，尝试使用快捷键保存页面...")
                try:
                    from selenium.webdriver.common.keys import Keys
                    self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.CONTROL + 's')
                    time.sleep(3)
                    download_success = True
                except Exception as e:
                    print(f"快捷键下载失败: {e}")
            
            # 方法4: 如果以上都失败，尝试保存页面源码
            if not download_success:
                print("尝试保存页面内容...")
                success = self.save_page_content(url, title)
                if success:
                    download_success = True
                    print("页面内容保存成功")
            
            # 等待下载完成
            if download_success:
                print("等待下载完成...")
                new_files = self.wait_for_download_complete(initial_files, timeout=15)
                
                if new_files:
                    for new_file in new_files:
                        renamed_path = self.rename_downloaded_file(new_file, title)
                        print(f"文件已保存: {renamed_path}")
                else:
                    print("未检测到新下载的文件")
            
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
    
    def download_pdf_directly_from_url(self, pdf_url, title):
        """
        直接从URL下载PDF文件
        :param pdf_url: PDF文件URL
        :param title: 文档标题
        :return: 是否下载成功
        """
        try:
            print(f"直接下载PDF: {pdf_url}")
            
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
            clean_title = self.clean_filename(title)
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
            
            print(f"PDF下载成功: {filename}")
            return True
            
        except Exception as e:
            print(f"直接下载PDF失败: {e}")
            return False
    
    def save_page_content(self, url, title):
        """
        保存页面内容为HTML文件
        :param url: 页面URL
        :param title: 页面标题
        :return: 是否保存成功
        """
        try:
            print("保存页面内容为HTML文件...")
            
            # 获取页面源码
            page_source = self.driver.page_source
            
            # 生成文件名
            clean_title = self.clean_filename(title)
            filename = f"{clean_title}.html"
            filepath = os.path.join(self.download_path, filename)
            
            # 如果文件已存在，添加序号
            counter = 1
            while os.path.exists(filepath):
                filename = f"{clean_title}_{counter}.html"
                filepath = os.path.join(self.download_path, filename)
                counter += 1
            
            # 保存文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(page_source)
            
            print(f"页面内容保存成功: {filename}")
            return True
            
        except Exception as e:
            print(f"保存页面内容失败: {e}")
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
    
    def get_api_data(self, page_num):
        """
        通过API请求获取指定页面的数据
        :param page_num: 页码
        :return: API返回的数据
        """
        import time
        import json
        
        # 构造API请求URL，修改type参数为xzfg获取行政法规
        timestamp = int(time.time() * 1000)  # 生成时间戳
        api_url = f"https://flk.npc.gov.cn/api/?page={page_num}&type=xzfg&searchType=title%3Baccurate&sortTr=f_bbrq_s%3Bdesc&gbrqStart=&gbrqEnd=&sxrqStart=&sxrqEnd=&sort=true&size=10&_={timestamp}"
        
        print(f"请求第 {page_num} 页API数据: {api_url}")
        
        try:
            # 设置请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': 'https://flk.npc.gov.cn/fl.html',
                'Origin': 'https://flk.npc.gov.cn',
            }
            
            response = requests.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 解析JSON数据
            data = response.json()
            print(f"第 {page_num} 页API请求成功，返回数据条数: {len(data.get('result', {}).get('data', []))}")
            return data
            
        except Exception as e:
            print(f"第 {page_num} 页API请求失败: {e}")
            return None
    
    def extract_links_from_api_data(self, api_data):
        """
        从API返回的数据中提取链接信息
        :param api_data: API返回的数据
        :return: 链接列表
        """
        links = []
        
        try:
            # 根据您提供的JSON格式，数据在 result.data 中
            result = api_data.get('result', {})
            data_list = result.get('data', [])
            
            for item in data_list:
                try:
                    # 从JSON数据中提取信息
                    title = item.get('title', '')
                    url_suffix = item.get('url', '')
                    office = item.get('office', '')
                    publish_date = item.get('publish', '')
                    law_type = item.get('type', '')
                    status = item.get('status', '')  # 时效属性
                    
                    if url_suffix:
                        # 如果url是相对路径，需要组合完整URL
                        if url_suffix.startswith('./'):
                            full_url = "https://flk.npc.gov.cn/" + url_suffix[2:]  # 移除 './'
                        elif url_suffix.startswith('/'):
                            full_url = "https://flk.npc.gov.cn" + url_suffix
                        else:
                            full_url = url_suffix
                        
                        # 处理公布日期，删除_00_00_00
                        clean_publish_date = publish_date[:10]

                        
                        # 构造更详细的标题，在法律性质和公布日期之间插入时效属性
                        detailed_title = f"{title} {office} {law_type}"
                        if status=="1":
                            detailed_title += f" 有效"
                        elif status=="3":
                            detailed_title += f" 尚未生效"
                        elif status=="7":
                            detailed_title += f" 异常"

                        if clean_publish_date:
                            detailed_title += f" {clean_publish_date}"
                        
                        links.append({
                            'url': full_url,
                            'title': detailed_title
                        })
                        print(f"从API数据提取链接: {title} - {full_url}")
                    
                except Exception as e:
                    print(f"处理API数据项时出错: {e}")
                    continue
            
        except Exception as e:
            print(f"解析API数据时出错: {e}")
        
        print(f"从API数据中提取到 {len(links)} 个链接")
        return links
    
    def crawl_all_pages(self, base_url, max_pages=50):
        """
        爬取所有页面（通过API翻页）
        :param base_url: 基础URL
        :param max_pages: 最大页面数，防止无限循环
        """
        all_links = []
        
        try:
            self.start_driver()
            
            # 直接通过API获取所有页面的数据
            for page_num in range(1, max_pages + 1):
                print(f"\n{'='*60}")
                print(f"正在处理第 {page_num} 页（通过API）")
                print(f"{'='*60}")
                
                # 获取API数据
                api_data = self.get_api_data(page_num)
                
                if not api_data:
                    print(f"第 {page_num} 页API请求失败，停止翻页")
                    break
                
                # 从API数据中提取链接
                page_links = self.extract_links_from_api_data(api_data)
                
                if not page_links:
                    print(f"第 {page_num} 页未找到任何链接，停止翻页")
                    break
                
                all_links.extend(page_links)
                print(f"第 {page_num} 页找到 {len(page_links)} 个链接")
                
                # 检查是否还有更多页面
                result = api_data.get('result', {})
                total_sizes = result.get('totalSizes', 0)
                current_page = result.get('page', page_num)
                size = result.get('size', 10)
                
                print(f"总数据量: {total_sizes}, 当前页: {current_page}, 每页大小: {size}")
                
                # 如果当前页的数据量小于每页大小，说明已经是最后一页
                if len(page_links) < size:
                    print(f"第 {page_num} 页数据量不足，已到达最后一页")
                    break
                
                # 避免请求过于频繁
                time.sleep(2)
            
            print(f"\n所有页面处理完成！共找到 {len(all_links)} 个链接")
            
            # 逐个处理所有链接
            for i, link_info in enumerate(all_links, 1):
                print(f"\n{'='*50}")
                print(f"进度: {i}/{len(all_links)}")
                self.download_pdf_from_sublink(link_info)
                time.sleep(2)  # 避免请求过于频繁
            
            print(f"\n所有链接处理完成！文件已保存到: {self.download_path}")
            
        except Exception as e:
            print(f"爬取过程中出错: {e}")
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
    # 现在不需要主页面URL，直接通过API获取数据
    base_url = "https://flk.npc.gov.cn/"
    
    # 创建爬虫实例，将下载路径改为"标准"文件夹
    crawler = MemGovCrawler(download_path="./行政法规")
    
    # 直接开始爬取所有页面（通过API）
    print("开始通过API爬取所有页面...")
    max_pages = 100  # 增加最大页面数，因为法律法规数据可能很多
    
    try:
        crawler.crawl_all_pages(base_url, max_pages=max_pages)
    except KeyboardInterrupt:
        print("\n用户中断爬取")
    except Exception as e:
        print(f"\n爬取过程中出错: {e}")

if __name__ == "__main__":
    main() 