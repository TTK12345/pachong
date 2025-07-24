#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import sys
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

def check_chrome_installation():
    """检查Chrome浏览器安装情况"""
    print("检查Chrome浏览器...")
    
    if sys.platform.startswith('linux'):
        # Linux系统检查
        try:
            result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True, check=True)
            path = result.stdout.strip()
            print(f"✓ 找到Chrome浏览器: {path}")
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("✗ 未找到 'google-chrome' 命令。请确保已安装Google Chrome。")
            return False

    elif sys.platform == 'win32':
        # Windows系统检查
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
        ]
        
        for path in chrome_paths:
            if os.path.exists(path):
                print(f"✓ 找到Chrome浏览器: {path}")
                return True
        
        print("✗ 未找到Chrome浏览器")
        return False
        
    else:
        print(f"i 不支持的操作系统: {sys.platform}. 跳过Chrome安装检查。")
        return True

def check_chromedriver():
    """检查ChromeDriver是否在PATH中或当前目录，并且可执行"""
    print("\n检查ChromeDriver...")
    
    try:
        # 优先检查PATH
        result = subprocess.run(['chromedriver', '--version'], capture_output=True, text=True, check=True)
        print(f"✓ ChromeDriver已在PATH中找到并可执行: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        # 如果在PATH中找不到，检查当前目录
        if os.path.exists('./chromedriver'):
            print("i ChromeDriver不在PATH中，但在当前目录中找到。")
            try:
                result = subprocess.run(['./chromedriver', '--version'], capture_output=True, text=True, check=True)
                print(f"✓ ChromeDriver在当前目录中找到并可执行: {result.stdout.strip()}")
                return True
            except PermissionError:
                print("✗ 权限错误! 当前目录的'chromedriver'文件没有执行权限。")
                print("  请在终端中运行: chmod +x ./chromedriver")
                return False
            except Exception as e:
                print(f"✗ 在当前目录中执行chromedriver失败: {e}")
                return False
        
        print("✗ ChromeDriver未在PATH或当前目录中找到。")
        return False
    except PermissionError:
        print("✗ 权限错误! PATH中的'chromedriver'文件没有执行权限。")
        print("  请找到该文件并运行: sudo chmod +x <path_to_chromedriver>")
        return False
    except subprocess.CalledProcessError as e:
        print(f"✗ ChromeDriver在PATH中找到但执行失败: {e.stderr.strip()}")
        return False

def test_selenium():
    """测试Selenium是否能正常启动Chrome(利用Selenium Manager)"""
    print("\n测试Selenium启动Chrome...")
    
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        print("正在启动Chrome (Selenium Manager可能会自动下载驱动)...")
        driver = webdriver.Chrome(options=options)
        print("✓ Chrome启动成功")
        
        print("正在访问测试页面...")
        driver.get("https://www.baidu.com")
        title = driver.title
        print(f"✓ 页面访问成功，标题: {title}")
        
        driver.quit()
        print("✓ Chrome已正常关闭")
        return True
        
    except WebDriverException as e:
        print(f"✗ Selenium测试失败: {e.msg}")
        if "permission denied" in e.msg.lower():
            print("  -> 错误提示包含'permission denied'。请检查chromedriver的执行权限。")
        if "version" in e.msg.lower():
            print("  -> 错误提示包含'version'。请检查ChromeDriver版本与Chrome版本是否匹配。")
        return False
    except Exception as e:
        print(f"✗ Selenium测试失败: {str(e)}")
        return False

def main():
    print("=" * 50)
    print("跨平台Chrome环境检查")
    print("=" * 50)
    
    chrome_ok = check_chrome_installation()
    chromedriver_ok = check_chromedriver()
    
    selenium_ok = False
    if chrome_ok:
        selenium_ok = test_selenium()
    
    print("\n" + "=" * 50)
    print("检查结果:")
    print("=" * 50)
    print(f"Chrome浏览器: {'✓ 正常' if chrome_ok else '✗ 异常'}")
    print(f"ChromeDriver(手动检查): {'✓ 正常' if chromedriver_ok else '✗ 异常'}")
    print(f"Selenium测试(自动管理): {'✓ 正常' if selenium_ok else '✗ 异常'}")
    
    if not chrome_ok or not selenium_ok:
        print("\n" + "-" * 50)
        print("解决方案建议:")
        if not chrome_ok:
            print("- 请先安装Google Chrome浏览器。")
            print("  - Linux: 'sudo apt update && sudo apt install google-chrome-stable'")
            print("  - Windows: https://www.google.com/chrome/")
        
        if not chromedriver_ok and not selenium_ok:
            print("- 无法找到或运行ChromeDriver。")
            print("  1. 确保ChromeDriver文件有执行权限 (Linux: chmod +x chromedriver)。")
            print("  2. 下载匹配您Chrome浏览器版本的ChromeDriver:")
            print("     https://googlechromelabs.github.io/chrome-for-testing/")
            print("  3. 将chromedriver可执行文件放在项目目录, 或 /usr/local/bin/ (Linux)。")
        
        if chrome_ok and not selenium_ok:
            print("- Selenium无法启动Chrome，可能原因:")
            print("  - ChromeDriver与Chrome浏览器版本不匹配。")
            print("  - 权限问题(请再次确认chromedriver有执行权限)。")
            print("  - 防火墙或安全软件阻止。")
    else:
        print("\n✓ 环境看起来很棒！")


if __name__ == '__main__':
    main() 