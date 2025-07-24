from base_crawler import BaseCrawler
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time

class SystemFileCrawler(BaseCrawler):
    """制度文件爬虫 - 继承自BaseCrawler"""
    
    def __init__(self, download_path="./标准/制度文件", logger=None, task_id=None, socketio=None, progress_callback=None):
        super().__init__(download_path, logger, task_id, socketio, progress_callback)
        self.crawler_type = 'system_file'
    

    
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
        从子链接页面下载PDF附件
        :param sub_link_info: 包含url和title的字典
        """
        url = sub_link_info['url']
        title = sub_link_info['title']
        
        self.log(f"正在处理: {title}")
        self.log(f"访问URL: {url}")
        
        # 记录下载前的文件列表
        initial_files = self.get_files_in_directory()
        self.log(f"下载前文件数量: {len(initial_files)}")
        
        download_success = False
        documents_found = 0
        documents_downloaded = 0
        
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
                        self.log(f"找到 {len(elements)} 个PDF链接，使用选择器: {selector}")
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
                self.log("未找到PDF附件链接", 'warning')
                # 记录失败的链接
                self.stats['failed_links'].append({
                    'url': url,
                    'title': title,
                    'reason': '未找到PDF附件'
                })
                return
            
            documents_found = len(pdf_links)
            self.log(f"找到 {len(pdf_links)} 个PDF附件")
            
            # 逐个下载PDF文件
            for i, pdf_info in enumerate(pdf_links, 1):
                self.log(f"下载第 {i}/{len(pdf_links)} 个PDF: {pdf_info['text']}")
                self.log(f"PDF链接: {pdf_info['url']}")
                
                try:
                    # 方法1: 直接使用requests下载PDF
                    success = self.download_pdf_directly_from_url(pdf_info['url'], title, pdf_info['text'])
                    if success:
                        download_success = True
                        documents_downloaded += 1
                        continue
                    
                    # 方法2: 如果直接下载失败，尝试点击元素
                    self.log("直接下载失败，尝试点击PDF链接...")
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
                            self.log("PDF链接点击成功")
                            clicked = True
                            time.sleep(2)
                            break
                        except Exception as e:
                            self.log(f"点击方法失败: {e}", 'warning')
                            continue
                    
                    if clicked:
                        # 处理可能的新窗口或下载
                        original_window = self.driver.current_window_handle
                        
                        # 检查是否有新窗口
                        if len(self.driver.window_handles) > 1:
                            self.log("检测到新窗口，尝试处理...")
                            self.driver.switch_to.window(self.driver.window_handles[-1])
                            time.sleep(3)
                            
                            # 尝试下载按钮
                            self.try_download_buttons()
                            
                            # 关闭新窗口
                            self.driver.close()
                            self.driver.switch_to.window(original_window)
                        
                        download_success = True
                        documents_downloaded += 1
                    else:
                        self.log("所有点击方法都失败了", 'error')
                    
                except Exception as e:
                    self.log(f"下载PDF时出错: {e}", 'error')
                    # 确保回到主窗口
                    try:
                        if len(self.driver.window_handles) > 1:
                            self.driver.close()
                            self.driver.switch_to.window(self.driver.window_handles[0])
                    except:
                        pass
                
                # 等待下载完成
                if download_success:
                    self.log("等待PDF下载完成...")
                    new_files = self.wait_for_download_complete(initial_files, timeout=15)
                    
                    if new_files:
                        for new_file in new_files:
                            pdf_title = f"{title}_{self.clean_filename(pdf_info['text'])}_{i}"
                            renamed_path = self.rename_downloaded_file(new_file, pdf_title)
                            self.log(f"PDF已保存: {renamed_path}", 'success')
                        # 更新文件列表
                        initial_files = self.get_files_in_directory()
                    else:
                        self.log("未检测到新的PDF文件", 'warning')
                
                time.sleep(1)
            
        except Exception as e:
            self.log(f"处理页面时出错: {e}", 'error')
            # 记录失败的链接
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
        
        # 更新统计信息
        self.stats['total_documents'] += documents_found
        self.stats['successful_downloads'] += documents_downloaded
        self.stats['failed_downloads'] += (documents_found - documents_downloaded)
        
        self.log(f"已完成处理: {title} (找到{documents_found}个文档，成功下载{documents_downloaded}个)")

def main():
    """主函数 - 用于独立测试"""
    base_url = "https://www.mem.gov.cn/fw/flfgbz/bz/bzgg/"
    
    # 创建爬虫实例
    crawler = SystemFileCrawler(download_path="./标准/制度文件")
    
    # 开始爬取所有页面（自动翻页）
    print("开始爬取所有页面...")
    max_pages = 1000
    
    try:
        crawler.crawl_all_pages(base_url, max_pages=max_pages)
    except KeyboardInterrupt:
        print("\n用户中断爬取")
    except Exception as e:
        print(f"\n爬取过程中出错: {e}")

if __name__ == "__main__":
    main() 