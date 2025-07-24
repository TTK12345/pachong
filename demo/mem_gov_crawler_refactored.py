from base_crawler import BaseCrawler
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time

class MemGovCrawler(BaseCrawler):
    """法律法规爬虫 - 继承自BaseCrawler"""
    
    def __init__(self, download_path="./法律法规", logger=None, task_id=None, socketio=None, progress_callback=None):
        super().__init__(download_path, logger, task_id, socketio, progress_callback)
        self.crawler_type = 'memgov'
    
    def generate_page_url(self, base_url, page_num):
        """
        生成指定页面的URL（法律法规只有第一页）
        :param base_url: 基础URL
        :param page_num: 页面编号（0表示第一页）
        :return: 页面URL
        """
        if page_num == 0:
            # 第一页：返回原始URL
            return base_url.rstrip('/')
        else:
            # 其他页：返回不存在的URL，让check_page_exists检测到不存在
            return f"{base_url}nonexistent_page_{page_num}.html"
    
    def get_sub_links(self, main_url):
        """
        获取主页面的子链接
        :param main_url: 主页面URL
        :return: 子链接列表
        """
        self.log(f"正在访问主页面: {main_url}")
        self.driver.get(main_url)
        time.sleep(3)
        
        sub_links = []
        try:
            # 根据具体的xpath获取所有子链接
            link_elements = self.driver.find_elements(By.XPATH, "//table//tbody//tr//td//a[contains(@href, 'flk.npc.gov.cn')]")
            
            for element in link_elements:
                href = element.get_attribute('href')
                text = element.text.strip()
                if href and 'flk.npc.gov.cn' in href:
                    sub_links.append({
                        'url': href,
                        'title': text
                    })
                    self.log(f"找到子链接: {text} - {href}")
            
        except Exception as e:
            self.log(f"获取子链接时出错: {e}", 'error')
        
        self.log(f"共找到 {len(sub_links)} 个子链接")
        # 更新统计信息
        self.stats['total_sub_links'] += len(sub_links)
        return sub_links
    
    def download_from_sublink(self, sub_link_info):
        """
        从子链接页面下载PDF
        :param sub_link_info: 包含url和title的字典
        """
        url = sub_link_info['url']
        title = sub_link_info['title']
        
        self.log(f"\n正在处理: {title}")
        self.log(f"访问URL: {url}")
        
        # 记录下载前的文件列表
        initial_files = self.get_files_in_directory()
        self.log(f"下载前文件数量: {len(initial_files)}")
        
        download_success = False
        
        # 统计：每处理一个子链接
        self.stats['total_documents'] += 1
        
        try:
            self.driver.get(url)
            time.sleep(3)
            
            # 点击下载按钮
            download_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[6]/div/div"))
            )
            download_button.click()
            self.log("已点击下载按钮")
            time.sleep(2)
            
            # 记录当前窗口
            original_window = self.driver.current_window_handle
            download_success = True
            
            # 检查是否有新窗口打开
            if len(self.driver.window_handles) > 1:
                self.log("检测到新窗口打开")
                # 切换到新窗口
                self.driver.switch_to.window(self.driver.window_handles[-1])
                time.sleep(2)
                
                try:
                    # 点击PDF格式下载
                    pdf_download_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, "/html/body/div[6]/div/div"))
                    )
                    pdf_download_button.click()
                    self.log("已点击PDF格式下载")
                    time.sleep(2)
                except Exception as e:
                    self.log(f"点击PDF下载按钮时出错: {e}", 'warning')
                
                # 关闭新窗口，切换回原窗口
                self.driver.close()
                self.driver.switch_to.window(original_window)
            else:
                self.log("未检测到新窗口，可能直接开始下载")
            
        except Exception as e:
            self.log(f"下载过程中出错: {e}", 'error')
            # 确保回到主窗口
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass
        
        # 等待下载完成并重命名
        if download_success:
            self.log("等待下载完成...")
            new_files = self.wait_for_download_complete(initial_files, timeout=30)
            
            if new_files:
                self.log(f"检测到 {len(new_files)} 个新下载的文件")
                for new_file in new_files:
                    # 重命名文件
                    renamed_path = self.rename_downloaded_file(new_file, title)
                    self.log(f"文件已保存并重命名: {renamed_path}", 'success')
                self.stats['successful_downloads'] += 1
            else:
                self.log("未检测到新下载的文件，可能下载失败", 'warning')
                self.stats['failed_downloads'] += 1
                self.stats['failed_links'].append({
                    'url': url,
                    'title': title,
                    'reason': '未检测到新下载的文件'
                })
        else:
            self.stats['failed_downloads'] += 1
            self.stats['failed_links'].append({
                'url': url,
                'title': title,
                'reason': '下载过程失败'
            })
        
        self.log(f"已完成处理: {title}")

def main():
    """主函数"""
    base_url = "https://www.mem.gov.cn/fw/flfgbz/fg/"
    
    # 创建爬虫实例
    crawler = MemGovCrawler(download_path="./法律法规")
    
    # 开始爬取（单页面，max_pages=1）
    crawler.crawl_all_pages(base_url, max_pages=1)

if __name__ == "__main__":
    main() 