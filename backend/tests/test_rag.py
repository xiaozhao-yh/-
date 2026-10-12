"""纯函数单元测试：rag.py 内部工具函数，零 DB / 零 API 依赖"""
import sys
import math

sys.path.insert(0, "..")

from app.services import rag


# ---------- _cosine ----------
class TestCosine:
    def test_identical(self):
        v = [0.1, 0.2, 0.3]
        assert abs(rag._cosine(v, v) - 1.0) < 1e-6

    def test_orthogonal(self):
        assert abs(rag._cosine([1, 0], [0, 1])) < 1e-6

    def test_opposite(self):
        assert rag._cosine([1, 0], [-1, 0]) < -0.999

    def test_zero_vector(self):
        assert rag._cosine([0, 0], [1, 2]) == 0.0

    def test_different_length_skipped(self):
        # 长度不等时调用方会跳过，这里直接调不会 crash
        assert rag._cosine([1, 2], [1, 2, 3]) is not None


# ---------- _tokenize / _keyword_overlap ----------
class TestKeywordOverlap:
    def test_ascii_token(self):
        score = rag._keyword_overlap("Python Flask MySQL", "熟悉 Python Flask 后端开发")
        # Python 和 Flask 都命中，>= 2
        assert score >= 2

    def test_chinese_bigram(self):
        score = rag._keyword_overlap("量化成果", "成果量化表达技巧，每条经历包含数字")
        # "成果" bigram 或单字命中
        assert score >= 1

    def test_no_overlap(self):
        score = rag._keyword_overlap("STAR 法则", "简历时间线断档怎么办")
        assert score == 0

    def test_empty_query(self):
        score = rag._keyword_overlap("", "任何内容")
        assert score == 0

    def test_empty_chunk(self):
        score = rag._keyword_overlap("Python", "")
        assert score == 0

    def test_mixed_cn_en(self):
        score = rag._keyword_overlap("Python 后端 接口开发", "用了 Python Flask 写接口")
        # Python + 接口 bigram 或单字
        assert score >= 2


# ---------- build_query ----------
class TestBuildQuery:
    def _resume(self, pos="后端开发", jd="熟悉 Python"):
        class R:
            target_position = pos
            job_desc = jd
            current_text = "张三 做了一个订单系统"
        return R()

    def test_scene_suggestion(self):
        q = rag.build_query(self._resume(), "suggestion")
        assert "目标岗位" in q
        assert "量化表达" in q

    def test_scene_score(self):
        q = rag.build_query(self._resume(), "score")
        assert "评分标准" in q

    def test_unknown_scene(self):
        q = rag.build_query(self._resume(), "unknown_scene")
        assert q  # 不崩溃、不为空
        assert "目标岗位" in q


# ---------- build_kb_message ----------
class TestBuildKbMessage:
    def test_none_input(self):
        assert rag.build_kb_message(None) is None

    def test_empty_list(self):
        assert rag.build_kb_message([]) is None

    def test_normal_refs(self):
        refs = [{"title": "来源A", "snippet": "片段内容A", "source_url": ""},
                {"title": "来源B", "snippet": "片段内容B", "source_url": "http://x"}]
        msg = rag.build_kb_message(refs)
        assert msg["role"] == "system"
        assert "来源A" in msg["content"]
        assert "片段内容A" in msg["content"]
        assert "（来源：http://x）" in msg["content"]  # 有 url 附加来源标注
        assert msg["content"].count("来源：") == 1     # 空 url 不附加

    def test_source_url_empty(self):
        refs = [{"title": "T", "snippet": "S", "source_url": ""}]
        msg = rag.build_kb_message(refs)
        assert "（来源：" not in msg["content"]
