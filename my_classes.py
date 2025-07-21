"""
这个文件装填一些需要的类
"""

import fitz


# 信号节点类，实例包含参数：信号名称，信号值；以及一个添加子级信号的方法
class SignalNode:
    def __init__(self, name: str, value: bool):
        self.name = name
        self.value = value
        self.child_signals = []
        self.parent_signals = []
        self.mutual_signals = []

    def add_child_signal(self, node: 'SignalNode'):  # 添加子级信号
        self.child_signals.append(node)
        node.parent_signals.append(self)

    def add_mutual_signals(self, node: 'SignalNode'):  # 添加互斥信号
        self.mutual_signals.append(node)
        node.mutual_signals.append(self)

    def open_signal(self):  # 打开信号方法
        # is_legal = False if self.parent_signals and not self.parent_signals[-1].value else True
        self.value = True
        for signal in self.mutual_signals:
            signal.close_signal()
        if not self.parent_signals:
            return
        else:
            for signal in self.parent_signals:
                signal.open_signal()

    def close_signal(self):  # 关闭信号方法
        self.value = False
        if not self.child_signals:
            return
        else:
            for signal in self.child_signals:
                signal.close_signal()

    def update_signal(self):  # 更新信号方法
        self.open_signal() if not self.value else self.close_signal()

    def check_close_signal(self):  # 搜索并关闭当前信号所在的互斥层中最末端的开启状态信号
        if not self.value and all(not signal.value for signal in self.mutual_signals):
            return
        elif self.value:
            if (not signal.value for signal in self.child_signals):  # 满足该条件的信号一定是某个互斥分支的末端开启信号
                self.close_signal()
                return
            else:
                for signal in self.child_signals:
                    signal.check_close_signal()
        else:
            for signal in self.mutual_signals:
                signal.check_close_signal()


class PDFMultiPageWriter:
    def __init__(self, input_file=None):
        """
        初始化PDF写入器

        参数:
        input_file - 可选，要修改的现有PDF文件路径
        """
        if input_file:
            self.doc = fitz.open(input_file)
        else:
            self.doc = fitz.open()

        # 默认样式设置
        self.default_style = {
            'margin_top': 80,  # 上边距
            'margin_bottom': 70,  # 下边距
            'margin_left': 50,  # 左边距
            'margin_right': 50,  # 右边距
            'line_spacing': 30,  # 行间距
            'fontname': 'helv',  # 默认字体
            'fontsize': 14,  # 正文字号
            'title_fontsize': 24,  # 标题字号
            'header_fontsize': 10,  # 页眉字号
            'footer_fontsize': 10,  # 页脚字号
            'text_color': (0, 0, 0),  # 文本颜色
            'header_color': (0.4, 0.4, 0.4),  # 页眉颜色
            'footer_color': (0.4, 0.4, 0.4),  # 页脚颜色
            'line_color': (0.9, 0.9, 0.9),  # 分隔线颜色
            'line_width': 0.5,  # 分隔线宽度
            'line_dashes': None  # 分隔线样式（None为实线）
        }

    def add_content(self, contents, title=None, style=None):
        """
        添加多页内容（自动分页）

        参数:
        contents - 二维内容列表
        title - 可选，文档标题
        style - 可选，自定义样式字典
        """
        # 合并样式
        style = {**self.default_style, **(style or {})}

        # 添加标题页（如果需要）

        if title:
            self._add_title_page(title, style)

        # 计算每页可容纳的行数
        page_height = fitz.paper_size("a4")[1]  # A4高度842点
        usable_height = page_height - style['margin_top'] - style['margin_bottom']
        lines_per_page = int(usable_height // style['line_spacing'])

        # 分块处理内容
        total_items = len(contents)
        for page_num, start_idx in enumerate(range(0, total_items, lines_per_page)):
            # 获取当前页内容块
            end_idx = min(start_idx + lines_per_page, total_items)
            page_contents = contents[start_idx:end_idx]

            # 创建新页面
            page = self.doc.new_page()

            # 添加内容
            self._add_page_content(page, page_contents, page_num, lines_per_page, style)

    def _add_title_page(self, title, style):
        """添加标题页"""
        title_page = self.doc.new_page()

        # 计算居中位置
        page_width = title_page.rect.width
        page_height = title_page.rect.height

        # 添加主标题
        title_width = fitz.get_text_length(title, "helv", style['title_fontsize'])
        title_x = (page_width - title_width) / 2
        title_y = page_height / 2 - 50

        title_page.insert_text(
            (title_x, title_y),
            title,
            fontname="helv",
            fontsize=style['title_fontsize'],
            color=style['text_color']
        )

        # 添加副标题（可选）
        subtitle = "Ghlýtch Reader"
        subtitle_size = style['title_fontsize'] * 0.6
        subtitle_width = fitz.get_text_length(subtitle, "helv", subtitle_size)
        subtitle_x = (page_width - subtitle_width) / 2
        subtitle_y = title_y + style['title_fontsize'] * 1.5

        title_page.insert_text(
            (subtitle_x, subtitle_y),
            subtitle,
            fontname="helv",
            fontsize=subtitle_size,
            color=style['header_color']
        )

    @staticmethod
    def _add_page_content(page, contents, page_num, lines_per_page, style):
        """在页面上添加内容项"""
        page_width = page.rect.width

        # 添加内容行
        for i, content in enumerate(contents):
            if len(content) < 2:
                continue  # 跳过无效项

            # 计算当前行位置
            line_idx = i + (page_num * lines_per_page)
            y_pos = style['margin_top'] + (i * style['line_spacing'])

            # 添加行号（可选）
            line_num = line_idx + 1
            page.insert_text(
                (style['margin_left'], y_pos),
                f"{line_num}.",
                fontname=style['fontname'],
                fontsize=style['fontsize'] * 0.8,
                color=style['text_color']
            )

            # 左对齐文本
            left_text = str(content[0])
            left_x = style['margin_left'] + 30  # 留出编号空间
            page.insert_text(
                (left_x, y_pos),
                left_text,
                fontname=style['fontname'],
                fontsize=style['fontsize'],
                color=style['text_color']
            )

            # 右对齐文本
            right_text = str(content[1])
            text_width = fitz.get_text_length(right_text, style['fontname'], style['fontsize'])
            right_x = page_width - style['margin_right'] - text_width

            page.insert_text(
                (right_x, y_pos),
                right_text,
                fontname=style['fontname'],
                fontsize=style['fontsize'],
                color=style['text_color']
            )

            # 添加分隔线
            if i < len(contents) - 1:  # 最后一行不添加
                line_y = y_pos + style['line_spacing'] * 0.8
                page.draw_line(
                    (left_x, line_y),
                    (page_width - style['margin_right'], line_y),
                    color=style['line_color'],
                    width=style['line_width'],
                    dashes=style['line_dashes']
                )

    def save(self, output_path):
        """保存文档"""
        self.doc.save(output_path)
        self.doc.close()
        # print(f"PDF已保存至: {output_path}")
