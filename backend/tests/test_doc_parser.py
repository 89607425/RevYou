"""Tests for DocParser."""
import pytest
from app.services.doc_parser import DocParser


SAMPLE_MD = """# 用户中心改版需求

## 1. 背景
现有用户中心页面陈旧，需要改版提升体验。

## 2. 功能需求

### 2.1 个人信息展示
展示用户头像、昵称、注册时间。

### 2.2 安全设置
支持修改密码、绑定手机。
"""


def test_parse_markdown_basic():
    doc = DocParser.parse_markdown(SAMPLE_MD, "test.md")
    assert doc.title == "用户中心改版需求"
    assert doc.source_type == "markdown"
    assert len(doc.sections) >= 5

    headings = [s.heading for s in doc.sections]
    assert "1. 背景" in headings
    assert "2.1 个人信息展示" in headings


def test_parse_markdown_sections_have_content():
    doc = DocParser.parse_markdown(SAMPLE_MD)
    bg = next(s for s in doc.sections if s.heading == "1. 背景")
    assert len(bg.paragraphs) > 0
    assert "用户中心" in bg.paragraphs[0]


def test_context_text_includes_sections():
    doc = DocParser.parse_markdown(SAMPLE_MD)
    ctx = doc.to_context_text()
    assert "用户中心改版需求" in ctx
    assert "2.2 安全设置" in ctx


def test_parse_unsupported():
    with pytest.raises(ValueError):
        DocParser.parse("/tmp/test.xyz")


def test_parse_markdown_no_headings():
    doc = DocParser.parse_markdown("只是一段没有标题的文本。")
    assert len(doc.sections) >= 1
    assert doc.sections[0].paragraphs
