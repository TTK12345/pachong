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
    def __init__(self, download_path="./法律法规"):
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
            # 根据您提供的xpath获取所有子链接
            link_elements = self.driver.find_elements(By.XPATH, "//table//tbody//tr//td//a[contains(@href, 'flk.npc.gov.cn')]")
            
            for element in link_elements:
                href = element.get_attribute('href')
                text = element.text.strip()
                if href and 'flk.npc.gov.cn' in href:
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
        从子链接页面下载PDF
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
            
            # 点击下载按钮
            download_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[6]/div/div"))
            )
            download_button.click()
            print("已点击下载按钮")
            time.sleep(2)
            
            # 记录当前窗口
            original_window = self.driver.current_window_handle
            download_success = True
            
            # 检查是否有新窗口打开
            if len(self.driver.window_handles) > 1:
                print("检测到新窗口打开")
                # 切换到新窗口
                self.driver.switch_to.window(self.driver.window_handles[-1])
                time.sleep(2)
                
                try:
                    # 点击PDF格式下载
                    pdf_download_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, "/html/body/div[6]/div/div"))
                    )
                    pdf_download_button.click()
                    print("已点击PDF格式下载")
                    time.sleep(2)
                except Exception as e:
                    print(f"点击PDF下载按钮时出错: {e}")
                
                # 关闭新窗口，切换回原窗口
                self.driver.close()
                self.driver.switch_to.window(original_window)
            else:
                print("未检测到新窗口，可能直接开始下载")
            
        except Exception as e:
            print(f"下载过程中出错: {e}")
            # 确保回到主窗口
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass
        
        # 无论是否成功点击，都等待下载完成并重命名
        if download_success:
            print("等待下载完成...")
            new_files = self.wait_for_download_complete(initial_files, timeout=30)
            
            if new_files:
                print(f"检测到 {len(new_files)} 个新下载的文件")
                for new_file in new_files:
                    # 重命名文件
                    renamed_path = self.rename_downloaded_file(new_file, title)
                    print(f"文件已保存并重命名: {renamed_path}")
            else:
                print("未检测到新下载的文件，可能下载失败")
        
        print(f"已完成处理: {title}")
    
    def crawl_all(self, main_url, max_links=None):
        """
        爬取所有内容
        :param main_url: 主页面URL
        :param max_links: 最大处理链接数，None表示处理所有链接
        """
        try:
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
            
            print(f"\n所有任务完成！文件已保存到: {self.download_path}")
            
        except Exception as e:
            print(f"爬取过程中出错: {e}")
        finally:
            self.close_driver()

def main():
    """主函数"""
    main_url = "https://www.mem.gov.cn/fw/flfgbz/fg/"
    
    # 创建爬虫实例
    crawler = MemGovCrawler(download_path="./法律法规")
    
    # 开始爬取（这里限制为前3个链接进行测试）
    crawler.crawl_all(main_url)

if __name__ == "__main__":
    main() 