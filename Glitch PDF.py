import sys
import fitz
import webbrowser
import re
import json
import pdf_reader
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QShortcut, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem
)
from PyQt5.QtCore import Qt, QRectF, QTimer
from PyQt5.QtGui import QKeySequence, QImage, QPixmap, QPen, QBrush, QColor, QCloseEvent


class glitch_pdf(QMainWindow):
    def __init__(self, pdf_path=None):
        super().__init__()
        self.pdf_document = None
        self.pdf_name = ''
        self.ui = pdf_reader.Ui_MainWindow()
        self.ui.setupUi(self)

        # 初始化参数 ----------------------------------------------------------------------
        # 数据保存目录和文件名
        self.folder_path = os.path.join(os.path.expanduser("~"), "Documents", "Glitch PDF save data")
        self.save_file_name = ''
        self.save_file_path = ''

        # 缩放因子
        self.scale_factor = 1.0

        # 总页数
        self.total_page = 0

        # 设置焦点到主窗口
        self.setFocus()

        # 页面纠错码
        self.ecn = 0

        # 目录页码
        self.toc_page = 0

        # 使用输入框时的页码
        self.recorded_page = 0

        # focus_page_jump() 函数中的自增循环变量
        self.focus_pages_jump_count = 0

        # 存储书签的二维列表，元素形式为 ['bookmark title', page]
        self.bm_list = []

        # 用户在 real page 模式下查看到的书签列表
        self.r_view_bm_list = []

        # 用户的书签关键字搜索结果
        self.bm_search_result = []

        # 当前页面的 url 信息列表
        self.current_links = []

        # 当前显示的 url 信息
        self.display_url = ''

        # 索引组 ---------------------------------------------
        self.current_page_index = 0  # 当前页面索引
        self.focus_pages_index = []  # 存储循环跳转页面的列表
        self.bm_index = 0  # next_bm() 和 prev_bm() 函数的循环变量
        self.bm_result_index = 0  # next_bm() 和 prev_bm() 函数的循环变量
        self.current_link_index = -1  # url 列表索引
        # ----------------------------------------------------

        # 信号组 ---------------------------------------------
        self.is_shift_pressed = False # shift按下信号
        self.is_ctrl_pressed = False  # ctrl按下信号
        self.is_x_pressed = False  # x按下信号
        self.is_real_page = False  # 显示真实页码信号
        self.is_toc_set = False  # 已设置目录书签信号
        self.is_bm_mod = False  # 查看书签信号
        self.is_pdf_opened = False  # 启动程序后是否打开了pdf信号
        self.is_save_mod = True  # 关闭窗口自动保存数据
        self.is_data_loaded = False  # 已加载保存数据信号
        self.is_top_top_view = False  # 每次翻页从顶部开始阅读信号
        self.is_bottom_top_view = False # 每次往回翻页从底部开始阅读，往后翻页从顶部阅读信号
        self.is_bm_search_mode = False  # 关键字搜索书签信号
        self.is_url_mode = False  # 显示页面超链接信号
        # --------------------------------------------------

        # 计时器组 ------------------------------------
        self.load_info_timer = QTimer(self)
        self.load_info_timer.setSingleShot(True)
        self.load_info_timer.timeout.connect(self.restore_placeholder_from_load_info)

        self.check_clipboard_timer = QTimer(self)
        self.check_clipboard_timer.setSingleShot(True)
        self.check_clipboard_timer.timeout.connect(self.restore_placeholder_from_clipboard)
        # ----------------------------------------

        # 快捷键组 -------------------------------------------------------------
        # Ctrl + O 打开文件
        open_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        open_shortcut.activated.connect(self.open_pdf_dialog)

        # Ctrl + Z 跳转操作输入框时的页面
        back_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        back_shortcut.activated.connect(self.back_to_recorded_page)

        # Shift + Down 查看下一个书签
        next_bm_shortcut = QShortcut(QKeySequence("Shift+Down"), self)
        next_bm_shortcut.activated.connect(self.next_bm)

        # Shift + Up 查看上一个书签
        prev_bm_shortcut = QShortcut(QKeySequence("Shift+Up"), self)
        prev_bm_shortcut.activated.connect(self.prev_bm)

        # Ctrl + Up 或 Ctrl + W 放大当前页面
        zoom_in_shortcut_1 = QShortcut(QKeySequence("Ctrl+Up"), self)
        zoom_in_shortcut_1.activated.connect(self.zoom_in)

        zoom_in_shortcut_2 = QShortcut(QKeySequence("Ctrl+W"), self)
        zoom_in_shortcut_2.activated.connect(self.zoom_in)

        # Ctrl + Down 或 Ctrl + S 缩小当前页面
        zoom_out_shortcut_1 = QShortcut(QKeySequence("Ctrl+Down"), self)
        zoom_out_shortcut_1.activated.connect(self.zoom_out)

        zoom_out_shortcut_2 = QShortcut(QKeySequence("Ctrl+S"), self)
        zoom_out_shortcut_2.activated.connect(self.zoom_out)

        # Ctrl + C 从输入框复制
        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        copy_shortcut.activated.connect(self.copy_from_input)
        # ---------------------------------------------------------------------------

        self.ui.open_button.clicked.connect(self.open_pdf_dialog)

        self.scene = QGraphicsScene(self)  # 创建图形场景
        self.ui.graphicsView.setScene(self.scene)  # 设置图形视图的场景

        # ---------------------------------------------------------------------------------------------------------
        if pdf_path:
            self.open_pdf(pdf_path)

    def zoom_in(self):
        self.scale_factor *= 1.2
        self.show_page()

    def zoom_out(self):
        if self.scale_factor >= 1.2:
            self.scale_factor /= 1.2
        self.show_page()

    def reset_parameters(self):  # 从已有文件开启新文件时需要重置的参数
        self.pdf_document = None

        self.is_real_page = False
        self.is_toc_set = False
        self.is_bm_mod = False
        self.is_bm_search_mode = False
        self.is_url_mode = False
        self.is_pdf_opened = False
        self.is_save_mod = True
        self.is_data_loaded = False
        self.is_top_top_view = False
        self.is_bottom_top_view = False

        self.bm_list = []
        self.bm_search_result = []
        self.focus_pages_index = []
        self.r_view_bm_list = []

        self.display_url = ''

        self.recorded_page = 0
        self.bm_index = 0
        self.bm_result_index = 0
        self.focus_pages_jump_count = 0
        self.toc_page = 0
        self.ecn = 0
        self.scale_factor = 1.0

        self.ui.open_button.setText('open')
        self.setFocus()

    def open_pdf_dialog(self):
        # 打开文件选择对话框
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "选择 PDF 文件", "",
                                                             "PDF Files (*.pdf);;All Files (*)", options=options)
        if file_name:
            self.open_pdf(file_name)

    def open_pdf(self, file_name):  # 注意其中的 file_name 参数是一个路径，其中包括了打开的pdf文件名
        if self.pdf_document:  # 如果已经打开了pdf文件，则关闭并保存后再开启新的pdf
            if self.is_save_mod:
                self.save_to_json()
            self.pdf_document.close()
            self.reset_parameters()
            self.clear_highlights()

        self.pdf_document = fitz.open(file_name)
        self.total_page = self.pdf_document.page_count
        self.current_page_index = 0  # 重置当前页面索引

        self.is_pdf_opened = True

        pdf_name = os.path.basename(file_name)  # 提取 pdf 文件名
        self.pdf_name = pdf_name

        self.setWindowTitle(pdf_name)

        self.save_file_name = pdf_name.replace('.pdf', '.json')
        self.save_file_path = os.path.join(self.folder_path, self.save_file_name)

        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)  # 注意这个语句是将 folder_path 中的内容全部当做文件夹处理了

        if not os.path.exists(self.save_file_path):
            with open(self.save_file_path, 'w', encoding='utf-8'):  # 创建空的.json文件
                pass
        else:
            if os.path.getsize(self.save_file_path) > 0:
                self.load_from_json()
                self.is_data_loaded = True

        self.show_page()  # 显示第一页

    def show_page(self):
        if hasattr(self, 'pdf_document') and self.pdf_document:
            # 获取当前页面
            self.current_page = self.pdf_document[self.current_page_index]

            # 根据当前缩放因子获取页面的 Pixmap
            mat = fitz.Matrix(self.scale_factor, self.scale_factor)  # 创建缩放矩阵
            pix = self.current_page.get_pixmap(matrix=mat)  # 将页面转换为图像

            # 创建 QImage
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)

            pixmap = QPixmap.fromImage(img)

            # 清楚场景
            self.scene.clear()

            # 添加 PDF图像到场景
            pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(pixmap_item)

            # 设置场景大小
            self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())

            # 目录指示灯
            if self.is_toc_set:
                self.ui.toc_flag_label.setStyleSheet("background-color: rgb(95, 180, 102)")
            else:
                self.ui.toc_flag_label.setStyleSheet("background-color: rgb(226, 73, 46)")

            # 提前当前页面的所有超链接
            self.extract_links(self.current_page)

            # 页码信息作为占位符显示
            self.page_placeholder()
        else:
            print("没有打开的 PDF 文档")

    # 输入框占位符 -----------------------------------------------------------------
    def page_placeholder(self):
        if self.is_data_loaded:  # 首先判断是否有数据加载
            str_load_info = "Saved data has been loaded."
            self.ui.everything_edit.setPlaceholderText(str_load_info)
            self.ui.everything_edit.setStyleSheet("color:green;")
            self.load_info_timer.start(2000)
        else:
            if self.is_bm_mod:  # 查看书签模式
                self.clear_highlights()
                if not self.is_bm_search_mode:  # 查看全部书签
                    self.ui.everything_edit.setStyleSheet("color:black;")
                    str4 = self.bm_mode_placeholder(self.bm_list, self.bm_index)
                    if len(str4) > 0:  # 结果列表非空
                        self.ui.everything_edit.setPlaceholderText(str4)
                    else:  # 没有书签则退出书签查看模式
                        self.is_bm_mod = False
                        self.page_placeholder()
                else:  # 查看书签搜索结果
                    str4 = self.bm_mode_placeholder(self.bm_search_result, self.bm_result_index)
                    if len(str4) > 0:  # 结果列表非空
                        self.ui.everything_edit.setStyleSheet("color:rgb(170, 85, 0);")
                        self.ui.everything_edit.setPlaceholderText(str4)
                    else:  # 没有结果则关闭搜索模式
                        self.is_bm_search_mode = False
                        self.page_placeholder()
            elif self.is_url_mode:  # 显示当前页面的超链接
                if self.current_link_index == -1 and self.current_links:
                    self.current_link_index = 0
                    self.show_link(0)
                elif self.current_links:
                    self.show_link(self.current_link_index)
                else:
                    self.is_url_mode = False
                    self.page_placeholder()
            else:  # 没有其他情况默认显示页码
                self.clear_highlights()
                self.ui.everything_edit.setStyleSheet("color:black;")
                real_page = self.current_page_index + 1 - self.ecn
                str1 = "before text" + "/" + str(self.total_page)
                str2 = str(real_page) + "/" + str(self.total_page)
                str3 = str(self.current_page_index + 1) + "/" + str(self.total_page)
                if self.is_real_page:  # 显示真实页码
                    if real_page <= 0:
                        self.ui.everything_edit.setPlaceholderText(str1)
                    else:
                        self.ui.everything_edit.setPlaceholderText(str2)
                else:  # 显示 pdf 页码
                    self.ui.everything_edit.setPlaceholderText(str3)
    # -----------------------------------------------------------------------------------

    # 恢复placeholder显示
    def restore_placeholder_from_load_info(self):
        self.is_data_loaded = False
        self.ui.everything_edit.setStyleSheet("color:black;")
        self.page_placeholder()

    def restore_placeholder_from_clipboard(self):
        self.ui.everything_edit.setStyleSheet("background-color:#FFFFFF;")

    # 显示书签列表的placeholder操作
    def bm_mode_placeholder(self, show_list, list_index):
        if len(show_list) > 0:
            show_bm = []
            for item in show_list:
                show_bm.append(item[:])
            if self.is_real_page:
                for item in show_bm:
                    item[1] -= self.ecn
            return f"{show_bm[list_index][0]}, {show_bm[list_index][1]}"
        else:
            return ''

    # 以下两组为翻页方法
    def prev_page(self):
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self.show_page()

    def next_page(self):
        if self.current_page_index < self.total_page - 1:
            self.current_page_index += 1
            self.show_page()

    # 接收输入窗口内容的函数----------------------------------------
    def everything_text(self):
        self.recorded_page = self.current_page_index
        unit = self.ui.everything_edit
        text = unit.text()

        # 匹配占位符显示真实页数
        pattern_ecn = r'show real page\s*:?\s*(\d+)*\s*'
        matches_ecn = re.search(pattern_ecn, text)

        # 匹配占位符恢复显示pdf页数
        pattern_not_ecn = r'show pdf page\s*'
        matches_not_ecn = re.search(pattern_not_ecn, text)

        # 匹配页码
        pattern_page_r = r'(^\d+$)\s*'
        matches_page_r = re.search(pattern_page_r, text)

        # 匹配设置目录书签语句
        pattern_set_toc = r'set\s+toc\s*'
        matches_set_toc = re.search(pattern_set_toc, text)

        # 匹配移除目录书签语句
        pattern_remove_toc = r'del\s+toc\s*'
        matches_remove_toc = re.search(pattern_remove_toc, text)

        # 匹配跳转目录语句
        pattern_jump_toc = r'toc\s*'
        matches_jump_toc = re.search(pattern_jump_toc, text)

        # 匹配范围内循环跳转页面语句
        pattern_focus_on = r'focus\s*:?\s*(\d+(?:[ ,]\d+)*)'
        matches_focus_on = re.search(pattern_focus_on, text)

        # 匹配查看书签语句
        pattern_bm_mod = r'^bm\s*$'
        matches_bm_mode = re.search(pattern_bm_mod, text)

        # 匹配添加书签语句
        pattern_add_bm = r'add\s+bm\s*:?\s*(.*)'
        matches_add_bm = re.search(pattern_add_bm, text)

        # 匹配删除书签语句
        pattern_del_bm = r'del\s+bm\s*'
        matches_del_bm = re.search(pattern_del_bm, text)

        # 匹配关键字搜索书签语句
        pattern_search_bm = r'find bm\s*:?\s*(.*)\s*'
        matches_search_bm = re.search(pattern_search_bm, text)

        # 匹配退出查看书签搜索结果语句
        pattern_exit_search_bm = r'show all\s*'
        matches_exit_search_bm = re.search(pattern_exit_search_bm, text)

        # 匹配显示书签搜索结果语句
        pattern_show_search_bm = r'show res\s*'
        matches_show_search_bm = re.search(pattern_show_search_bm, text)
        
        # 匹配翻页从顶部阅读视图语句
        pattern_top_view = r'tt view\s*'
        matches_top_view = re.search(pattern_top_view, text)

        # 匹配往回翻页从底部阅读视图语句
        pattern_bottom_top_view = r'bt view\s*'
        matches_bottom_top_view = re.search(pattern_bottom_top_view, text)

        # 匹配开启保存语句
        pattern_save = r'^save\s*$'
        matches_save = re.search(pattern_save, text)

        # 匹配关闭保存语句
        pattern_no_save = r'no save\s*'
        matches_no_save = re.search(pattern_no_save, text)
        
        # 匹配查看当前页面超链接语句
        pattern_show_url = r'^url\s*$'
        matches_show_url = re.search(pattern_show_url, text)

        if matches_ecn:  # show real page
            if matches_ecn.group(1) is not None:
                number = int(matches_ecn.group(1))
                self.ecn = self.current_page_index + 1 - number

            self.is_real_page = True
            self.show_page()
        elif matches_not_ecn:  # show pdf page
            self.is_real_page = False
            self.show_page()
        elif matches_page_r:  # page jump
            if self.is_real_page:
                number = int(matches_page_r.group(1)) + self.ecn
            else:
                number = int(matches_page_r.group(1))
            self.current_page_index = number - 1
            self.show_page()
        elif matches_set_toc:  # set toc
            self.toc_page = self.current_page_index
            self.is_toc_set = True
            self.show_page()
        elif matches_remove_toc:  # remove toc
            self.is_toc_set = False
            self.toc_page = 0
            self.show_page()
        elif matches_jump_toc:  # jump toc
            if self.is_toc_set:
                self.current_page_index = self.toc_page
                self.show_page()
        elif matches_focus_on:  # focus loop jump
            self.focus_pages_index.clear()
            focus_pages = [int(num) for num in matches_focus_on.group(1).replace(',', ' ').split()]
            if self.is_real_page:
                focus_pages_index = [num + self.ecn - 1 for num in focus_pages]
            else:
                focus_pages_index = [num - 1 for num in focus_pages]
            self.focus_pages_index = focus_pages_index
        elif matches_bm_mode:  # switch bookmark mode
            self.is_bm_mod = not self.is_bm_mod
            if not self.is_bm_mod:
                self.is_bm_search_mode = False
            else:
                self.is_url_mode = False
            self.page_placeholder()
        elif matches_add_bm:  # add bookmark
            bm_title = matches_add_bm.group(1)
            self.add_bm(bm_title)
        elif matches_del_bm:  # delete bookmark
            self.del_bm()
        elif matches_search_bm:  # search bookmarks
            self.is_url_mode = False
            self.is_bm_mod = True
            self.is_bm_search_mode = True
            self.bm_search_result = self.search_bm(matches_search_bm.group(1))
            self.page_placeholder()
        elif matches_show_search_bm:  # show search results of bookmarks
            self.is_url_mode = False
            self.is_bm_mod = True
            self.is_bm_search_mode = True
            self.page_placeholder()
        elif matches_exit_search_bm:  # exit from bm search mode
            if self.is_bm_mod:
                if self.is_bm_search_mode:
                    self.is_bm_search_mode = False
                    self.page_placeholder()
        elif matches_save:  # save mode
            self.is_save_mod = True
            self.ui.open_button.setStyleSheet("color:black;")
        elif matches_no_save:  # no save mode
            self.is_save_mod = False
            self.ui.open_button.setStyleSheet("color:red;")
        elif matches_top_view:  # top-top view
            self.is_top_top_view = not self.is_top_top_view
            self.is_bottom_top_view = False
            if self.is_top_top_view:
                self.ui.open_button.setText('TT')
            else:
                self.ui.open_button.setText('open')
        elif matches_bottom_top_view:  # bottom-top view
            self.is_bottom_top_view = not self.is_bottom_top_view
            self.is_top_top_view = False
            if self.is_bottom_top_view:
                self.ui.open_button.setText('BT')
            else:
                self.ui.open_button.setText('open')
        elif matches_show_url:  # switch display list of url of current page
            self.is_url_mode = not self.is_url_mode
            if self.is_url_mode:
                self.is_bm_mod = False
                self.is_bm_search_mode = False
            self.page_placeholder()

        unit.clear()
        unit.clearFocus()
    # ----------------------------------------------------------------------------

    # 回到记录页面
    def back_to_recorded_page(self):
        self.current_page_index = self.recorded_page
        self.show_page()

    # Focus页面循环跳转
    def focus_pages_jump(self):
        if self.focus_pages_jump_count < len(self.focus_pages_index):
            self.current_page_index = self.focus_pages_index[self.focus_pages_jump_count]
            self.show_page()
            self.focus_pages_jump_count += 1
        else:
            # self.focus_pages_jump_count %= len(self.focus_pages_index)
            self.focus_pages_jump_count = 0
            self.current_page_index = self.focus_pages_index[self.focus_pages_jump_count]
            self.show_page()
            self.focus_pages_jump_count += 1

    # 查看下一个书签
    def next_bm(self):
        if self.is_bm_mod:  # 处于书签查看模式才触发翻页效果
            # 根据所处不同模式给到不同赋值
            if not self.is_bm_search_mode:
                len_list = len(self.bm_list)
                index = self.bm_index
                if len_list > 0:
                    if index < len_list - 1:
                        index += 1
                    else:
                        index = 0
                self.bm_index = index
                self.page_placeholder()
            else:
                len_list = len(self.bm_search_result)
                index = self.bm_result_index
                if len_list > 0:
                    if index < len_list - 1:
                        index += 1
                    else:
                        index = 0
                self.bm_result_index = index
                self.page_placeholder()
        elif self.is_url_mode:
            len_list = len(self.current_links)
            index = self.current_link_index
            if len_list > 0:
                if index < len_list - 1:
                    index += 1
                else:
                    index = 0
            self.current_link_index = index
            self.page_placeholder()

    # 查看上一个书签
    def prev_bm(self):
        if self.is_bm_mod:  # 处于书签查看模式才触发翻页效果
            # 根据所处不同模式给到不同赋值
            if not self.is_bm_search_mode:
                len_list = len(self.bm_list)
                index = self.bm_index
                if len_list > 0:
                    if index > 0:
                        index -= 1
                    else:
                        index = len_list - 1
                self.bm_index = index
                self.page_placeholder()
            else:
                len_list = len(self.bm_search_result)
                index = self.bm_result_index
                if len_list > 0:
                    if index > 0:
                        index -= 1
                    else:
                        index = len_list - 1
                self.bm_result_index = index
                self.page_placeholder()
        elif self.is_url_mode:
            len_list = len(self.current_links)
            index = self.current_link_index
            if len_list > 0:
                if index > 0:
                    index -= 1
                else:
                    index = len_list - 1
            self.current_link_index = index
            self.page_placeholder()

    # 把当前页面添加到书签
    def add_bm(self, bm_title):
        bm_page = self.current_page_index + 1  # 书签列表默认使用pdf页码编号
        if not any(item[0] == bm_title for item in self.bm_list):
            self.bm_list.append([bm_title, bm_page])
            self.blank_blink()
        else:
            self.black_blink()

    # 把当前页面从书签中移除（如果存在的话）
    def del_bm(self):
        self.is_bm_mod = False
        self.is_bm_search_mode = False
        if any(item[1] == self.current_page_index + 1 for item in self.bm_list):
            self.bm_list = [item for item in self.bm_list if item[1] != self.current_page_index + 1]
            self.black_blink()
        self.page_placeholder()

    # 跳转到当前查看书签或打开当前查看的 url
    def bm_jump(self):
        if self.is_bm_mod:
            if not self.is_bm_search_mode:
                len_list = len(self.bm_list)
                page = int(self.bm_list[self.bm_index][1])
            else:
                len_list = len(self.bm_search_result)
                page = int(self.bm_search_result[self.bm_result_index][1])

            if len_list > 0:
                self.current_page_index = page - 1
                self.show_page()
        elif self.is_url_mode:
            self.open_current_link()

    # 根据名称查询书签
    def search_bm(self, query):
        pattern = re.escape(query)
        regex = re.compile(pattern, re.IGNORECASE)

        result = [item for item in self.bm_list if regex.search(item[0])]

        return result

    # 指示灯闪烁白色
    def blank_blink(self):
        for i in range(256):
            # 计算渐变到白色
            QTimer.singleShot(i, lambda i=i: self.ui.toc_flag_label.setStyleSheet(
                f"background-color: rgb({i}, {i}, {i});"))
        # 在渐变完成后，调用恢复原色的方法
        QTimer.singleShot(255, self.blank_to_color)

    # 指示灯闪烁白色后恢复原色
    def blank_to_color(self):
        for i in range(255):
            if self.is_toc_set:  # 添加目录后指示灯颜色为 rgb(95, 180, 102)
                r = 255 - int((255 - 95) * (i / 255))
                g = 255 - int((255 - 180) * (i / 255))
                b = 255 - int((255 - 102) * (i / 255))
            else:  # 未添加目录时指示灯颜色为 rgb(226, 73, 46)
                r = 255 - int((255 - 226) * (i / 255))
                g = 255 - int((255 - 73) * (i / 255))
                b = 255 - int((255 - 46) * (i / 255))
            QTimer.singleShot(i, lambda r=r, g=g, b=b: self.ui.toc_flag_label.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b});"))

    # 指示灯闪烁黑色
    def black_blink(self):
        for i in range(256):
            # 计算渐变到黑色
            QTimer.singleShot(i, lambda i=i: self.ui.toc_flag_label.setStyleSheet(
                f"background-color: rgb({255 - i}, {255 - i}, {255 - i});"))
        # 在渐变完成后，调用恢复原色的方法
        QTimer.singleShot(255, self.black_to_color)

    # 指示灯闪烁黑色后恢复原色
    def black_to_color(self):
        for i in range(255):
            if self.is_toc_set:  # 添加目录后指示灯颜色为 rgb(95, 180, 102)
                r = int(95 * (i / 255))
                g = int(180 * (i / 255))
                b = int(102 * (i / 255))
            else:  # 未添加目录时指示灯颜色为 rgb(226, 73, 46)
                r = int(226 * (i / 255))
                g = int(73 * (i / 255))
                b = int(46 * (i / 255))
            QTimer.singleShot(i, lambda r=r, g=g, b=b: self.ui.toc_flag_label.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b});"))

    # 键盘按键监听
    def keyPressEvent(self, event):
        # 处理修饰键
        if event.key() == Qt.Key_Control:
            self.is_ctrl_pressed = True
            event.accept()
            return
        elif event.key() == Qt.Key_Shift:
            self.is_shift_pressed = True
            event.accept()
            return
        elif event.key() == Qt.Key_X:
            self.is_x_pressed = True
            event.accept()
            return

        # 处理非修饰键
        if event.key() == Qt.Key_Left:
            if self.is_ctrl_pressed:  # Ctrl+Left - 向左滚动
                self.ui.graphicsView.horizontalScrollBar().setValue(
                    self.ui.graphicsView.horizontalScrollBar().value() - 80 * int(self.scale_factor)
                )
            else:  # Left - 往回翻页
                self.handle_left_key()
        elif event.key() == Qt.Key_Right:
            if self.is_ctrl_pressed:  # Ctrl+Right - 向右滚动
                self.ui.graphicsView.horizontalScrollBar().setValue(
                    self.ui.graphicsView.horizontalScrollBar().value() + 80 * int(self.scale_factor)
                )
            else:  # Right - 往后翻页
                self.handle_right_key()
        elif event.key() == Qt.Key_A:
            if self.is_ctrl_pressed:  # Ctrl+A - 向左滚动
                self.ui.graphicsView.horizontalScrollBar().setValue(
                    self.ui.graphicsView.horizontalScrollBar().value() - 80 * int(self.scale_factor)
                )
            else:  # A - 往回翻页
                self.handle_left_key()
        elif event.key() == Qt.Key_D:
            if self.is_ctrl_pressed:  # Ctrl+D - 向右滚动
                self.ui.graphicsView.horizontalScrollBar().setValue(
                    self.ui.graphicsView.horizontalScrollBar().value() + 80 * int(self.scale_factor)
                )
            else:  # D - 往后翻页
                self.handle_right_key()
        elif event.key() == Qt.Key_Up or event.key() == Qt.Key_W:  # 向上滚动
            self.ui.graphicsView.verticalScrollBar().setValue(
                self.ui.graphicsView.verticalScrollBar().value() - 80 * int(self.scale_factor)
            )
        elif event.key() == Qt.Key_Down or event.key() == Qt.Key_S:  # 向下滚动
            self.ui.graphicsView.verticalScrollBar().setValue(
                self.ui.graphicsView.verticalScrollBar().value() + 80 * int(self.scale_factor)
            )
        elif event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return:  # Enter 确认输入
            self.handle_enter_key()
        elif event.key() == Qt.Key_Escape:  # Esc 退出输入模式
            self.handle_escape_key()
        elif event.key() == Qt.Key_Tab and len(self.focus_pages_index) > 0:  # Tab 在 Focus 视图中切换页面
            self.focus_pages_jump()
        elif event.key() == Qt.Key_Space and self.is_x_pressed:  # "x+space" 快捷键
            self.ui.everything_edit.setFocus()
        else:
            super().keyPressEvent(event)

        event.accept()

    def keyReleaseEvent(self, event):
        """处理按键释放事件，重置修饰键状态"""
        if event.key() == Qt.Key_Control:
            self.is_ctrl_pressed = False
        elif event.key() == Qt.Key_Shift:
            self.is_shift_pressed = False
        elif event.key() == Qt.Key_X:
            self.is_x_pressed = False

        super().keyReleaseEvent(event)

    # 辅助函数
    def handle_left_key(self):
        """处理左箭头键逻辑"""
        if self.is_top_top_view:
            self.ui.graphicsView.verticalScrollBar().setValue(0)
        elif self.is_bottom_top_view:
            self.ui.graphicsView.verticalScrollBar().setValue(
                self.ui.graphicsView.verticalScrollBar().maximum()
            )
        self.prev_page()

    def handle_right_key(self):
        """处理右箭头键逻辑"""
        if self.is_top_top_view or self.is_bottom_top_view:
            self.ui.graphicsView.verticalScrollBar().setValue(0)
        self.next_page()

    def handle_enter_key(self):
        """处理回车键逻辑"""
        if self.ui.everything_edit.hasFocus():
            self.everything_text()
        elif self.is_shift_pressed:  # Shift+Enter
            self.bm_jump()

    def handle_escape_key(self):
        """处理Esc键逻辑"""
        if self.ui.everything_edit.hasFocus():
            self.ui.everything_edit.clear()
            self.ui.everything_edit.clearFocus()
        elif self.is_url_mode:
            self.is_url_mode = False
        elif self.is_bm_mod:
            if self.is_bm_search_mode:
                self.is_bm_search_mode = False
            else:
                self.is_bm_mod = False
        self.page_placeholder()

    # 鼠标事件监听
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:  # 左键往回翻页
            if self.is_top_top_view:
                self.ui.graphicsView.verticalScrollBar().setValue(0)
            elif self.is_bottom_top_view:
                self.ui.graphicsView.verticalScrollBar().setValue(
                    self.ui.graphicsView.verticalScrollBar().maximum()
                )
            self.prev_page()
        elif event.button() == Qt.RightButton:  # 右键往后翻页
            if self.is_top_top_view or self.is_bottom_top_view:
                self.ui.graphicsView.verticalScrollBar().setValue(0)
            self.next_page()

        self.setFocus()
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if self.is_ctrl_pressed:  # Ctrl+滚轮 放缩页面大小
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()

    # 重载关闭窗口函数
    def closeEvent(self, a0: QCloseEvent) -> None:
        if self.is_pdf_opened:
            if self.is_save_mod:
                self.save_to_json()
        a0.accept()

    # 打开pdf文件时读取保存数据
    def load_from_json(self):
        with open(self.save_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            self.is_top_top_view = data["is_top_top_view"]
            self.is_bottom_top_view = data["is_bottom_top_view"]
            self.is_real_page = data["is_real_page"]
            self.is_toc_set = data["is_toc_set"]
            self.toc_page = data["toc_page"]
            self.ecn = data["ecn"]
            self.bm_list = data["bookmarks"]

            if self.is_top_top_view:
                self.ui.open_button.setText("TT")
            elif self.is_bottom_top_view:
                self.ui.open_button.setText("BT")

    # 关闭窗口时保存数据
    def save_to_json(self):
        with open(self.save_file_path, 'w'):
            pass

        data_to_save = {
            "is_top_top_view": self.is_top_top_view,
            "is_bottom_top_view": self.is_bottom_top_view,
            "is_real_page": self.is_real_page,
            "is_toc_set": self.is_toc_set,
            "toc_page": self.toc_page,
            "ecn": self.ecn,
            "bookmarks": self.bm_list
        }

        with open(self.save_file_path, 'w', encoding='utf-8') as file:
            json.dump(data_to_save, file, ensure_ascii=False, indent=4)

    # 这部分为提取页面中超链接的方法  -------------------------------------------
    def extract_links(self, page):  # 填充了 current_links 列表
        self.current_links = []  # 因为只提前当前页面的链接，所以每次先清空列表

        # 1. 提取显式超链接（可点击区域）
        for link in page.get_links():
            if link["kind"] == fitz.LINK_URI:
                # 尝试获取链接文本，这里再写一个提前文本的函数
                link_text = self.extract_link_text(page, link["from"])
                self.current_links.append({
                    "type": "explicit",
                    "url": link["uri"],
                    "rect": link["from"],
                    "text": link_text if link_text else link["uri"]
                })

        # 2. 提取文本中的URL（非可点击但可能是超链接）
        text = page.get_text("text")
        text_urls = self.extract_text_urls(text, page)  # 包含4条信息的元素
        self.current_links.extend(text_urls)

        # 3. 按位置排序链接（从上到下）
        self.current_links.sort(key=lambda x: x["rect"].y0)

    def extract_link_text(self, page, rect):
        """提取链接区域内的文本"""
        # 获取链接矩形区域内的所有单词
        words = page.get_text("words", clip=rect)

        # 按位置排序单词（从左到右，从上到下）
        words.sort(key=lambda w: (w[1], w[0]))

        # 合并单词形成文本
        link_text = " ".join(word[4] for word in words)

        # 清理文本（去除多余空格）
        return re.sub(r'\s+', ' ', link_text).strip()

    def extract_text_urls(self, text, page):
        """从页面文本中提取URL并确定其位置"""
        urls = []
        # 匹配URL的正则表达式
        url_pattern = r'https?://[^\s\)\]]+'

        # 查找所有URL
        for match in re.finditer(url_pattern, text):
            url = match.group()
            # 获取URL的位置
            areas = page.search_for(url)
            if areas:
                # 使用第一个匹配区域
                rect = areas[0]
                urls.append({
                    "type": "text",
                    "url": url,
                    "rect": rect,
                    "text": url  # 文本就是URL本身
                })

        return urls

    # 显示指定索引的链接
    def show_link(self, index):
        if 0 <= index < len(self.current_links):
            self.clear_highlights()

            link = self.current_links[index]

            # 显示链接文本
            display_text = link["text"]
            self.display_url = display_text

            if len(display_text) > 50:  # 截断过长的文本
                display_text = display_text[:47] + "..."

            self.ui.everything_edit.setPlaceholderText(
                f"Link {index + 1}/{len(self.current_links)}:{display_text}")
            self.ui.everything_edit.setStyleSheet("color: blue; text-decoration: underline;")

            # 高亮显示链接区域
            self.highlight_link(link["rect"])

    # 清除所有高亮矩形
    def clear_highlights(self):
        for item in self.scene.items():
            if isinstance(item, QGraphicsRectItem):
                self.scene.removeItem(item)

    # 在PDF视图上高亮显示链接区域
    def highlight_link(self, rect):
        # 创建矩形项
        highlight_rect = QRectF(
            rect.x0 * self.scale_factor,
            rect.y0 * self.scale_factor,
            rect.width * self.scale_factor,
            rect.height * self.scale_factor)
        rect_item = QGraphicsRectItem(highlight_rect)

        # 设置边框和填充
        pen = QPen(QColor(255, 0, 0))  # 红色边框
        pen.setWidth(2)
        rect_item.setPen(pen)

        # 半透明填充
        brush = QBrush(QColor(255, 0, 0, 50))  # 半透明红色
        rect_item.setBrush(brush)

        # 添加到场景
        self.scene.addItem(rect_item)

        # 确保高亮在最前面
        rect_item.setZValue(1)

    # 输入框控件以外的控件触发高亮显示超链接
    def direct_show_link(self):
        if self.is_url_mode:
            self.show_link(self.current_link_index)

    # 在浏览器中打开当前显示的链接
    def open_current_link(self):
        if self.current_link_index >= 0 and self.current_links:
            link = self.current_links[self.current_link_index]
            try:
                webbrowser.open(link["url"])
                self.statusBar().showMessage(f"directing: {link['url']}", 2000)
            except Exception as e:
                self.statusBar().showMessage(f"failed: {str(e)}", 2000)

    # 将输入复制到剪切板
    def copy_from_input(self):
        clipboard = QApplication.clipboard()
        if self.is_url_mode:
            clipboard.setText(self.display_url)
        else:
            clipboard.setText(self.ui.everything_edit.placeholderText())

        if clipboard.text() != '':
            self.ui.everything_edit.setStyleSheet("background-color:#ccdece")
            self.check_clipboard_timer.start(300)
    # ----------------------------------------------------------------


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
    viewer = glitch_pdf(pdf_path)
    viewer.show()
    sys.exit(app.exec_())
