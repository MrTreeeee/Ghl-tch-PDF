"""
这个文件是所有实现阅读器主要功能的函数的集合
"""

import json
import os.path
import re
import sys

import fitz
from typing import Dict
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPen, QBrush, QColor
from PyQt5.QtWidgets import QGraphicsRectItem
from my_classes import PDFMultiPageWriter


def page_adjust(current_page_index: int, error_correct: int, real_page: bool):
    """页码调整，返回页码"""

    return current_page_index + 1 - error_correct if real_page else current_page_index + 1


def page_jump(dest: int, error_correct: int, real_page: bool):
    """页面跳转，返回页码下标"""

    return dest + error_correct - 1 if real_page else dest - 1


def focus_pages(page_list: list, error_correct: int, real_page: bool):
    """make focus pages, return page index"""

    return [page + error_correct - 1 for page in page_list] if real_page else [page - 1 for page in page_list]


def make_bookmark(title: str, current_page_index: int):
    """制作书签"""

    return [f'{title}', current_page_index + 1]


def del_bookmark(bookmark_list: list, key_words: str):
    """删除书签: 按关键字删除"""

    pattern = build_search_regex(key_words)
    return [item for item in bookmark_list if not pattern.search(item[0])]


def show_bookmarks(bookmark_list: list, error_correct: int, real_page: bool):
    """查看书签"""

    show_list = []
    for item in bookmark_list:
        show_list.append(item[:])
    if real_page:
        for item in show_list:
            item[1] -= error_correct
    return show_list


def search_bookmarks(bookmarks_list: list, key_words: str):
    """书签搜索"""

    pattern = build_search_regex(key_words)

    result = [item for item in bookmarks_list if pattern.search(item[0])]

    return result


def build_search_regex(user_input):
    """建立搜索模式"""

    # 用非单词字符（空格、逗号等）分割输入，过滤空字符串
    keywords = re.split(r'[\W_]+', user_input, flags=re.IGNORECASE)
    keywords = [kw for kw in keywords if kw]

    if not keywords:
        # 空输入匹配任意内容
        return re.compile(r'.*', re.IGNORECASE)

    # 构建正则表达式：每个关键词用 .*? 连接（非贪婪匹配任意字符）
    regex_str = r'.*?'.join(re.escape(kw) for kw in keywords)
    return re.compile(regex_str, re.IGNORECASE)


def loop_list_index_inc(show_list: list, show_list_index: int):
    """输入列表索引循环自增"""

    return show_list_index + 1 if show_list_index < len(show_list) - 1 else 0


def loop_list_index_dec(show_list: list, show_list_index: int):
    """输入列表索引循环自减"""

    return show_list_index - 1 if show_list_index > 0 else len(show_list) - 1


def save_to_json(save_file_path: str, save_data: Dict):
    """保存数据"""

    with open(save_file_path, 'w'):
        pass

    with open(save_file_path, 'w', encoding='utf-8') as file:
        json.dump(save_data, file, ensure_ascii=False, indent=4)


def load_from_json(init_data: Dict, load_path: str):
    """加载数据"""

    with open(load_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    for key0 in init_data.keys():
        for key1 in data.keys():
            if key0 == key1:
                if key0 == 'tt view' or key0 == 'bt view':
                    init_data[key0].value = data[key1]
                else:
                    init_data[key0] = data[key1]


def extract_toc(file_path):
    """获取目录文件通过 .get_toc() 方法得到的目录表中的非层级信息"""

    doc = fitz.open(file_path)
    toc = doc.get_toc()
    op1 = [[item[1], item[2]] for item in toc]
    for item in op1:
        item[0] = item[0][:72] + '...' if len(item[0]) > 75 else item[0]

    return op1


def add_fitz_toc(file_path):
    """对输入文件添加通过 get_toc 获取的目录页面并保存覆盖原文件"""

    _, form = os.path.splitext(os.path.basename(file_path))
    parent_dir = os.path.dirname(file_path)
    temp_file_path = os.path.join(parent_dir, 'temp_file' + form)

    writer = PDFMultiPageWriter(file_path)
    content = extract_toc(file_path)
    custom_style = {
        'fontsize': 12,
        'line_spacing': 28,
        'margin_top': 90,
        'margin_bottom': 60,
        'line_dashes': "[3 2]"  # 虚线样式
    }
    writer.add_content(
        content,
        title="Raw ToC",
        style=custom_style
    )
    writer.save(temp_file_path)

    os.remove(file_path)
    os.rename(temp_file_path, file_path)


# 超链接提取
def extract_links(page):
    """填充 current_links 列表为当前页面超链接信息"""

    current_links = []  # 因为只提前当前页面的链接，所以每次先清空列表

    # 1. 提取显式超链接（可点击区域）
    for link in page.get_links():
        if link["kind"] == fitz.LINK_URI:
            # 尝试获取链接文本，这里再写一个提取文本的函数
            link_text = extract_link_text(page, link["from"])
            current_links.append({
                "type": "explicit",
                "url": link["uri"],
                "rect": link["from"],
                "text": link_text if link_text else link["uri"]
            })

    # 2. 提取文本中的URL（非可点击但可能是超链接）
    text = page.get_text("text")
    text_urls = extract_text_urls(text, page)  # 包含4条信息的元素
    current_links.extend(text_urls)

    # 3. 按位置排序链接（从上到下）
    current_links.sort(key=lambda x: x["rect"].y0)

    return current_links


def extract_link_text(page, rect):
    """提取链接区域内的文本"""

    # 获取链接矩形区域内的所有单词
    words = page.get_text("words", clip=rect)

    # 按位置排序单词（从左到右，从上到下）
    words.sort(key=lambda w: (w[1], w[0]))

    # 合并单词形成文本
    link_text = " ".join(word[4] for word in words)

    # 清理文本（去除多余空格）
    return re.sub(r'\s+', ' ', link_text).strip()


def extract_text_urls(text, page):
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


def show_link(index, current_links, scale_factor):
    """显示指定索引的链接"""

    if 0 <= index < len(current_links):
        link = current_links[index]
        display_text = link["text"]

        if len(display_text) > 50:  # 截断过长的文本
            display_text = display_text[:47] + "..."

        return f"Link {index + 1}/{len(current_links)}:{display_text}", highlight_link(link["rect"], scale_factor)


def highlight_link(rect, scale_factor):
    """在PDF视图上高亮显示链接区域"""

    # 创建矩形项
    highlight_rect = QRectF(
        rect.x0 * scale_factor,
        rect.y0 * scale_factor,
        rect.width * scale_factor,
        rect.height * scale_factor)
    rect_item = QGraphicsRectItem(highlight_rect)

    # 设置边框和填充
    pen = QPen(QColor(255, 0, 0))  # 红色边框
    pen.setWidth(2)
    rect_item.setPen(pen)

    # 半透明填充
    brush = QBrush(QColor(255, 0, 0, 50))  # 半透明红色
    rect_item.setBrush(brush)

    # 确保高亮在最前面
    rect_item.setZValue(1)

    return rect_item
