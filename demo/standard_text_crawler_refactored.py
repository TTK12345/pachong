from base_crawler import BaseCrawler
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time

class StandardTextCrawler(BaseCrawler):
    """标准文本爬虫 - 继承自BaseCrawler"""
    
    def __init__(self, download_path="./标准/标准文本", logger=None, task_id=None, socketio=None, progress_callback=None):
        super().__init__(download_path, logger, task_id, socketio, progress_callback)
        self.crawler_type = 'standard_text'
    

    
    def get_sub_links(self, main_url):
        """
        获取主页面的子链接
        :param main_url: 主页面URL
        :return: 子链接列表
        """
        self.log(f"正在访问列表页面: {main_url}")
        self.driver.get(main_url)
        time.sleep(3)
        
        sub_links = []
        try:
            # 根据具体XPath获取所有子链接
            self.log("尝试获取主页面链接...")
            link_elements = self.driver.find_elements(By.XPATH, "//div[4]//div[5]//div[1]//div//ul/li/a")
            
            # 如果上面的XPath没有找到元素，尝试更通用的路径
            if not link_elements:
                self.log("尝试备用XPath路径...")
                link_elements = self.driver.find_elements(By.XPATH, "//ul/li/a[contains(@href, '.shtml')]")
                
            # 如果还是没有找到，尝试最通用的路径
            if not link_elements:
                self.log("尝试最通用XPath路径...")
                link_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'fdzdgknr') or contains(@href, 'tzgg')]")
            
            for element in link_elements:
                href = element.get_attribute('href')
                text = element.text.strip()
                if href and text:
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
        从子链接页面直接下载内容
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
            
            # 方法1: 尝试直接下载页面内容（如果是PDF页面）
            current_url = self.driver.current_url
            if '.pdf' in current_url.lower():
                self.log("检测到PDF页面，直接下载...")
                success = self.download_pdf_directly_from_url(current_url, title)
                if success:
                    self.log("PDF页面下载成功", 'success')
                    self.stats['successful_downloads'] += 1
                    return
            
            # 方法2: 查找页面中的下载按钮
            download_selectors = [
                "//a[contains(text(), '下载')]",
                "//button[contains(text(), '下载')]",
                "//a[contains(@class, 'download')]",
                "//button[contains(@class, 'download')]",
                "//a[contains(text(), 'PDF')]",
                "//a[contains(text(), '附件')]",
                "//span[contains(text(), '下载')]/parent::a",
                "//div[contains(@class, 'download')]//a"
            ]
            
            download_button = None
            for selector in download_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        download_button = elements[0]  # 取第一个找到的下载按钮
                        self.log(f"找到下载按钮，使用选择器: {selector}")
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
                    self.log("已点击下载按钮")
                    time.sleep(3)
                    download_success = True
                    
                    # 处理可能的新窗口
                    original_window = self.driver.current_window_handle
                    if len(self.driver.window_handles) > 1:
                        self.log("检测到新窗口")
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                        time.sleep(2)
                        
                        # 在新窗口中尝试下载
                        new_url = self.driver.current_url
                        if '.pdf' in new_url.lower():
                            self.log("新窗口是PDF，直接下载...")
                            self.download_pdf_directly_from_url(new_url, title)
                        else:
                            # 在新窗口中查找下载按钮
                            self.try_download_buttons()
                        
                        # 关闭新窗口
                        self.driver.close()
                        self.driver.switch_to.window(original_window)
                    
                except Exception as e:
                    self.log(f"点击下载按钮失败: {e}", 'error')
            
            # 方法3: 如果没有找到下载按钮，尝试使用快捷键下载页面
            if not download_success:
                self.log("未找到下载按钮，尝试使用快捷键保存页面...")
                try:
                    self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.CONTROL + 's')
                    time.sleep(3)
                    download_success = True
                except Exception as e:
                    self.log(f"快捷键下载失败: {e}", 'error')
            
            # 方法4: 如果以上都失败，尝试保存页面源码
            if not download_success:
                self.log("尝试保存页面内容...")
                success = self.save_page_content(url, title)
                if success:
                    download_success = True
                    self.log("页面内容保存成功")
            
            # 等待下载完成
            if download_success:
                self.log("等待下载完成...")
                new_files = self.wait_for_download_complete(initial_files, timeout=15)
                
                if new_files:
                    for new_file in new_files:
                        renamed_path = self.rename_downloaded_file(new_file, title)
                        self.log(f"文件已保存: {renamed_path}", 'success')
                    self.stats['successful_downloads'] += 1
                else:
                    self.log("未检测到新下载的文件", 'warning')
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
                    'reason': '下载失败'
                })
            
        except Exception as e:
            self.log(f"处理页面时出错: {e}", 'error')
            self.stats['failed_downloads'] += 1
            self.stats['failed_links'].append({
                'url': url,
                'title': title,
                'reason': f'处理页面时出错: {str(e)}'
            })
            # 确保回到主窗口
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass
        
        self.log(f"已完成处理: {title}")

def main():
    """主函数"""
    print("这是一个模块文件，请通过主程序 app.py 运行。")

if __name__ == "__main__":
    main() 