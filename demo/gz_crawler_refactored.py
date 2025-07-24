from base_crawler import BaseCrawler
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.support import expected_conditions as EC

class GzCrawler(BaseCrawler):
    """规章爬虫 - 继承自BaseCrawler"""
    
    def __init__(self, download_path="./规章", logger=None, task_id=None, socketio=None, progress_callback=None):
        super().__init__(download_path, logger, task_id, socketio, progress_callback)
        self.crawler_type = 'gz'
    

    
    def generate_page_url(self, base_url, page_num):
        """
        生成指定页面的URL
        :param base_url: 基础URL（这里不使用，直接用固定的基础URL）
        :param page_num: 页面编号（0表示第一页）
        :return: 页面URL
        """
        base_url = "https://www.mem.gov.cn/gk/zfxxgkpt/fdzdgknr/gz11/"
        if page_num == 0:
            return f"{base_url}index.shtml"
        else:
            return f"{base_url}index_{page_num}.shtml"
    
    def get_sub_links(self, main_url):
        """
        获取主页面的子链接（规章页面的文档信息）
        :param main_url: 主页面URL
        :return: 子链接列表
        """
        self.log(f"正在访问规章页面: {main_url}")
        
        # 直接访问iframe页面
        self.driver.get(main_url)
        
        # 等待页面加载
        self.log("等待页面加载...")
        time.sleep(8)
        
        documents = []
        
        try:
            # 等待表格加载
            try:
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
                self.log("表格已加载")
            except:
                self.log("等待表格超时", 'warning')
                return documents
            
            # 查找表格
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            self.log(f"找到 {len(tables)} 个表格")
            
            if tables:
                table = tables[0]
                rows = table.find_elements(By.TAG_NAME, "tr")
                self.log(f"表格有 {len(rows)} 行")
                
                # 从第2行开始遍历（跳过表头）
                for row_num in range(2, len(rows) + 1):
                    try:
                        self.log(f"检查第 {row_num} 行...")
                        
                        # 使用相对xpath
                        title_xpath = f"//table//tr[{row_num}]/td[2]//a"
                        download_xpath = f"//table//tr[{row_num}]/td[3]//a[1]"
                        
                        title_element = None
                        download_element = None
                        
                        # 查找标题元素
                        try:
                            title_elements = self.driver.find_elements(By.XPATH, title_xpath)
                            if title_elements:
                                title_element = title_elements[0]
                                self.log(f"  找到标题元素")
                        except Exception as e:
                            self.log(f"  查找标题元素时出错: {e}", 'warning')
                        
                        # 查找下载元素
                        try:
                            download_elements = self.driver.find_elements(By.XPATH, download_xpath)
                            if download_elements:
                                download_element = download_elements[0]
                                self.log(f"  找到下载元素")
                        except Exception as e:
                            self.log(f"  查找下载元素时出错: {e}", 'warning')
                        
                        if title_element and download_element:
                            file_name = title_element.text.strip()
                            download_url = download_element.get_attribute('href')
                            
                            if file_name and download_url:
                                documents.append({
                                    'url': download_url,
                                    'title': file_name,
                                    'download_element': download_element,
                                    'row_index': row_num
                                })
                                self.log(f"  成功找到文档: {file_name}")
                                self.log(f"  下载链接: {download_url}")
                            else:
                                self.log(f"  第 {row_num} 行：文件名或下载链接为空", 'warning')
                        else:
                            self.log(f"  第 {row_num} 行：未找到必要元素", 'warning')
                            # 如果连续多行都没有元素，可能到了表格末尾
                            if row_num > 5:  # 给一些容错空间
                                break
                    
                    except Exception as e:
                        self.log(f"  处理第 {row_num} 行时出错: {e}", 'error')
                        continue
                
        except Exception as e:
            self.log(f"获取规章文档信息时出错: {e}", 'error')
        
        self.log(f"找到 {len(documents)} 个规章文档")
        # 更新统计信息
        self.stats['total_sub_links'] += len(documents)
        return documents
    
    def download_from_sublink(self, doc_info):
        """
        从子链接下载文档
        :param doc_info: 文档信息字典
        """
        name = doc_info['title']
        download_url = doc_info['url']
        
        self.log(f"\n正在处理: {name}")
        self.log(f"下载URL: {download_url}")
        
        # 记录下载前的文件列表
        initial_files = self.get_files_in_directory()
        self.log(f"下载前文件数量: {len(initial_files)}")
        
        download_success = False
        
        # 统计：每处理一个文档
        self.stats['total_documents'] += 1
        
        try:
            # 直接访问下载链接
            self.driver.get(download_url)
            self.log("已访问下载链接")
            time.sleep(8)  # 增加等待时间
            
            # 获取当前URL
            current_url = self.driver.current_url
            self.log(f"当前URL: {current_url}")
            
            # 无论URL是什么，都认为下载可能已经开始
            download_success = True
            self.log("假设下载已开始...")
                
        except Exception as e:
            self.log(f"访问下载链接时出错: {e}", 'error')
            download_success = True  # 即使出错也检查文件
        
        # 等待下载完成并重命名
        if download_success:
            self.log("等待下载完成...")
            new_files = self.wait_for_download_complete(initial_files, timeout=30)
            
            if new_files:
                self.log(f"检测到 {len(new_files)} 个新下载的文件")
                for new_file in new_files:
                    # 重命名文件
                    renamed_path = self.rename_downloaded_file(new_file, name)
                    self.log(f"文件已保存并重命名: {renamed_path}", 'success')
                self.stats['successful_downloads'] += 1
                return True
            else:
                self.log("未检测到新下载的文件", 'warning')
                self.stats['failed_downloads'] += 1
                self.stats['failed_links'].append({
                    'url': download_url,
                    'title': name,
                    'reason': '未检测到新下载的文件'
                })
                return False
        
        self.stats['failed_downloads'] += 1
        self.stats['failed_links'].append({
            'url': download_url,
            'title': name,
            'reason': '下载过程失败'
        })
        return False
    


def main():
    """主函数"""
    # 创建规章爬虫实例
    crawler = GzCrawler(download_path="./规章")
    
    # 开始爬取所有页面的所有文档
    base_url = "https://www.mem.gov.cn/gk/zfxxgkpt/fdzdgknr/gz11/"
    crawler.crawl_all_pages(base_url, max_pages=10)

if __name__ == "__main__":
    main() 