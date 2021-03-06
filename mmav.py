#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import platform
import shutil
import json
import tempfile
from time import sleep
from timeit import default_timer
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import asyncio
import re

import requests
from bs4 import BeautifulSoup
import aiohttp

__version__ = "v2.3.0"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
      " like Gecko) Chrome/84.0.4147.125 Safari/537.36")

class Maomiav():

    FILE_JSON = "settings.json"
    __list = [
        ("/tupian/list-自拍偷拍", "自拍偷拍"),
        ("/tupian/list-亚洲色图", "亚洲色图"),
        ("/tupian/list-欧美色图", "欧美色图"),
        ("/tupian/list-美腿丝袜", "美腿丝袜"),
        ("/tupian/list-清纯唯美", "清纯唯美"),
        ("/tupian/list-乱伦熟女", "乱伦熟女"),
        ("/tupian/list-卡通动漫", "卡通动漫"),
    ]
    parts = OrderedDict([(str(k), v) for k, v in enumerate(__list, 1)])

    def __init__(self, bs4_parser, sysstr):
        self.bs4_parser = bs4_parser
        self.sysstr = sysstr

        self.saved_settings = read_from_json(self.FILE_JSON)
        self.aio_download = self.saved_settings.get("aio_download", 0)
        self.threads_num = self.saved_settings.get("max_threads_num", 16)
        self.req_timeout = self.saved_settings.get("request_timeout", 15)
        self.default_part = self.saved_settings.get("default_part", "5")
        self.proxies = self.saved_settings.get("http_proxies", "")
        self.proxies_global = self.saved_settings.get("proxies_global", True)
        self.dload_tips = self.saved_settings.get("download_tips_all", True)

        self.sel_part = self.default_part

        self.page_no = 1
        self.last_page_no = 1
        self.infinite_mode = False
        self.__init2()

    def __init2(self):
        # 最大尝试次数
        __MAX_TRY_NUM = 5
        try_num = 1
        while try_num <= __MAX_TRY_NUM:
            os_clear_screen(self.sysstr)
            self.use_proxies = {"http": self.proxies, "https": self.proxies}
            print_in("正在获取最新的链接(第 %s 次尝试)..." % try_num)
            self.url, self.re_url = self.get_url()
            if self.url:
                print_in("已获取最新链接: " + self.url)
                # 蛤?
                sleep(1)
                if not self.proxies_global:
                    self.use_proxies = {"http": "", "https": ""}
                return
            sleep(0.5)
            try_num += 1
        print_an("Emmm... 尽管尝试了很多次, 但还是没能成功获取链接-_-!")
        print_an("请检查你的网络连接情况, 或者稍候再试？"
                 "(对了如果科学上网的话成功率会大大提高哟~)")
        if input_an("输入 \"S\" 进入设置菜单, 输入其他则退出: ").upper() == "S":
            self.set_settings()
            self.__init2()

    def run(self, goto_sel_item_flag=False):
        if not self.url:
            sys.exit()
        if not self.infinite_mode:
            os_clear_screen(self.sysstr)
        urll = self.url + self.parts[self.sel_part][0]
        if self.page_no > 1:
            url_page = "-%s" % self.page_no
        else:
            url_page = ""
        print_in("正在请求页面并解析, 请稍候...")
        bsObj = self.get_bs(urll + url_page + ".html", self.bs4_parser)
        if not bsObj:
            self.open_failed(urll + url_page)
            if self.infinite_mode:
                return
            temp = input_an("输入 \"0\" 重试, 输入 \"S\" 进入设置菜单,"
                            " 输入其他则退出: ")
            if temp == "0":
                self.run()
            elif temp.upper() == "S":
                self.set_settings()
                self.run()
            else:
                sys.exit()
            return
        print_in("正在解析页面...")
        try:
            nb = bsObj.find("div", {"id": "tpl-img-content"}).find_all("li")
            if self.page_no == 1:
                try:
                    lp = bsObj.find("div", {"class": "pagination"}) \
                              .find_all("a")[-1]["href"]
                    self.last_page_no = int(lp[lp.rindex("-")+1:lp.rindex(".")])
                except:
                    pass
        except:
            if self.infinite_mode:
                return
            self.analyze_failed(urll + url_page)
            input_an("请按回车键退出: ")
            sys.exit()
        threads = []
        for thread in nb:
            try:
                threads.append(self.get_threads(thread))
            except:
                continue
        # 蛤?
        sleep(1)
        if self.infinite_mode:
            self.get_page_pics(threads)
            return
        if goto_sel_item_flag:
            self.sel_item_init(threads)
        self.main_(threads)

    def main_(self, threads):
        while True:
            os_clear_screen(self.sysstr)
            self.show_title()
            print_in("当前图区: " + self.parts[self.sel_part][1])
            print_in("当前页码: " + str(self.page_no))
            print_in("选择操作:")
            print_l("1.爬取此页面下的所有项目")
            print_l("2.浏览项目列表并选择其中一项爬取")
            if self.page_no != 1:
                print_l("8.← 上一页")
            if self.page_no != self.last_page_no:
                print_l("9.→ 下一页")
            print_l("N.无限模式")
            print_l("I.跳页")
            print_l("R.刷新页面")
            print_l("X.切换图区")
            print_l("S.程序设置")
            print_l("E.退出")
            temp = input_an("请输入选项并按回车键: ")
            if temp == "1":
                self.get_page_pics(threads)
            if temp == "2":
                self.sel_item_init(threads)
            if temp == "8" and self.page_no != 1:
                self.page_no -= 1
                self.run()
            if temp == "9" and self.page_no != self.last_page_no:
                self.page_no += 1
                self.run()
            if temp.upper() == "N":
                self.infinite_get()
            if temp.upper() == "I":
                print_in("输入其他则返回:")
                try:
                    temp2 = int(input_an("范围: 1 ~ %s : " % self.last_page_no))
                except ValueError:
                    continue
                if temp2 < 1 or temp2 > self.last_page_no:
                    continue
                self.page_no = temp2
                self.run()
            # Special
            if temp.upper() == "Z":
                self.page_flag = False
                sp_item = {}
                sp_item["date"] = "Special"
                sp_item["link"] = \
                    input_an("请输入页面链接(链接不正确可能会失败哟): ")
                sp_item["title"] = "unnamed"
                os_clear_screen(self.sysstr)
                print_()
                self.get_item_pics(sp_item)
            if temp.upper() == "X":
                if self.sel_pic_part():
                    self.run()
            if temp.upper() == "S":
                if self.set_settings():
                    self.run()
            if temp.upper() == "R":
                self.run()
            if temp.upper() == "E":
                os_clear_screen(self.sysstr)
                sys.exit()

    def get_threads(self, thread):
        return {
            "title": self.adj_dir_name(thread.find("a")["title"]),
            "date": thread.find("span").get_text().strip(),
            "link": self.url + thread.find("a")["href"]
        }

    def infinite_get(self):
        os_clear_screen(self.sysstr)
        print_in("无限模式")
        print_in("在无限模式下, 将会从所在图区的第一页开始"
                 "依次下载每个项目的图片,\n")
        print_("    直到下载到所在图区的最后一页为止.\n")
        print_("    遇到错误会提示但不会终止, 适合挂机下载.")
        print_an("注意! 一旦下载开始, 除非下载任务全部完成"
                 "或是强制终止程序, 否则无法暂停/停止!")
        print_an("你确定要继续吗?")
        if input_an("输入 \"0\" 以继续, 输入其他则返回: ") != "0":
            return
        os_clear_screen(self.sysstr)
        self.infinite_mode = True
        self.page_no = 1
        time_start_sp = default_timer()
        self.failed_num = 0
        while self.page_no <= self.last_page_no:
            print_in("开始下载第 %s 页, 共 %s 页"
                     % (self.page_no, self.last_page_no))
            self.run()
            print_in("第 %s 页下载完成!" % self.page_no)
            self.page_no += 1
        self.infinite_mode = False
        self.page_flag = False
        time_cost_sp = default_timer() - time_start_sp
        print_in("下载任务已全部完成! 总计耗时 %i 分 %i 秒"
                 % (time_cost_sp // 60, time_cost_sp % 60))
        input_an("请按回车键返回主界面: ")

    def get_page_pics(self, threads):
        if not self.infinite_mode:
            os_clear_screen(self.sysstr)
            page_time_start = default_timer()
            time_cost_all = 0
            self.failed_num = 0
        num = 1
        self.page_flag = True
        for child in threads:
            print_in("开始下载第 %s 项, 共 %s 项" % (num, len(threads)))
            print_i()
            exit_flag = self.get_item_pics(child)
            if exit_flag == "break":
                print_an("任务已被用户终止!")
                break
            elif exit_flag == "pass":
                print_an("已跳过 %s !" % child["title"])
            elif exit_flag in ("timeout", "analyze_failed"):
                print_an("%s 下载失败!" % child["title"])
            elif not self.infinite_mode:
                time_cost_all += exit_flag
            num += 1
            # 稍作休息
            try:
                sleep(2)
            except KeyboardInterrupt:
                print_an("任务已被用户终止!")
                break
        if self.infinite_mode:
            return
        page_time_cost = default_timer() - page_time_start
        self.page_flag = False
        print_in("下载任务已全部完成! "
                 "下载总计耗时 %i 分 %i 秒, 实际耗时 %i 分 %i 秒, "
                 "总计有 %s 张下载失败"
                 % (time_cost_all // 60, time_cost_all % 60,
                    page_time_cost // 60, page_time_cost % 60, self.failed_num))
        input_an("请按回车键返回主界面: ")

    def get_item_pics(self, item):
        mkdir("下载保存目录", False)
        if item["date"] == "Special":
            dir_2 = os.path.join("下载保存目录", "Special")
        else:
            dir_2 = os.path.join("下载保存目录", self.parts[self.sel_part][1])
        mkdir(dir_2, False)
        dir_3 = os.path.join(dir_2, item["title"])
        if not mkdir(dir_3):
            if self.infinite_mode:
                return "pass"
            if self.page_flag:
                temp2 = input_an("输入 \"0\" 则跳过, 输入 \"e\" 则跳过"
                                 "之后所有的项目, 否则将清空此目录重新下载: ")
                if temp2 == "0":
                    return "pass"
                if temp2.upper() == "E":
                    return "break"
            else:
                temp2 = input_an("输入 \"0\" 取消下载,"
                                 " 否则将清空此目录重新下载: ")
                if temp2 == "0":
                    return ""
            clean_dir(dir_3)
        bsObj = self.get_bs(item["link"], self.bs4_parser)
        if not bsObj:
            self.open_failed(item["link"])
            if self.page_flag:
                return "timeout"
            input_an("下载失败! 请按回车键返回主界面: ")
            return ""
        try:
            pics = [
                p for p in bsObj.find("div", {"class": "content"}).find_all("img")
                if "_tmb." not in p["data-original"]
            ]
            if item["title"] == "unnamed":
                item["title"] = self.adj_dir_name(
                    bsObj.find("div", {"class": "page_title"}).get_text())
                dir_3_o = dir_3
                dir_3 = os.path.join(dir_2, item["title"])
                fmove(dir_3_o, dir_3)
        except:
            self.analyze_failed(item["link"])
            if self.page_flag:
                return "analyze_failed"
            input_an("下载失败! 请按回车键返回主界面: ")
            return ""
        print_i()
        print_i("开始下载 " + item["title"])
        print_i("共 %s 张" % len(pics))
        time_start = default_timer()
        if self.aio_download == 1:
            failed_num_once = dload_file_all_aio(
                self.dload_tips,
                dir_3,
                (self.proxies, self.req_timeout, self.re_url, item["link"]),
                pics
            )
        else:
            failed_num_once = dload_file_all(
                self.threads_num,
                self.dload_tips, dir_3,
                (self.proxies, self.req_timeout, self.re_url, item["link"]),
                pics
            )
        self.failed_num += failed_num_once
        time_cost_all = default_timer() - time_start
        print_i()
        print_i("%s 下载已完成! 总耗时 %.3f 秒, 有 %s 张下载失败"
                % (item["title"], time_cost_all, failed_num_once))
        if self.page_flag:
            return time_cost_all
        input("\n=== 任务已完成!\n\n*** 请按回车键返回主界面: ")

    def sel_item_init(self, threads):
        self.page_flag = False
        while True:
            temp2 = self.sel_item(threads)
            if not temp2:
                break
            os_clear_screen(self.sysstr)
            print_()
            self.failed_num = 0
            self.get_item_pics(threads[int(temp2) - 1])

    def sel_item(self, threads):
        while True:
            os_clear_screen(self.sysstr)
            print_in("当前图区: " + self.parts[self.sel_part][1])
            print_in("当前页码: " + str(self.page_no))
            num = 1
            for child in threads:
                print_in("%2s: %s %s"
                         % (num, child["date"], child["title"]))
                num += 1
            print_an("请输入你想要下载的项目标号")
            temp = input_an("输入 \"+\" 或 \"-\" 可直接翻页,"
                            " 输入 \"0\" 则返回: ")
            if temp == "0":
                return ""
            if temp == "-" and self.page_no != 1:
                self.page_no -= 1
                self.run(goto_sel_item_flag=True)
            if temp == "+" and self.page_no != self.last_page_no:
                self.page_no += 1
                self.run(goto_sel_item_flag=True)
            if temp in [str(a) for a in range(1, len(threads) + 1)]:
                return temp

    def set_settings(self):
        reset_flag_1 = False
        while True:
            os_clear_screen(self.sysstr)
            print_in("程序设置:")
            print_l("1.设置下载方式 (当前: ", end="")
            if self.aio_download:
                print_("异步 IO 实现)")
            else:
                print_("多线程实现, %s 线程)" % self.threads_num)
            print_l("2.设置请求超时 (当前: %s 秒)" % self.req_timeout)
            print_l("3.设置默认图区 (当前: %s)"
                    % self.parts[self.default_part][1])
            print_l("4.代理配置")
            print_l("5.下载提醒 (当前: ", end="")
            if self.dload_tips:
                print_("显示所有下载结果)")
            else:
                print_("仅显示下载失败的文件)")
            print_l("0.返回")
            temp = input_an("请输入选项并按回车键: ")
            if temp == "1":
                self.set_download_method()
            if temp == "2":
                self.set_req_timeout()
            if temp == "3":
                self.set_default_part()
            if temp == "4":
                reset_flag_1 = self.set_proxies()
            if temp == "5":
                self.set_dload_tips()
            if temp == "0":
                # 保存设置
                save_to_json(self.saved_settings, self.FILE_JSON)
                return reset_flag_1

    def set_download_method(self):
        while True:
            os_clear_screen(self.sysstr)
            print_in("多线程下载更稳定, 异步 IO 下载速度更快, 但尚处于测试阶段:")
            print_l("1: 多线程实现")
            print_l("2: 异步 IO 实现")
            temp = input_an("请输入选项并按回车键: ")
            if temp in ("1", "2"):
                self.aio_download = int(temp) - 1
                self.saved_settings["aio_download"] = self.aio_download
                if self.aio_download == 0:
                    self.set_threads_num()
                return

    def set_threads_num(self):
        self.threads_num = \
            self.set_index({"1": 4, "2": 8, "3": 16, "4": 32},
                           "线程",
                           "更低的线程数将降低下载失败的概率, "
                           "更高的线程数将提升下载速度, 推荐 16 线程",
                           "设置最大下载线程数")
        self.saved_settings["max_threads_num"] = self.threads_num

    def set_req_timeout(self):
        self.req_timeout = \
            self.set_index({"1": 5, "2": 10, "3": 15, "4": 30},
                           "秒",
                           "对于网络环境较差的用户, "
                           "提高超时时间可以降低下载失败的概率...或许",
                           "设置请求超时")
        self.saved_settings["request_timeout"] = self.req_timeout

    def set_default_part(self):
        while True:
            os_clear_screen(self.sysstr)
            print_in("设置打开程序后默认所在的图区:")
            for k, v in self.parts.items():
                print_l("%s: %s" % (k, v[1]))
            temp = input_an("请输入选项并按回车键: ")
            if temp in self.parts.keys():
                self.default_part = temp
                self.saved_settings["default_part"] = self.default_part
                return

    def set_dload_tips(self):
        self.dload_tips = not self.dload_tips
        self.saved_settings["download_tips_all"] = self.dload_tips

    def set_index(self, dic, unit, info, info_2=""):
        while True:
            os_clear_screen(self.sysstr)
            print_in("Tip: " + info)
            if info_2:
                print_in(info_2 + ":")
            for k in sorted(dic.keys()):
                print_l("%s: %-2s %s" % (k, dic[k], unit))
            temp = input_an("请输入选项并按回车键: ")
            if temp in dic.keys():
                return dic[temp]

    def set_proxies(self):
        reset_flag_2 = False
        while True:
            os_clear_screen(self.sysstr)
            print_in("当前使用的代理: ", end="")
            if self.proxies:
                print_(self.proxies)
            else:
                print_("未使用")
            print_in("代理模式: ", end="")
            if self.proxies_global:
                print_("全局")
            else:
                print_("仅用于获取链接")
            print_in("选择操作:")
            print_l("1.设置 HTTP 代理服务器")
            print_l("2.不使用代理")
            print_l("3.设置代理模式")
            print_l("0.返回")
            temp = input_an("请输入选项并按回车键: ")
            if temp == "1":
                proxies_address = input_an("请输入 HTTP 代理地址"
                                           "(留空则默认为 127.0.0.1): ")
                if not proxies_address.strip():
                    proxies_address = "127.0.0.1"
                while True:
                    try:
                        proxies_port = int(input_an("输入代理端口"
                                                    "(范围: 0 ~ 65535): "))
                    except ValueError:
                        print_an("输入有误! 请重新输入")
                    else:
                        if 0 <= proxies_port <= 65535:
                            break
                        print_an("输入有误! 请重新输入")
                self.proxies = "%s:%s" % (proxies_address, proxies_port)
                self.saved_settings["http_proxies"] = self.proxies
                print_in("代理已配置为 " + self.proxies)
                reset_flag_2 = True
                sleep(2)
            if temp == "2":
                self.proxies = ""
                self.saved_settings["http_proxies"] = ""
                print_in("已禁用代理")
                reset_flag_2 = True
                sleep(2)
            if temp == "3":
                print_in("你决定何时使用代理？")
                proxies_when = input_an("如果希望只在获取链接时使用, 请输入0, "
                                        "否则将全局使用代理(默认): ")
                self.proxies_global = (proxies_when != "0")
                self.saved_settings["proxies_global"] = self.proxies_global
            if temp == "0":
                if self.proxies_global:
                    self.use_proxies = {"http": self.proxies,
                                        "https": self.proxies}
                else:
                    self.use_proxies = {"http": "", "https": ""}
                return reset_flag_2

    def sel_pic_part(self):
        # 切换图区
        while True:
            os_clear_screen(self.sysstr)
            print_in("当前图区:" + self.parts[self.sel_part][1])
            print_in("所有图区:")
            for k, v in self.parts.items():
                print_l("%s: %s" % (k, v[1]))
            temp3 = input_an("请输入你要进入的图区编号(输入 \"0\" 则返回): ")
            if temp3 in self.parts.keys():
                self.sel_part = temp3
                self.page_no = 1
                self.last_page_no = 1
                return True
            if temp3 == "0":
                return

    def get_url(self):
        try:
            config_js = requests.get("https://www.maomiav.com/assets/js/custom/config.js",
                                     timeout=self.req_timeout,
                                     proxies=self.use_proxies)
            source_url = re.search('window.line_1 = "(.*?)";', config_js.text).group(1)
            r = requests.get(source_url, timeout=self.req_timeout, proxies=self.use_proxies)
            r.encoding = "utf-8"
            real_url = re.search('LDtemp\s*=\s*\[\s*"(.*?)".*\]', r.text).group(1)
            real_url = "https://www." + real_url
            real_url2 = re.search('url2\s*=\s*\[\s*"(.*?)".*\]', r.text).group(1)
            real_url2 = "https://www." + real_url2
            return real_url, real_url2
        except:
            return "", ""

    def get_bs(self, urll, bs4_parser):
        # 使用浏览器 UA 来请求页面
        headers = {"User-Agent": UA}
        try:
            req = requests.get(url=urll, headers=headers,
                               timeout=self.req_timeout,
                               proxies=self.use_proxies)
            req.encoding = "utf-8"
            return BeautifulSoup(req.text, bs4_parser)
        except:
            return

    @staticmethod
    def adj_dir_name(dir_name):
        for char in ("?", "/", "\\", ":", "*", "\"", "<", ">", "|", "."):
            dir_name = dir_name.replace(char, "")
        dir_name = dir_name.replace(" ", "_")
        return dir_name

    @staticmethod
    def open_failed(real_name=None):
        if real_name:
            print_n(real_name + os.linesep)
        print_a("请求失败或连接超时!")

    @staticmethod
    def analyze_failed(real_name=None):
        if real_name:
            print_n(real_name + os.linesep)
        print_a("页面解析失败!")

    @staticmethod
    def show_title():
        print_()
        print_("=" * 36)
        print_("===" + " " * 30 + "===")
        print_("===  猫咪 AV 图片爬取脚本 %6s ===" % __version__)
        print_("===" + " " * 30 + "===")
        print_("===" + " " * 21 + "By Pzqqt ===")
        print_("===" + " " * 30 + "===")
        print_("=" * 36)

def dload_file_all(max_threads_num, dload_tips, save_path, pars, pics):

    def _dload_file(url):
        nonlocal failed_num
        file_name = url.split("/")[-1]
        try:
            r = requests.get(
                url,
                timeout=req_timeout,
                proxies={"http": proxies, "https": proxies},
                headers=headers
            )
        except:
            try:
                r = requests.get(
                url,
                timeout=15,
                proxies={"http": proxies, "https": proxies},
                headers=headers
            )
            except:
                print_a("%s 下载失败! 状态: %s" % (file_name, "请求超时"))
                return False
        if not r.ok:
            print_a("%s 下载失败! 状态: %s" % (file_name, r.status_code))
            failed_num += 1
            return False
        dload_file = tempfile.mktemp(".pic.tmp")
        with open(dload_file, 'wb') as f:
            f.write(r.content)
        if url.endswith(".txt"):
            # 解密文件是CPU密集型操作 但是因为解密一张图片很快(不到1秒) 所以直接在线程里操作就行了
            rc = os.system("des_decrypt {0} {0}.jpg".format(dload_file))
            if rc != 0:
                print_a("%s 解密失败!" % file_name)
                failed_num += 1
                return False
            remove_path(dload_file)
            dload_file += ".jpg"
            file_name = file_name[:file_name.rindex(".")] + ".jpg"
        elif r.content[1:4] == b'PNG':
            file_name = file_name[:file_name.rindex(".")] + ".png"
        fmove(dload_file, os.path.join(os.path.abspath('.'), save_path, file_name))
        if dload_tips:
            print_i("%s 下载成功! " % file_name)
        return True

    proxies, req_timeout, origin_url, referer_url = pars
    headers = {
        "User-Agent": UA,
        "Origin": origin_url,
        "Referer": referer_url
    }
    # 统计下载失败的文件数量
    failed_num = 0
    # 神奇的多线程下载
    with ThreadPoolExecutor(max_threads_num) as executor1:
        executor1.map(_dload_file, [c["data-original"] for c in pics])
    return failed_num

def dload_file_all_aio(dload_tips, save_path, pars, pics):
    # 下载的异步IO实现

    async def request_get(url):
        async with aiohttp.ClientSession() as session:
            try:
                response = await session.get(url, timeout=req_timeout, proxy=proxies, headers=headers)
                content = await response.read()
                return response.status, content
            except asyncio.TimeoutError:
                return "请求超时", None

    async def dload_file_aio(url):
        # 下载文件
        file_name = url.split("/")[-1]
        req_status, req_content = await request_get(url)
        if req_status != 200:
            print_a("%s 请求失败! 状态: %s" % (file_name, req_status))
            nonlocal failed_num
            failed_num += 1
            return
        dload_file = tempfile.mktemp(".pic.tmp")
        with open(dload_file, "wb") as f:
            f.write(req_content)
        if req_content[1:4] == b"PNG":
            file_name = file_name[:file_name.rindex(".")] + ".png"
        fmove(dload_file, os.path.join(os.getcwd(), save_path, file_name))
        if dload_tips:
            print_i("%s 下载成功! " % file_name)

    urls = [c["data-original"] for c in pics]
    proxies, req_timeout, origin_url, referer_url = pars
    headers = {
        "User-Agent": UA,
        "Origin": origin_url,
        "Referer": referer_url
    }
    proxies = "http://" + proxies
    # 统计下载失败的文件数量
    failed_num = 0

    loop = asyncio.get_event_loop()
    tasks = [dload_file_aio(url) for url in urls]
    loop.run_until_complete(asyncio.wait(tasks))

    # 解密操作放到协程里会阻塞 还是需要丢到线程池里进行操作比较好
    def des_decrypt(file_):
        rc = os.system("des_decrypt {0} {0}.jpg".format(file_))
        if rc != 0:
            print_a("%s 解密失败!" % file_)
        else:
            remove_path(file_)

    encryptd_files = [file for file in os.listdir(os.path.join(os.getcwd(), save_path)) if file.endswith(".txt")]
    if encryptd_files:
        print_i("发现被加密的文件! 正在解密...")
        with ThreadPoolExecutor(8) as executor2:
            executor2.map(des_decrypt, [os.path.join(os.getcwd(), save_path, file) for file in encryptd_files])
    return failed_num

def clean_dir(path):
    # 清空文件夹
    ls = os.listdir(path)
    for i in ls:
        c_path = os.path.join(path, i)
        if os.path.isdir(c_path):
            clean_dir(c_path)
        else:
            os.remove(c_path)

def mkdir(path, print_flag=True):
    # 创建目录
    if os.path.exists(os.path.join(os.path.abspath('.'), path)):
        if print_flag:
            print_a(path + " 目录已存在!")
        return False
    os.makedirs(path)
    print_i(path + " 创建成功")
    return True

def fmove(srcfile, dstfile):
    # 移动/重命名文件或目录
    if not (os.path.isfile(srcfile) or os.path.isdir(srcfile)):
        print_a(srcfile + " 文件或目录不存在!")
    else:
        shutil.move(srcfile, dstfile)

def remove_path(path):
    # 移除文件/目录(如果存在的话)
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)

def select_bs4_parser():
    # 选择 BS4 解析器(优先使用lxml)
    try:
        import lxml
        del lxml
        return "lxml"
    except ModuleNotFoundError:
        try:
            import html5lib
            del html5lib
            return "html5lib"
        except ModuleNotFoundError:
            return ""

def os_clear_screen(ostype):
    # 清屏
    os.system("cls") if ostype == "Windows" else os.system("clear")

def save_to_json(save_data, filename):
    # 保存字典到 json 文件
    try:
        with open(filename, "w") as savefile:
            json.dump(save_data, savefile,
                      sort_keys=True, indent=4, ensure_ascii=False)
    # Debug
    except:
        print_(save_data)
        raise Exception("Write json failed!")

def read_from_json(filename):
    # 从 json 文件中读取字典
    try:
        with open(filename, "r", encoding="utf-8", errors="ignore") as savefile:
            return json.load(savefile)
    except:
        try:
            os.remove(filename)
        finally:
            return {}

def print_n(argv="", end=os.linesep):
    sys.stderr.write("%s%s%s" % (os.linesep, argv, end))

def print_i(argv="", end=os.linesep):
    sys.stderr.write("=== %s%s" % (argv, end))

def print_in(argv="", end=os.linesep):
    sys.stderr.write("%s=== %s%s" % (os.linesep, argv, end))

def print_a(argv="", end=os.linesep):
    sys.stderr.write("*** %s%s" % (argv, end))

def print_an(argv="", end=os.linesep):
    sys.stderr.write("%s*** %s%s" % (os.linesep, argv, end))

def print_l(argv="", end=os.linesep):
    sys.stderr.write("  |%s  === %s%s" % (os.linesep, argv, end))

def print_(argv="", end=os.linesep):
    sys.stderr.write("%s%s" % (argv, end))

def input_a(argv):
    return input("*** " + argv)

def input_an(argv):
    return input("\n*** " + argv)

def main():

    ''' 检查 OS '''
    sysstr = platform.system()
    if sysstr not in ("Windows", "Linux"):
        print_("\n运行失败!\n\n不支持你的操作系统!")
        sys.exit()

    ''' 检测 BS4 解析器 '''
    bs4_parser = select_bs4_parser()
    if not bs4_parser:
        print_("\n运行失败!\n\n请安装至少一个解析器!")
        print_("可选: \"lxml\" 或 \"html5lib\"!")
        sys.exit()

    ''' Windows 命令行窗口设置 '''
    if sysstr == "Windows":
        os.system("title 猫咪 AV 图片爬取脚本 " + __version__ + " By Pzqqt")
        term_lines = 87
        term_cols = 120
        hex_lines = hex(term_lines).replace("0x", "").zfill(4)
        hex_cols = hex(term_cols).replace("0x", "").zfill(4)
        set_terminal_size = (r'reg add "HKEY_CURRENT_USER\Console" '
                             '/t REG_DWORD /v WindowSize /d 0x')
        set_terminal_buffer = (r'reg add "HKEY_CURRENT_USER\Console" '
                               '/t REG_DWORD /v ScreenBufferSize /d 0x')
        os.system("%s%s%s /f >nul" % (set_terminal_size, hex_lines, hex_cols))
        os.system("%s%s%s /f >nul" % (set_terminal_buffer, "07d0", hex_cols))

    ''' 主界面 '''
    Maomiav(bs4_parser, sysstr).run()
    os_clear_screen(sysstr)
    sys.exit()

if __name__ == '__main__':
    main()
