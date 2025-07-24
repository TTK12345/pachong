#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫使用示例
展示如何使用重构后的爬虫类
"""

from gz_crawler_refactored import GzCrawler
from mem_gov_crawler_refactored import MemGovCrawler
from normative_file_crawler_refactored import NormativeFileCrawler
from standard_text_crawler_refactored import StandardTextCrawler
from system_file_crawler_refactored import SystemFileCrawler

def test_gz_crawler():
    """测试规章爬虫"""
    print("\n" + "="*60)
    print("测试规章爬虫")
    print("="*60)
    
    crawler = GzCrawler(download_path="./test_output/规章")
    
    # 爬取前3页
    base_url = "https://www.mem.gov.cn/gk/zfxxgkpt/fdzdgknr/gz11/"
    crawler.crawl_all_pages(base_url, max_pages=3)
    
    print("规章爬虫测试完成")

def test_mem_gov_crawler():
    """测试法律法规爬虫"""
    print("\n" + "="*60)
    print("测试法律法规爬虫")
    print("="*60)
    
    crawler = MemGovCrawler(download_path="./test_output/法律法规")
    base_url = "https://www.mem.gov.cn/fw/flfgbz/fg/"
    
    # 单页面爬虫，max_pages=1
    crawler.crawl_all_pages(base_url, max_pages=1)
    
    print("法律法规爬虫测试完成")

def test_normative_file_crawler():
    """测试规范性文件爬虫"""
    print("\n" + "="*60)
    print("测试规范性文件爬虫")
    print("="*60)
    
    crawler = NormativeFileCrawler(download_path="./test_output/规范性文件")
    
    # 使用实际的URL
    base_url = "https://www.mem.gov.cn/fw/flfgbz/gfxwj/"
    
    # 单页面爬虫，max_pages=1
    crawler.crawl_all_pages(base_url, max_pages=1)
    
    print("规范性文件爬虫测试完成")

def test_standard_text_crawler():
    """测试标准文本爬虫"""
    print("\n" + "="*60)
    print("测试标准文本爬虫")
    print("="*60)
    
    crawler = StandardTextCrawler(download_path="./test_output/标准文本")
    
    # 使用实际的URL
    base_url = "https://www.mem.gov.cn/fw/flfgbz/bz/bzwb/"
    
    # 爬取前2页
    crawler.crawl_all_pages(base_url, max_pages=2)
    
    print("标准文本爬虫测试完成")

def test_system_file_crawler():
    """测试制度文件爬虫"""
    print("\n" + "="*60)
    print("测试制度文件爬虫")
    print("="*60)
    
    crawler = SystemFileCrawler(download_path="./test_output/制度文件")
    base_url = "https://www.mem.gov.cn/fw/flfgbz/bz/bzgg/"
    
    # 爬取前2页
    crawler.crawl_all_pages(base_url, max_pages=2)
    
    print("制度文件爬虫测试完成")

def main():
    """主函数 - 运行所有测试"""
    print("开始测试重构后的爬虫类...")
    
    # 选择要测试的爬虫
    test_options = {
        '1': ('规章爬虫', test_gz_crawler),
        '2': ('法律法规爬虫', test_mem_gov_crawler),
        '3': ('规范性文件爬虫', test_normative_file_crawler),
        '4': ('标准文本爬虫', test_standard_text_crawler),
        '5': ('制度文件爬虫', test_system_file_crawler),
        'all': ('所有爬虫', None)
    }
    
    print("\n请选择要测试的爬虫：")
    for key, (name, _) in test_options.items():
        print(f"{key}. {name}")
    
    choice = input("\n请输入选择 (1-5 或 all): ").strip()
    
    if choice == 'all':
        # 运行所有测试
        for key, (name, test_func) in test_options.items():
            if key != 'all' and test_func:
                try:
                    test_func()
                except Exception as e:
                    print(f"{name}测试失败: {e}")
    elif choice in test_options and choice != 'all':
        name, test_func = test_options[choice]
        try:
            test_func()
        except Exception as e:
            print(f"{name}测试失败: {e}")
    else:
        print("无效的选择")
    
    print("\n所有测试完成！")

if __name__ == "__main__":
    main() 