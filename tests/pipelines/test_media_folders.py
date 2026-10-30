import logging
from dataclasses import replace

from channels.gdrive.client import DriveError
from core.models import Post
from pipelines.media_folders.__main__ import run

LOG = logging.getLogger("test")
SHORT = Post("p1", "YT-1", "", "", None, "", None, channel="YT-쇼핑")
LONG = replace(SHORT, page_id="p2", content_id="YT-롱폼-1", channel="YT-롱폼")


class Store:
    def __init__(self, posts):
        self.posts, self.set = posts, []

    def missing_media_folders(self):
        return list(self.posts)

    def set_media_folder(self, post, url):
        self.set.append((post.content_id, url))


def test_creates_folders_and_notifies():
    made, sent = [], []
    store = Store([SHORT, LONG])
    assert run(store, lambda p: made.append(p.content_id) or f"https://d/{p.content_id}", LOG, sent.append) == 0
    assert made == ["YT-1", "YT-롱폼-1"]
    assert store.set == [("YT-1", "https://d/YT-1"), ("YT-롱폼-1", "https://d/YT-롱폼-1")]
    assert sent == ["📁 자료 폴더 2개 만듦"]


def test_nothing_to_do_sends_nothing():
    sent = []
    assert run(Store([]), lambda p: "x", LOG, sent.append) == 0
    assert sent == []


def test_drive_error_skips_that_post():
    def make(p):
        if p.content_id == "YT-1":
            raise DriveError(403, "no")
        return "https://d/ok"

    store, sent = Store([SHORT, LONG]), []
    assert run(store, make, LOG, sent.append) == 1
    assert store.set == [("YT-롱폼-1", "https://d/ok")]
    assert sent == ["📁 자료 폴더 1개 만듦 · 실패 1개 (YT-1: [403] no)"]
