"""后端单元测试：纯函数 + 独立模块逻辑，零 DB / 零 API 依赖"""
import sys
sys.path.insert(0, "..")

# =========================================================
# 1. rag.py 纯函数（余弦 / tokenize / keyword overlap / build_query / build_kb_message）
# =========================================================
class TestRagPure:
    def test_cosine_identical(self):
        from app.services.rag import _cosine
        v = [0.1, 0.2, 0.3]
        assert abs(_cosine(v, v) - 1.0) < 1e-6

    def test_cosine_orthogonal(self):
        from app.services.rag import _cosine
        assert abs(_cosine([1, 0], [0, 1])) < 1e-6

    def test_cosine_zero_vector(self):
        from app.services.rag import _cosine
        assert _cosine([0, 0], [1, 2]) == 0.0

    def test_keyword_overlap_ascii(self):
        from app.services.rag import _keyword_overlap
        assert _keyword_overlap("Python Flask MySQL", "熟悉 Python Flask 后端开发") >= 2

    def test_keyword_overlap_cn_bigram(self):
        from app.services.rag import _keyword_overlap
        assert _keyword_overlap("量化成果", "成果量化表达技巧") >= 1

    def test_keyword_overlap_no_hit(self):
        from app.services.rag import _keyword_overlap
        assert _keyword_overlap("STAR 法则", "简历时间线断档怎么办") == 0

    def test_keyword_overlap_empty(self):
        from app.services.rag import _keyword_overlap
        assert _keyword_overlap("", "任何") == 0
        assert _keyword_overlap("Python", "") == 0

    def test_build_query_scenes(self):
        from app.services.rag import build_query
        class R:
            target_position = "后端"
            job_desc = "Python"
            current_text = "张三 做了订单系统"
        assert "量化表达" in build_query(R(), "suggestion")
        assert "评分标准" in build_query(R(), "score")
        assert "目标岗位" in build_query(R(), "unknown_scene")

    def test_build_kb_message_empty(self):
        from app.services.rag import build_kb_message
        assert build_kb_message(None) is None
        assert build_kb_message([]) is None

    def test_build_kb_message_format(self):
        from app.services.rag import build_kb_message
        refs = [
            {"title": "来源A", "snippet": "片段A", "source_url": ""},
            {"title": "来源B", "snippet": "片段B", "source_url": "http://x"},
        ]
        msg = build_kb_message(refs)
        assert msg["role"] == "system"
        assert "来源A" in msg["content"]
        assert "（来源：http://x）" in msg["content"]  # 有 url 才附加
        assert msg["content"].count("来源：") == 1     # 空 url 不附加


# =========================================================
# 2. _trim_history：服务端多轮对话裁剪逻辑（含真实 bug 修复验证）
# =========================================================
class TestTrimHistory:
    @staticmethod
    def _call(h):
        from app.routers.ai import _trim_history
        return _trim_history(h)

    def test_dict_input(self):
        """前端传 list[dict]——这是真实调用路径，之前代码 t.role 是 bug"""
        out = self._call([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "ho"},
        ])
        assert out == [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "ho"},
        ]

    def test_role_whitelist(self):
        """只保留 user / assistant，过滤 system / tool 等"""
        h = [
            {"role": "user", "content": "hi"},
            {"role": "system", "content": "sys"},    # 过滤
            {"role": "assistant", "content": "ho"},
            {"role": "tool", "content": "x"},       # 过滤
        ]
        out = self._call(h)
        assert len(out) == 2
        assert [t["role"] for t in out] == ["user", "assistant"]

    def test_max_turns_cropped(self):
        from app.routers.ai import MAX_HISTORY_TURNS
        h = [{"role": "user", "content": f"消息{i}"} for i in range(20)]
        out = self._call(h)
        assert len(out) == MAX_HISTORY_TURNS

    def test_max_content_length(self):
        from app.routers.ai import MAX_TURN_CHARS
        long = "A" * (MAX_TURN_CHARS + 100)
        out = self._call([{"role": "user", "content": long}])
        assert len(out[0]["content"]) == MAX_TURN_CHARS

    def test_empty_content_filtered(self):
        out = self._call([
            {"role": "user", "content": ""},
            {"role": "user", "content": "   "},
            {"role": "user", "content": "有效"},
        ])
        assert len(out) == 1
        assert out[0]["content"] == "有效"

    def test_empty_input(self):
        assert self._call([]) == []
        assert self._call(None) == []


# =========================================================
# 3. _save_failed / _save_history 参数透传（函数签名验证）
# =========================================================
class TestSaveSignature:
    def test_save_history_accepts_status(self):
        from app.routers.ai import _save_history
        import inspect
        sig = inspect.signature(_save_history)
        assert "status" in sig.parameters

    def test_save_failed_exists(self):
        from app.routers import ai as ai_mod
        assert hasattr(ai_mod, "_save_failed")
        assert callable(ai_mod._save_failed)
