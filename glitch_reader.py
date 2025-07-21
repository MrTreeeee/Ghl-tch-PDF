import copy
import os
import importlib.resources
import pdf_reader
import webbrowser

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap, QCloseEvent, QKeyEvent, QPainter
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QGraphicsScene, QGraphicsPixmapItem, QFileDialog
)

from functions import *
from my_classes import SignalNode


# 颜色变化曲线
def color_curve(target: int, rgb: int, x: int):
    return round((target - rgb) * x / 128 + rgb) if x < 128 else round((rgb - target) * x / 128 + target * 2 - rgb)


# 在颜色变化曲线上取样
def sample_points(target: int, r: int, g: int, b: int, r_list: list, g_list: list, b_list: list):
    for i in range(257):
        r_list.append(color_curve(target, r, i))
        g_list.append(color_curve(target, g, i))
        b_list.append(color_curve(target, b, i))


class glitchReader(QMainWindow):
    def __init__(self, file_path=None):
        super().__init__()
        # 视图信号组局部变量（实例化 SignalNode）
        bookmark_view = SignalNode('bookmark view', False)
        bookmark_search = SignalNode('bookmark search', False)
        url_search = SignalNode('url search', False)
        tt_view = SignalNode('tt view', False)
        bt_view = SignalNode('bt view', False)
        # 信号级别关系绑定
        bookmark_view.add_mutual_signals(url_search)
        bookmark_view.add_child_signal(bookmark_search)
        tt_view.add_mutual_signals(bt_view)

        # 方便在局部初始化的变量
        self.from_input_change = None
        self.list_index = 0
        self.bookmarks_key_words = ''
        self.current_links = []
        # self.display_text = ''  # 输入窗口展示的占位文本

        # 需要在全局初始化的变量
        self.doc_paras = {
            'doc': None,  # 打开的文件
            'doc name': '',  # 文件名
            'total page': 0,  # 总页数
            'current page index': 0,  # 当前页码
            # 'current page': None,  # 当前读取的页面
            'scale factor': 1.0,  # 缩放因子
            'ecn': 0,  # 页码纠错值
            'toc page': None,  # 目录页
            'bookmarks': [],  # 书签
            'focus pages': [],  # focus pages
            'focus page index': 0,  # focus pages list index
            'save file': '',  # 保存文件
            'save path': '',  # 保存路径
            'bm search result': [],  # 书签搜索结果
            # 信号组
            'real page': False,  # 显示真实页码
            'bm view': bookmark_view,  # 显示书签
            'bm search': bookmark_search,  # 显示书签搜索结果
            'url search': url_search,  # 显示超链接搜索结果
            'tt view': tt_view,  # 置顶置顶视图
            'bt view': bt_view,  # 置底置顶视图
            'save mode': True,  # 自动保存
            # 'make raw toc': True  # 执行生目录添加
        }
        self.doc_paras_copy = copy.deepcopy(self.doc_paras)  # copy参数字典用于操作

        # 键盘信号
        self.is_ctrl_pressed = False
        self.is_shift_pressed = False
        self.is_x_pressed = False

        # 窗口界面初始化
        self.ui = pdf_reader.Ui_MainWindow()  # 调用我们用Qt写好的主窗口
        self.ui.setupUi(self)
        self.scene = QGraphicsScene(self)  # 创建图形场景
        self.ui.graphicsView.setScene(self.scene)  # 设置图形视图的场景

        self.ui.graphicsView.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.pixmap_item = None
        self.resize(1920, 1080)
        with importlib.resources.path('resources', 'cat.png') as img_path:
            self.add_image(str(img_path))

        self.ui.open_button.clicked.connect(self.open_file_dialog)  # open按钮绑定打开文件方法

        if file_path:
            self.open_file(file_path)

    # 添加图片
    def add_image(self, image_path):
        # 1. 加载图片
        pixmap = QPixmap(image_path)

        # 2. 创建图片项并添加到场景
        self.pixmap_item = self.scene.addPixmap(pixmap)

        # 3. 设置场景大小为图片尺寸
        self.scene.setSceneRect(QRectF(pixmap.rect()))

    # def showEvent(self, event):
    #     """窗口显示时调整视图大小"""
    #     super().showEvent(event)
    #     if self.pixmap_item and self.doc_paras_copy['doc'] is None:
    #         # 延迟执行以确保视图有正确尺寸
    #         self.ui.graphicsView.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
    #
    # def resizeEvent(self, event):
    #     """窗口大小变化时重新调整视图"""
    #     super().resizeEvent(event)
    #     if self.pixmap_item and self.doc_paras_copy['doc'] is None:
    #         self.ui.graphicsView.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    # 打开文件选择对话框
    def open_file_dialog(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 文件", "",
                                                   "PDF Files (*.pdf);;All Files (*)", options=options)
        if file_path:
            self.open_file(file_path)

    # 打开一个文件的时候需要执行的操作
    def open_file(self, file_path):
        # 如果此时还有文件未关闭，则处理保存后，将文件参数重新初始化
        if self.doc_paras_copy['doc']:
            if self.doc_paras_copy['save mode']:
                save_data = {
                    "toc page": self.doc_paras_copy['toc page'],  # 目录页
                    "bookmarks": self.doc_paras_copy['bookmarks'],  # 书签
                    "tt view": self.doc_paras_copy['tt view'].value,  # 置顶置顶视图
                    "bt view": self.doc_paras_copy['bt view'].value,  # 置底置顶视图
                    "ecn": self.doc_paras_copy['ecn'],  # 页码纠错值
                }
                save_to_json(self.doc_paras_copy['save path'], save_data)
                self.doc_paras_copy['doc'].close()
        self.doc_paras_copy = copy.deepcopy(self.doc_paras)

        # 传递具体的文件参数
        self.doc_paras_copy['doc name'], form = os.path.splitext(os.path.basename(file_path))
        self.setWindowTitle(self.doc_paras_copy['doc name'])
        data_load_flag = False

        # 创建数据保存路径和文件
        self.doc_paras_copy['save file'] = self.doc_paras_copy['doc name'] + '.json'  # 设置保存文件名称
        save_folder = os.path.join(os.path.expanduser("~"), "Documents", "Glitch Reader save data")
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)
        self.doc_paras_copy['save path'] = os.path.join(save_folder, self.doc_paras_copy['save file'])  # 设置保存文件路径
        if not os.path.exists(self.doc_paras_copy['save path']):  # 若不存在保存文件则创建空.json文件
            # if form == '.pdf':
            #     add_fitz_toc(file_path)  # 将 get_toc 获取的目录加入当前文件
            with open(self.doc_paras_copy['save path'], 'w', encoding='utf-8'):
                pass
        else:
            if os.path.getsize(self.doc_paras_copy['save path']) > 0:
                load_from_json(self.doc_paras_copy, self.doc_paras_copy['save path'])
                dic = self.doc_paras_copy
                if not (dic['toc page'] is None and not dic['bookmarks'] and not dic['tt view'].value
                        and not dic['bt view'] and dic['ecn'] == 0):
                    data_load_flag = True

        # 读取数据后再打开文件
        self.doc_paras_copy['doc'] = fitz.open(file_path)
        self.doc_paras_copy['total page'] = self.doc_paras_copy['doc'].page_count

        self.show_page()
        self.change_button_style()
        if data_load_flag:
            self.ui.everything_edit.setPlaceholderText('Data has been loaded')
            self.ui.everything_edit.setStyleSheet('color: green;')
            QTimer.singleShot(1000, self.text_select_and_display)
        else:
            self.text_select_and_display()

    # 根据 current_page_index 属性读取页面并添加到场景显示
    def show_page(self):
        document = self.doc_paras_copy['doc']
        if document:
            # 获取当前页面
            scale_factor = self.doc_paras_copy['scale factor']
            current_page_index = self.doc_paras_copy['current page index']
            current_page = document[current_page_index]

            # 根据当前缩放因子获取页面的 Pixmap
            mat = fitz.Matrix(scale_factor, scale_factor)  # 创建缩放矩阵
            pix = current_page.get_pixmap(matrix=mat)  # 将页面转换为图像

            # 创建 QImage
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(img)

            # 清除场景
            self.scene.clear()

            # 添加 PDF图像到场景
            pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(pixmap_item)

            # 设置场景大小
            self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())

    # 放缩页面
    def zoom_in(self):
        self.doc_paras_copy['scale factor'] *= 1.2
        self.show_page()

    def zoom_out(self):
        # if self.doc_paras_copy['scale factor'] >= 1.2:
        self.doc_paras_copy['scale factor'] /= 1.2
        self.show_page()

    # 键盘按键监听
    def keyPressEvent(self, a0: QKeyEvent) -> None:
        if a0.key() == Qt.Key_Control:
            self.is_ctrl_pressed = True
        elif a0.key() == Qt.Key_X:
            self.is_x_pressed = True
        elif a0.key() == Qt.Key_Shift:
            self.is_shift_pressed = True

        if a0.key() == Qt.Key_Space and self.is_x_pressed:
            self.ui.everything_edit.setFocus()
        elif a0.key() == Qt.Key_Z and self.is_ctrl_pressed:
            if self.from_input_change is not None:
                self.doc_paras_copy['current page index'] = self.from_input_change
                self.show_page()
                self.text_select_and_display()
                self.from_input_change = None
        elif a0.key() == Qt.Key_Up or a0.key() == Qt.Key_W:  # Up/W
            self.handle_up_key()
        elif a0.key() == Qt.Key_Down or a0.key() == Qt.Key_S:  # Down/S
            self.handle_down_key()
        elif a0.key() == Qt.Key_Left or a0.key() == Qt.Key_A:  # Left/A
            self.handle_left_key()
        elif a0.key() == Qt.Key_Right or a0.key() == Qt.Key_D:  # Right/D
            self.handle_right_key()
        elif a0.key() == Qt.Key_Enter or a0.key() == Qt.Key_Return:  # Enter
            self.handle_enter_key()
        elif a0.key() == Qt.Key_Tab:  # Tab
            self.handle_tab_key()
        elif a0.key() == Qt.Key_Escape:  # Esc
            self.handle_escape_key()

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
    def handle_up_key(self):
        if self.is_ctrl_pressed:
            self.zoom_in()
        elif self.is_shift_pressed:
            if self.doc_paras_copy['bm view'].value:
                if self.doc_paras_copy['bm search'].value:
                    self.list_index = loop_list_index_dec(self.doc_paras_copy['bm search result'], self.list_index)
                else:
                    self.list_index = loop_list_index_dec(self.doc_paras_copy['bookmarks'], self.list_index)
            elif self.doc_paras_copy['url search'].value:
                self.list_index = loop_list_index_dec(self.current_links, self.list_index)
            self.text_select_and_display()
        else:
            self.ui.graphicsView.verticalScrollBar().setValue(
                self.ui.graphicsView.verticalScrollBar().value() - 80 * int(self.doc_paras_copy['scale factor'])
            )

    def handle_down_key(self):
        if self.is_ctrl_pressed:
            self.zoom_out()
        elif self.is_shift_pressed:
            if self.doc_paras_copy['bm view'].value:
                if self.doc_paras_copy['bm search'].value:
                    self.list_index = loop_list_index_inc(self.doc_paras_copy['bm search result'], self.list_index)
                else:
                    self.list_index = loop_list_index_inc(self.doc_paras_copy['bookmarks'], self.list_index)
            elif self.doc_paras_copy['url search'].value:
                self.list_index = loop_list_index_inc(self.current_links, self.list_index)
            self.text_select_and_display()
        else:
            self.ui.graphicsView.verticalScrollBar().setValue(
                self.ui.graphicsView.verticalScrollBar().value() + 80 * int(self.doc_paras_copy['scale factor'])
            )

    def handle_left_key(self):
        """处理左箭头键逻辑"""
        if self.is_ctrl_pressed:
            self.ui.graphicsView.horizontalScrollBar().setValue(
                self.ui.graphicsView.horizontalScrollBar().value() - 80 * int(self.doc_paras_copy['scale factor'])
            )
        else:
            if self.doc_paras_copy['tt view'].value:
                self.ui.graphicsView.verticalScrollBar().setValue(0)
            elif self.doc_paras_copy['bt view'].value:
                self.ui.graphicsView.verticalScrollBar().setValue(
                    self.ui.graphicsView.verticalScrollBar().maximum()
                )
            if self.doc_paras_copy['current page index'] > 0:
                self.doc_paras_copy['current page index'] -= 1
                self.show_page()
                self.text_select_and_display()

    def handle_right_key(self):
        """处理右箭头键逻辑"""
        if self.is_ctrl_pressed:
            self.ui.graphicsView.horizontalScrollBar().setValue(
                self.ui.graphicsView.horizontalScrollBar().value() + 80 * int(self.doc_paras_copy['scale factor'])
            )
        else:
            if self.doc_paras_copy['tt view'].value or self.doc_paras_copy['bt view'].value:
                self.ui.graphicsView.verticalScrollBar().setValue(0)
            if self.doc_paras_copy['current page index'] < self.doc_paras_copy['total page'] - 1:
                self.doc_paras_copy['current page index'] += 1
                self.show_page()
                self.text_select_and_display()

    def handle_enter_key(self):
        """处理回车键逻辑"""
        self.from_input_change = self.doc_paras_copy['current page index']

        if not self.is_shift_pressed:
            if self.ui.everything_edit.hasFocus():
                input_text = self.ui.everything_edit.text()
                self.ui.everything_edit.clear()
                self.ui.everything_edit.clearFocus()
                self.match_input(input_text)
        else:
            if self.doc_paras_copy['bm view'].value:
                if self.doc_paras_copy['bm search'].value:
                    if self.doc_paras_copy['bm search result']:
                        self.doc_paras_copy['current page index'] \
                            = int(self.doc_paras_copy['bm search result'][self.list_index][1]) - 1
                        self.show_page()
                else:
                    if self.doc_paras_copy['bookmarks']:
                        self.doc_paras_copy['current page index'] \
                            = int(self.doc_paras_copy['bookmarks'][self.list_index][1]) - 1
                        self.show_page()
            elif self.doc_paras_copy['url search'].value:
                self.open_current_link()

            self.text_select_and_display()

    def handle_tab_key(self):
        """处理Tab键逻辑"""
        if self.doc_paras_copy['focus pages']:
            self.doc_paras_copy['current page index'] \
                = self.doc_paras_copy['focus pages'][self.doc_paras_copy['focus page index']]
            self.show_page()
            self.text_select_and_display()
            self.doc_paras_copy['focus page index'] \
                = loop_list_index_inc(self.doc_paras_copy['focus pages'], self.doc_paras_copy['focus page index'])

    def handle_escape_key(self):
        """处理Esc键逻辑"""
        if self.ui.everything_edit.hasFocus():
            self.ui.everything_edit.clear()
            self.ui.everything_edit.clearFocus()
        else:
            self.clear_highlights()
            self.doc_paras_copy['bm view'].check_close_signal()
            self.list_index = 0
            self.text_select_and_display()

    # 鼠标事件监听
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:  # 左键往回翻页
            self.handle_left_key()
        elif event.button() == Qt.RightButton:  # 右键往后翻页
            self.handle_right_key()

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
        if self.doc_paras_copy['doc'] is not None:
            if self.doc_paras_copy['save mode']:
                # 需要保存的数据
                save_data = {
                    "toc page": self.doc_paras_copy['toc page'],  # 目录页
                    "bookmarks": self.doc_paras_copy['bookmarks'],  # 书签
                    "tt view": self.doc_paras_copy['tt view'].value,  # 置顶置顶视图
                    "bt view": self.doc_paras_copy['bt view'].value,  # 置底置顶视图
                    "ecn": self.doc_paras_copy['ecn'],  # 页码纠错值
                }
                save_to_json(self.doc_paras_copy['save path'], save_data)
        a0.accept()

    # 在浏览器中打开当前显示的链接
    def open_current_link(self):
        if self.list_index >= 0 and self.current_links:
            link = self.current_links[self.list_index]
            try:
                webbrowser.open(link["url"])
                self.statusBar().showMessage(f"directing: {link['url']}", 2000)
            except Exception as e:
                self.statusBar().showMessage(f"failed: {str(e)}", 2000)

    # 改变目录指示灯颜色
    def change_toc_light(self):
        if self.doc_paras_copy['toc page'] is not None:
            self.ui.toc_flag_label.setStyleSheet("background-color: rgb(95, 180, 102)")
        else:
            self.ui.toc_flag_label.setStyleSheet("background-color: rgb(226, 73, 46)")

    # 删增书签时指示灯闪烁白色后复原
    def blank_blink(self, target: int):
        r_list = []
        g_list = []
        b_list = []
        if self.doc_paras_copy['toc page'] is not None:
            sample_points(target, 95, 180, 102, r_list, g_list, b_list)
        else:
            sample_points(target, 226, 73, 46, r_list, g_list, b_list)

        for i in range(257):
            QTimer.singleShot(i, lambda r=r_list[i], g=g_list[i], b=b_list[i]: self.ui.toc_flag_label.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b});"))

    # 清除所有高亮矩形
    def clear_highlights(self):
        for item in self.scene.items():
            if isinstance(item, QGraphicsRectItem):
                self.scene.removeItem(item)

    # 改变tt/bt按钮样式
    def change_button_style(self):
        if self.doc_paras_copy['tt view'].value:
            self.ui.open_button.setText('TT')
        elif self.doc_paras_copy['bt view'].value:
            self.ui.open_button.setText('BT')
        elif not self.doc_paras_copy['save mode']:
            self.ui.open_button.setStyleSheet('color: red;')
        else:
            self.ui.open_button.setText('open')
            self.ui.open_button.setStyleSheet('color: black;')

    # 设置输入框占位文本
    # def set_placeholder(self, text: str):
    #     self.ui.everything_edit.setPlaceholderText(text)

    # 选择文本显示在输入框
    def text_select_and_display(self):
        self.clear_highlights()
        if self.doc_paras_copy['bm view'].value:  # 想看书签..
            if not self.doc_paras_copy['bookmarks']:  # 如果没有书签..
                text = "Can't be any emptier..."
            else:  # 确实有书签
                if self.doc_paras_copy['bm search'].value:  # 搜索书签
                    search_result = search_bookmarks(self.doc_paras_copy['bookmarks'], self.bookmarks_key_words)
                    show_result = show_bookmarks(search_result, self.doc_paras_copy['ecn'],
                                                 self.doc_paras_copy['real page'])
                    self.doc_paras_copy['bm search result'] = search_result
                    if search_result:  # 有搜到
                        self.ui.everything_edit.setStyleSheet(
                            '''
                            background-color: #c8dbe3; color: purple; 
                            text-decoration: underline black; 
                            text-decoration-style: wavy;
                            '''
                        )
                        text = f"[{show_result[self.list_index][0]}, {show_result[self.list_index][1]}]"
                    else:  # 没有搜到
                        text = 'No Match.'
                else:  # 展示全部书签
                    self.ui.everything_edit.setStyleSheet("background-color:#c8dbe3; color:purple;")
                    show_list = show_bookmarks(self.doc_paras_copy['bookmarks'],
                                               self.doc_paras_copy['ecn'], self.doc_paras_copy['real page'])
                    text = f"[{show_list[self.list_index][0]}, {show_list[self.list_index][1]}]"
        elif self.doc_paras_copy['url search'].value:  # 搜索超链接
            page = self.doc_paras_copy['doc'][self.doc_paras_copy['current page index']]
            self.current_links = extract_links(page)
            if self.current_links:
                text, rect_item = show_link(self.list_index, self.current_links, self.doc_paras_copy['scale factor'])
                self.ui.everything_edit.setStyleSheet("color: blue; text-decoration: underline;")
                self.scene.addItem(rect_item)
            else:
                text = 'No Links.'
        else:  # 显示页码
            self.ui.everything_edit.setStyleSheet("background-color:white; color:black;")
            page_num = page_adjust(self.doc_paras_copy['current page index'],
                                   self.doc_paras_copy['ecn'], self.doc_paras_copy['real page'])
            if page_num < 1:
                text = f"before text/{self.doc_paras_copy['total page']}"
            else:
                text = f"{page_num}/{self.doc_paras_copy['total page']}"

        self.ui.everything_edit.setPlaceholderText(text)

    # 处理输入窗口的用户输入
    def match_input(self, input_text: str):
        if re.search(r'real page\s*:?\s*(\d+)*\s*', input_text):  # 匹配占位符显示真实页数
            ecn = re.search(r'real page\s*:?\s*(\d+)*\s*', input_text).group(1)
            if ecn is not None:
                self.doc_paras_copy['ecn'] = ecn
            self.doc_paras_copy['real page'] = True
            self.text_select_and_display()
        elif re.search(r'pdf page\s*', input_text):  # 匹配显示pdf页数
            self.doc_paras_copy['real page'] = False
            self.text_select_and_display()
        elif re.search(r'(^\d+$)\s*', input_text):  # 页码跳转
            self.doc_paras_copy['current page index'] = page_jump(
                int(re.search(r'(^\d+$)\s*', input_text).group(1)),
                self.doc_paras_copy['ecn'], self.doc_paras_copy['real page']
            )
            self.show_page()
            self.text_select_and_display()
        elif re.search(r'^raw toc\s*$', input_text):  # 生目录跳转
            if self.doc_paras_copy['raw toc page'] is not None:
                self.doc_paras_copy['current page index'] = self.doc_paras_copy['raw toc page']
                self.show_page()
                self.text_select_and_display()
        elif re.search(r'set\s+toc\s*', input_text):  # 设置目录
            self.doc_paras_copy['toc page'] = self.doc_paras_copy['current page index']
            self.change_toc_light()
        elif re.search(r'del\s+toc\s*', input_text):  # 删除目录
            self.doc_paras_copy['toc page'] = None
            self.change_toc_light()
        elif re.search(r'^toc\s*$', input_text):  # 跳转目录
            self.doc_paras_copy['current page index'] = self.doc_paras_copy['toc page']
            self.show_page()
            self.text_select_and_display()
        elif re.search(r'focus\s*:?\s*(\d+(?:[ ,]\d+)*)', input_text):  # focus pages
            self.doc_paras_copy['focus pages'].clear()
            page_list = [int(num) for num in re.search(r'focus\s*:?\s*(\d+(?:[ ,]\d+)*)',
                                                       input_text).group(1).replace(',', ' ').split()]
            focus_list = focus_pages(page_list, self.doc_paras_copy['ecn'], self.doc_paras_copy['real page'])
            self.doc_paras_copy['focus pages'] = focus_list
        elif re.search(r'^bm\s*$', input_text):  # 查看书签
            self.doc_paras_copy['bm view'].update_signal()
            self.list_index = 0
            self.text_select_and_display()
        elif re.search(r'add\s+bm\s*:?\s*(.*)', input_text):  # 添加书签
            bm_title = re.search(r'add\s+bm\s*:?\s*(.*)', input_text).group(1)
            bm = make_bookmark(bm_title, self.doc_paras_copy['current page index'])
            if not any(item[0] == bm_title for item in self.doc_paras_copy['bookmarks']):
                self.doc_paras_copy['bookmarks'].append(bm)
                self.doc_paras_copy['bookmarks'].sort(key=lambda x: x[1])
                self.blank_blink(255)
                self.text_select_and_display()
        elif re.search(r'del\s+bm\s*:?\s*(.*)?\s*', input_text):  # 删除书签
            key_words = re.search(r'del\s+bm\s*:?\s*(.*)?\s*', input_text).group(1)
            if key_words is None:
                if any(item[1] == self.doc_paras_copy['current page index'] + 1
                       for item in self.doc_paras_copy['bookmarks']):
                    self.doc_paras_copy['bookmarks'] = [item for item in self.doc_paras_copy['bookmarks']
                                                        if item[1] != self.doc_paras_copy['current page index'] + 1]
            else:
                self.doc_paras_copy['bookmarks'] = del_bookmark(self.doc_paras_copy['bookmarks'], key_words)
            self.list_index = loop_list_index_inc(self.doc_paras_copy['bookmarks'], self.list_index)
            self.blank_blink(0)
            self.text_select_and_display()
        elif re.search(r'find bm\s*:?\s*(.*)\s*', input_text):  # 搜索书签
            self.doc_paras_copy['bm search'].open_signal()
            self.list_index = 0
            self.bookmarks_key_words = re.search(r'find bm\s*:?\s*(.*)\s*', input_text).group(1)
            self.text_select_and_display()
        elif re.search(r'^url\s*$', input_text):  # 搜索超链接
            self.doc_paras_copy['url search'].update_signal()
            self.list_index = 0
            self.text_select_and_display()
        elif re.search(r'^tt$\s*', input_text):  # tt view
            self.doc_paras_copy['tt view'].update_signal()
            self.change_button_style()
        elif re.search(r'^bt$\s*', input_text):  # bt view
            self.doc_paras_copy['bt view'].update_signal()
            self.change_button_style()
        elif re.search(r'^save\s*$', input_text):  # auto save
            self.doc_paras_copy['save mode'] = True
            self.change_button_style()
        elif re.search(r'no save\s*', input_text):  # no save
            self.doc_paras_copy['save mode'] = False
            self.change_button_style()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
    viewer = glitchReader(pdf_path)
    viewer.show()
    sys.exit(app.exec_())
