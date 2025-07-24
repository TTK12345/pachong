# 爬虫重构说明

## 重构概述

本次重构将原来的5个独立爬虫文件重构为一个基类 + 5个子类的架构，提高了代码的可维护性和可扩展性。

## 文件结构

### 基类
- `base_crawler.py` - 基础爬虫类，包含所有爬虫的共同功能

### 子类（重构后）
- `gz_crawler_refactored.py` - 规章爬虫
- `mem_gov_crawler_refactored.py` - 法律法规爬虫
- `normative_file_crawler_refactored.py` - 规范性文件爬虫
- `standard_text_crawler_refactored.py` - 标准文本爬虫
- `system_file_crawler_refactored.py` - 制度文件爬虫

### 原始文件（保留）
- `gz_crawler_final.py` - 原始规章爬虫
- `mem_gov_crawler_final.py` - 原始法律法规爬虫
- `normative_file_crawler.py` - 原始规范性文件爬虫
- `standard_text_crawler.py` - 原始标准文本爬虫
- `system_file_crawler.py` - 原始制度文件爬虫

### 使用示例
- `crawler_usage_example.py` - 使用示例和测试脚本

## 基类功能（BaseCrawler）

### 通用功能
1. **浏览器驱动管理**
   - `start_driver()` - 启动浏览器驱动
   - `close_driver()` - 关闭浏览器驱动
   - `_setup_chrome_options()` - 设置Chrome选项

2. **日志记录**
   - `log(message, level)` - 统一的日志记录方法

3. **文件管理**
   - `clean_filename(filename)` - 清理文件名
   - `get_files_in_directory()` - 获取目录中的文件
   - `wait_for_download_complete()` - 等待下载完成
   - `rename_downloaded_file()` - 重命名下载的文件

4. **下载功能**
   - `download_pdf_directly_from_url()` - 直接从URL下载PDF
   - `try_download_buttons()` - 尝试点击下载按钮
   - `save_page_content()` - 保存页面内容为HTML

5. **页面处理**
   - `check_page_exists()` - 检查页面是否存在
   - `generate_page_url()` - 生成页面URL（默认实现）

6. **统计和报告**
   - `print_summary_report()` - 输出详细的总结报告
   - 统计信息收集和管理

7. **主要流程控制**
   - `crawl_all_pages()` - 爬取所有页面（支持翻页）
   - `crawl_all()` - 爬取单个页面的所有内容

### 抽象方法（需要子类实现）
- `get_sub_links(main_url)` - 获取主页面的子链接
- `download_from_sublink(sub_link_info)` - 从子链接下载内容

## 子类特化

### 1. GzCrawler（规章爬虫）
- **特点**: 处理表格形式的文档列表
- **URL模式**: 支持翻页（index.shtml, index_1.shtml, ...）
- **下载方式**: 直接访问下载链接
- **特殊方法**: `crawl_all_gz_pages()` - 专门的规章页面爬取方法

### 2. MemGovCrawler（法律法规爬虫）
- **特点**: 处理链接到外部网站的文档
- **URL模式**: 单页面，包含指向flk.npc.gov.cn的链接
- **下载方式**: 点击下载按钮，处理弹窗
- **特殊处理**: 新窗口管理，PDF格式选择

### 3. NormativeFileCrawler（规范性文件爬虫）
- **特点**: 提取页面文本内容并保存为Word文档
- **URL模式**: 单页面，包含文章链接
- **下载方式**: 文本提取 + docx文档生成
- **特殊功能**: 支持多种内容选择器，自动添加来源信息

### 4. StandardTextCrawler（标准文本爬虫）
- **特点**: 多种下载策略，支持翻页
- **URL模式**: 支持翻页
- **下载方式**: PDF直接下载、按钮点击、快捷键、页面保存
- **特殊处理**: 多种下载方法的fallback机制

### 5. SystemFileCrawler（制度文件爬虫）
- **特点**: 处理PDF附件下载
- **URL模式**: 支持翻页
- **下载方式**: 查找PDF链接，直接下载或点击下载
- **特殊处理**: 多PDF文件处理，文件名包含序号

## 使用方法

### 基本使用
```python
from gz_crawler_refactored import GzCrawler

# 创建爬虫实例
crawler = GzCrawler(download_path="./规章")

# 爬取所有页面
crawler.crawl_all_gz_pages(max_pages=10)
```

### 带日志记录器使用
```python
from gz_crawler_refactored import GzCrawler

# 创建带日志记录器的爬虫
crawler = GzCrawler(download_path="./规章", logger=your_logger)

# 爬取指定数量的页面
crawler.crawl_all_gz_pages(max_pages=5)
```

### 单页面爬取
```python
from mem_gov_crawler_refactored import MemGovCrawler

crawler = MemGovCrawler(download_path="./法律法规")
main_url = "https://www.mem.gov.cn/fw/flfgbz/fg/"

# 爬取前10个链接
crawler.crawl_all(main_url, max_links=10)
```

## 重构优势

### 1. 代码复用
- 消除了大量重复代码
- 通用功能集中在基类中
- 子类只需实现特定的业务逻辑

### 2. 易于维护
- 修改通用功能只需修改基类
- 各爬虫的特定逻辑分离清晰
- 统一的接口和方法命名

### 3. 易于扩展
- 添加新爬虫只需继承基类并实现抽象方法
- 可以轻松添加新的通用功能
- 支持多态和方法重写

### 4. 统一的错误处理和日志
- 所有爬虫使用相同的日志格式
- 统一的异常处理机制
- 一致的统计报告格式

### 5. 测试友好
- 每个爬虫可以独立测试
- 基类功能可以单独测试
- 提供了完整的使用示例

## 运行测试

```bash
# 运行使用示例
python crawler_usage_example.py

# 选择要测试的爬虫类型
# 1. 规章爬虫
# 2. 法律法规爬虫
# 3. 规范性文件爬虫
# 4. 标准文本爬虫
# 5. 制度文件爬虫
# all. 所有爬虫
```

## 注意事项

1. **依赖项**: 确保安装了所有必需的Python包（selenium, requests, python-docx等）
2. **ChromeDriver**: 确保ChromeDriver已正确安装并在PATH中
3. **网络连接**: 爬虫需要稳定的网络连接
4. **目标网站**: 某些网站可能有反爬虫机制，需要适当调整延时和请求频率
5. **文件权限**: 确保下载目录有写入权限

## 未来扩展

1. **添加新爬虫**: 继承BaseCrawler并实现抽象方法
2. **增强功能**: 可以在基类中添加更多通用功能
3. **配置管理**: 可以添加配置文件支持
4. **数据库支持**: 可以添加数据库存储功能
5. **并发处理**: 可以添加多线程或异步处理支持 