"""파이프라인 테스트용 가짜 저장소·클라이언트."""
from dataclasses import replace
from datetime import datetime

from channels.threads.client import ThreadsError
from core.models import KST, Post

BASE_POST = Post(
    page_id="page-1",
    content_id="TH-LIVING-20261101-001",
    role="정보",
    text="좁은 집 수납 팁",
    link=None,
    disclosure="",
    scheduled_at=datetime(2026, 11, 1, 8, 0, tzinfo=KST),
)


def make_post(**overrides) -> Post:
    return replace(BASE_POST, **overrides)


class FakeStore:
    def __init__(self, due=(), recent=(), fail_mark_posted=False):
        self.due = list(due)
        self.recent = list(recent)
        self.fail_mark_posted = fail_mark_posted
        self.posting = []
        self.reverted = []
        self.posted, self.failed, self.failures, self.metrics, self.collected = [], [], [], [], []

    def approved_threads_due(self, now):
        return list(self.due)

    def posted_threads_since(self, since):
        return [p for p in self.recent if p.posted_at and p.posted_at >= since]

    def mark_posting(self, post):
        self.posting.append(post.content_id)

    def mark_approved(self, post):
        self.reverted.append(post.content_id)

    def mark_posted(self, post, media_id, reply_id, at):
        if self.fail_mark_posted:
            raise RuntimeError("notion down")
        self.posted.append((post.content_id, media_id, reply_id))

    def mark_failed(self, post, error):
        self.failed.append((post.content_id, error))

    def log_failure(self, content_id, step, code, message, retries, final, at):
        self.failures.append((content_id, step, code, final))

    def add_metrics(self, post, hours, actual_hours, metrics, at):
        self.metrics.append((post.content_id, hours, actual_hours, metrics))

    def mark_collected(self, post, hours):
        self.collected.append((post.content_id, sorted(hours)))


class FakeClient:
    def __init__(self, fail_times=0, error_code="1", quota=250, insights=None):
        self.calls = []
        self.quota = quota
        self._fail = fail_times
        self._code = error_code
        self._insights = insights or {"views": 10}
        self._n = 0

    def quota_left(self):
        return self.quota

    def post_text(self, text, reply_to=None):
        self.calls.append((text, reply_to))
        if self._fail > 0:
            self._fail -= 1
            raise ThreadsError(self._code, "boom")
        self._n += 1
        return f"m{self._n}"

    def insights(self, media_id):
        self.calls.append(("insights", media_id))
        if self._fail > 0:
            self._fail -= 1
            raise ThreadsError(self._code, "boom")
        return dict(self._insights)
