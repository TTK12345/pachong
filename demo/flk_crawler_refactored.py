import time
import os
import re
import json
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from base_crawler import BaseCrawler


class FlkCrawler(BaseCrawler):
    """
    国家法律法规数据库爬虫
    支持多种法规类型：宪法、法律、行政法规、监察法规、司法解释、地方性法规
    """
    
    # 法规类型配置
    FLK_TYPES = {
        'flk_xf': {
            'name': '宪法',
            'api_type': 'xffl',
            'referer': 'https://flk.npc.gov.cn/xf.html'
        },
        'flk_fl': {
            'name': '法律',
            'api_type': 'flfg',
            'referer': 'https://flk.npc.gov.cn/fl.html'
        },
        'flk_xzfg': {
            'name': '行政法规',
            'api_type': 'xzfg',
            'referer': 'https://flk.npc.gov.cn/xzfg.html'
        },
        'flk_jcfg': {
            'name': '监察法规',
            'api_type': 'jcfg',
            'referer': 'https://flk.npc.gov.cn/jcfg.html'
        },
        'flk_sfjs': {
            'name': '司法解释',
            'api_type': 'sfjs',
            'referer': 'https://flk.npc.gov.cn/sfjs.html'
        },
        'flk_dfxfg': {
            'name': '地方性法规',
            'api_type': 'dfxfg',
            'referer': 'https://flk.npc.gov.cn/dfxfg.html'
        }
    }
    
    def __init__(self, download_path, flk_type='flk_fl', logger=None, task_id=None, socketio=None, progress_callback=None):
        """
        初始化法规库爬虫
        :param download_path: 下载文件保存路径
        :param flk_type: 法规类型，支持: flk_xf, flk_fl, flk_xzfg, flk_jcfg, flk_sfjs, flk_dfxfg
        :param logger: 日志记录器
        :param task_id: 任务ID
        :param socketio: SocketIO实例
        :param progress_callback: 进度更新回调函数
        """
        super().__init__(download_path, logger, task_id, socketio, progress_callback)
        
        if flk_type not in self.FLK_TYPES:
            raise ValueError(f"不支持的法规类型: {flk_type}，支持的类型: {list(self.FLK_TYPES.keys())}")
        
        self.flk_type = flk_type
        self.flk_config = self.FLK_TYPES[flk_type]
        self.log(f"初始化法规库爬虫: {self.flk_config['name']}")
        
        # API配置
        self.base_api_url = "https://flk.npc.gov.cn/api/"
        self.base_url = "https://flk.npc.gov.cn/"
        
    def get_api_data(self, page_num):
        """
        通过API请求获取指定页面的数据
        :param page_num: 页码
        :return: API返回的数据
        """
        timestamp = int(time.time() * 1000)  # 生成时间戳
        
        # 构造API请求URL
        params = {
            'page': page_num,
            'type': self.flk_config['api_type'],
            'searchType': 'title;accurate',
            'sortTr': 'f_bbrq_s;desc',
            'gbrqStart': '',
            'gbrqEnd': '',
            'sxrqStart': '',
            'sxrqEnd': '',
            'sort': 'true',
            'size': 10,
            '_': timestamp
        }
        
        # 移除宪法的sort参数（根据原始代码）
        if self.flk_type == 'flk_xf':
            params.pop('sort', None)
        
        api_url = self.base_api_url + '?' + '&'.join([f"{k}={v}" for k, v in params.items()])
        self.log(f"请求第 {page_num} 页API数据: {self.flk_config['name']}")
        
        try:
            # 设置请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': self.flk_config['referer'],
                'Origin': 'https://flk.npc.gov.cn',
            }
            
            response = requests.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 解析JSON数据
            data = response.json()
            result_data = data.get('result', {}).get('data', [])
            self.log(f"第 {page_num} 页API请求成功，返回数据条数: {len(result_data)}")
            return data
            
        except Exception as e:
            self.log(f"第 {page_num} 页API请求失败: {e}", 'error')
            return None
    
    def extract_links_from_api_data(self, api_data):
        """
        从API返回的数据中提取链接信息
        :param api_data: API返回的数据
        :return: 链接列表
        """
        links = []
        
        try:
            # 根据API响应格式，数据在 result.data 中
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
                    
                    if url_suffix and title:
                        # 如果url是相对路径，需要组合完整URL
                        if url_suffix.startswith('./'):
                            full_url = self.base_url + url_suffix[2:]  # 移除 './'
                        elif url_suffix.startswith('/'):
                            full_url = self.base_url + url_suffix[1:]
                        else:
                            full_url = url_suffix
                        
                        # 处理公布日期，删除时间部分
                        clean_publish_date = publish_date[:10] if publish_date else ''
                        
                        link_info = {
                            'title': title,
                            'url': full_url,
                            'office': office,
                            'publish_date': clean_publish_date,
                            'type': law_type,
                            'status': status
                        }
                        
                        links.append(link_info)
                        self.log(f"提取链接: {title[:50]}{'...' if len(title) > 50 else ''}")
                        
                except Exception as e:
                    self.log(f"处理API数据项时出错: {e}", 'error')
                    continue
            
        except Exception as e:
            self.log(f"解析API数据时出错: {e}", 'error')
        
        self.log(f"从API数据中提取到 {len(links)} 个链接")
        return links
    
    def get_sub_links(self, main_url):
        """
        获取主页面的子链接（通过API）
        :param main_url: 主页面URL（这里不使用，直接通过API获取）
        :return: 子链接列表
        """
        self.log(f"开始获取 {self.flk_config['name']} 的子链接")
        all_links = []
        page_num = 1
        max_pages = 100  # 防止无限循环
        
        while page_num <= max_pages:
            if self.is_stopped:
                self.log("爬取被停止")
                break
                
            self.log(f"正在处理第 {page_num} 页")
            
            # 获取API数据
            api_data = self.get_api_data(page_num)
            
            if not api_data:
                self.log(f"第 {page_num} 页API请求失败，停止翻页")
                break
            
            # 从API数据中提取链接
            page_links = self.extract_links_from_api_data(api_data)
            
            if not page_links:
                self.log(f"第 {page_num} 页未找到任何链接，停止翻页")
                break
            
            all_links.extend(page_links)
            self.log(f"第 {page_num} 页找到 {len(page_links)} 个链接")
            
            # 检查是否还有更多页面
            result = api_data.get('result', {})
            total_sizes = result.get('totalSizes', 0)
            current_page = result.get('page', page_num)
            size = result.get('size', 10)
            
            self.log(f"总数据量: {total_sizes}, 当前页: {current_page}, 每页大小: {size}")
            
            # 如果当前页的数据量小于每页大小，说明已经是最后一页
            if len(page_links) < size:
                self.log(f"第 {page_num} 页数据量不足，已到达最后一页")
                break
            
            page_num += 1
            time.sleep(2)  # 避免请求过于频繁
        
        self.log(f"获取子链接完成！共找到 {len(all_links)} 个链接")
        self.stats['total_sub_links'] = len(all_links)
        return all_links
    
    def clean_filename(self, filename):
        """
        清理文件名，移除不合法的字符
        :param filename: 原始文件名
        :return: 清理后的文件名
        """
        # 移除或替换不合法的字符
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        
        # 移除多余的空格和换行符
        filename = re.sub(r'\s+', ' ', filename).strip()
        
        # 限制文件名长度
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename
    
    def get_download_files(self):
        """
        获取下载目录中的所有文件信息
        :return: 文件信息列表
        """
        files = []
        if os.path.exists(self.download_path):
            for filename in os.listdir(self.download_path):
                file_path = os.path.join(self.download_path, filename)
                if os.path.isfile(file_path):
                    stat = os.stat(file_path)
                    files.append({
                        'name': filename,
                        'path': file_path,
                        'size': stat.st_size,
                        'mtime': stat.st_mtime
                    })
        return files
    
    def wait_for_download_complete(self, initial_files, timeout=30):
        """
        等待下载完成
        :param initial_files: 初始文件列表
        :param timeout: 超时时间（秒）
        :return: 新下载的文件列表
        """
        self.log("等待下载完成...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.is_stopped:
                return []
                
            current_files = self.get_download_files()
            new_files = []
            
            # 查找新文件
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
                time.sleep(3)  # 等待文件稳定
                stable_files = []
                for new_file in new_files:
                    # 检查文件是否下载完成（不是临时文件）
                    if not new_file['name'].endswith('.crdownload') and not new_file['name'].endswith('.tmp'):
                        stable_files.append(new_file)
                        self.log(f"发现稳定文件: {new_file['name']}")
                
                if stable_files:
                    return stable_files
            
            time.sleep(1)
        
        self.log(f"等待超时，未检测到新文件")
        return []
    
    def rename_downloaded_file(self, file_info, new_name):
        """
        重命名下载的文件
        :param file_info: 文件信息字典
        :param new_name: 新的文件名（不包含扩展名）
        :return: 新文件路径
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
            self.log(f"文件已重命名: {old_name} -> {new_filename}")
            return new_path
            
        except Exception as e:
            self.log(f"重命名文件时出错: {e}", 'error')
            return file_info['path']
    
    def download_pdf_directly_from_url(self, pdf_url, title):
        """
        直接从URL下载PDF文件
        :param pdf_url: PDF文件URL
        :param title: 文档标题
        :return: 是否下载成功
        """
        try:
            self.log(f"直接下载PDF: {pdf_url}")
            
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
            file_path = os.path.join(self.download_path, filename)
            
            # 如果文件已存在，添加序号
            counter = 1
            while os.path.exists(file_path):
                filename = f"{clean_title}_{counter}.pdf"
                file_path = os.path.join(self.download_path, filename)
                counter += 1
            
            # 保存文件
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            self.log(f"PDF文件下载成功: {filename}")
            return True
            
        except Exception as e:
            self.log(f"直接下载PDF失败: {e}", 'error')
            return False
    
    def save_page_content(self, url, title):
        """
        保存页面内容为HTML文件
        :param url: 页面URL
        :param title: 页面标题
        :return: 是否保存成功
        """
        try:
            page_source = self.driver.page_source
            
            # 生成文件名
            clean_title = self.clean_filename(title)
            filename = f"{clean_title}.html"
            file_path = os.path.join(self.download_path, filename)
            
            # 如果文件已存在，添加序号
            counter = 1
            while os.path.exists(file_path):
                filename = f"{clean_title}_{counter}.html"
                file_path = os.path.join(self.download_path, filename)
                counter += 1
            
            # 保存页面内容
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(page_source)
            
            self.log(f"页面内容已保存: {filename}")
            return True
            
        except Exception as e:
            self.log(f"保存页面内容失败: {e}", 'error')
            return False
    
    def try_download_buttons(self):
        """
        尝试点击页面上的各种下载按钮
        :return: 是否成功点击
        """
        download_selectors = [
            "//a[contains(text(), '下载')]",
            "//button[contains(text(), '下载')]",
            "//a[contains(@href, '.pdf')]",
            "//a[contains(@class, 'download')]",
            "//button[contains(@class, 'download')]",
            "//input[@type='button' and contains(@value, '下载')]"
        ]
        
        for selector in download_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                if elements:
                    for element in elements:
                        try:
                            # 滚动到元素位置
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                            time.sleep(1)
                            
                            # 点击元素
                            element.click()
                            self.log(f"成功点击下载按钮: {selector}")
                            time.sleep(3)
                            return True
                        except Exception as e:
                            continue
            except Exception as e:
                continue
        
        return False
    
    def download_from_sublink(self, sub_link_info):
        """
        从子链接下载内容
        :param sub_link_info: 子链接信息字典，包含title, url等
        """
        if self.is_stopped:
            return
            
        title = sub_link_info.get('title', '未知文档')
        url = sub_link_info.get('url', '')
        
        if not url:
            self.log(f"跳过无效链接: {title}", 'warning')
            return
        
        self.log(f"正在处理: {title[:50]}{'...' if len(title) > 50 else ''}")
        
        try:
            # 记录下载前的文件
            initial_files = self.get_download_files()
            
            # 访问详情页面
            self.driver.get(url)
            time.sleep(3)
            
            download_success = False
            
            # 方法1: 查找并点击下载按钮
            if self.try_download_buttons():
                download_success = True
                self.log("通过下载按钮下载成功")
                
                # 处理可能的新窗口
                original_window = self.driver.current_window_handle
                if len(self.driver.window_handles) > 1:
                    self.log("检测到新窗口")
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    time.sleep(2)
                    
                    # 在新窗口中检查是否是PDF
                    new_url = self.driver.current_url
                    if '.pdf' in new_url.lower():
                        self.log("新窗口是PDF，直接下载...")
                        self.download_pdf_directly_from_url(new_url, title)
                    else:
                        # 在新窗口中再次尝试下载
                        self.try_download_buttons()
                    
                    # 关闭新窗口
                    self.driver.close()
                    self.driver.switch_to.window(original_window)
            
            # 方法2: 如果没有找到下载按钮，尝试使用快捷键下载页面
            if not download_success:
                self.log("未找到下载按钮，尝试使用快捷键保存页面...")
                try:
                    self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.CONTROL + 's')
                    time.sleep(3)
                    download_success = True
                except Exception as e:
                    self.log(f"快捷键下载失败: {e}", 'error')
            
            # 方法3: 如果以上都失败，尝试保存页面源码
            if not download_success:
                self.log("尝试保存页面内容...")
                if self.save_page_content(url, title):
                    download_success = True
                    self.log("页面内容保存成功")
            
            # 等待下载完成并重命名文件
            if download_success:
                self.log("等待下载完成...")
                new_files = self.wait_for_download_complete(initial_files, timeout=15)
                
                if new_files:
                    for new_file in new_files:
                        renamed_path = self.rename_downloaded_file(new_file, title)
                        self.log(f"文件已保存: {os.path.basename(renamed_path)}")
                    self.stats['successful_downloads'] += 1
                else:
                    self.log("未检测到新下载的文件", 'warning')
                    self.stats['failed_downloads'] += 1
            else:
                self.stats['failed_downloads'] += 1
                
        except Exception as e:
            self.log(f"处理页面时出错: {e}", 'error')
            self.stats['failed_downloads'] += 1
            # 确保回到主窗口
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass
        
        self.log(f"已完成处理: {title[:30]}{'...' if len(title) > 30 else ''}")
    
    def crawl_all_pages(self, base_url, max_pages=10):
        """
        爬取所有页面（通过API翻页）
        :param base_url: 基础URL（这里不使用，通过API获取数据）
        :param max_pages: 最大页面数，防止无限循环
        """
        try:
            # 处理max_pages=0的情况（表示无限制）
            if max_pages == 0:
                max_pages = 999999
                self.log("设置为无限制页数模式")
            
            if not self.driver:
                self.start_driver()
            
            # 通过API获取所有子链接
            self.log(f"开始通过API获取 {self.flk_config['name']} 的数据...")
            all_links = self.get_sub_links(base_url)
            
            if not all_links:
                self.log("未找到任何子链接", 'warning')
                return
            
            self.total_sub_links_count = len(all_links)
            self.log(f"共找到 {self.total_sub_links_count} 个子链接，开始下载...")
            
            # 逐个处理所有链接
            for i, link_info in enumerate(all_links, 1):
                if self.is_stopped:
                    self.log("爬虫已停止", 'warning')
                    break
                
                self.log(f"\n{'='*50}")
                self.log(f"进度: {i}/{len(all_links)}")
                
                # 更新进度
                if not self.update_progress(i, len(all_links), link_info.get('title', '')):
                    break
                
                self.download_from_sublink(link_info)
                self.completed_sub_links_count += 1
                time.sleep(2)  # 避免请求过于频繁
            
            # 生成最终统计信息
            self.log(f"\n{'='*60}")
            self.log(f"爬取完成！")
            self.log(f"总链接数: {self.total_sub_links_count}")
            self.log(f"成功下载: {self.stats['successful_downloads']}")
            self.log(f"失败下载: {self.stats['failed_downloads']}")
            self.log(f"下载成功率: {(self.stats['successful_downloads'] / self.total_sub_links_count * 100):.2f}%" if self.total_sub_links_count > 0 else "0%")
            self.log(f"文件已保存到: {self.download_path}")
            
        except Exception as e:
            self.log(f"爬取过程中出错: {e}", 'error')
        finally:
            self.close_driver()


def main():
    """测试函数"""
    import logging
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    # 创建爬虫实例
    crawler = FlkCrawler(
        download_path="./法规库-法律",
        flk_type='flk_fl',  # 法律类型
        logger=logger
    )
    
    try:
        print("开始测试法规库爬虫...")
        
        # 启动驱动
        crawler.start_driver()
        
        # 测试获取子链接（只获取前2页）
        sub_links = crawler.get_sub_links("https://flk.npc.gov.cn/fl.html")
        
        if sub_links:
            print(f"获取到 {len(sub_links)} 个子链接")
            
            # 测试下载前3个链接
            test_links = sub_links[:3]
            for i, link in enumerate(test_links, 1):
                print(f"\n测试下载 {i}/{len(test_links)}: {link['title'][:50]}")
                crawler.download_from_sublink(link)
                
        else:
            print("未获取到任何子链接")
            
    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"\n测试过程中出错: {e}")
    finally:
        crawler.close_driver()
        print("\n测试完成")


if __name__ == "__main__":
    main() 