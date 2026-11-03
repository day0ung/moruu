import httpx
import pytest

from channels.threads.client import BASE, ThreadsClient, ThreadsError


def make(handler):
    http = httpx.Client(base_url=BASE, transport=httpx.MockTransport(handler))
    return ThreadsClient("123", "SECRET-TOKEN", http=http)


def test_post_text_creates_container_then_publishes():
    seen = []

    def handler(req):
        seen.append((req.method, req.url.path, dict(req.url.params)))
        return httpx.Response(200, json={"id": "c1" if req.url.path.endswith("/threads") else "m1"})

    assert make(handler).post_text("안녕", reply_to="m0") == "m1"
    method, path, params = seen[0]
    assert (method, path) == ("POST", "/v1.0/123/threads")
    assert params["media_type"] == "TEXT"
    assert params["text"] == "안녕"
    assert params["reply_to_id"] == "m0"
    assert params["access_token"] == "SECRET-TOKEN"
    assert seen[1][1] == "/v1.0/123/threads_publish"
    assert seen[1][2]["creation_id"] == "c1"


def test_error_has_code_and_no_token():
    def handler(req):
        return httpx.Response(400, json={"error": {"code": 190, "message": "Error validating access token"}})

    with pytest.raises(ThreadsError) as e:
        make(handler).post_text("x")
    assert e.value.code == "190"
    assert "SECRET-TOKEN" not in str(e.value)


def test_non_json_error_uses_status():
    with pytest.raises(ThreadsError) as e:
        make(lambda req: httpx.Response(502, text="bad gateway")).quota_left()
    assert e.value.code == "502"


def test_non_dict_error_body_uses_status():
    with pytest.raises(ThreadsError) as e:
        make(lambda req: httpx.Response(400, json=["oops"])).quota_left()
    assert e.value.code == "400"


def test_quota_left():
    body = {"data": [{"quota_usage": 4, "config": {"quota_total": 250}}]}
    assert make(lambda req: httpx.Response(200, json=body)).quota_left() == 246


def test_insights_reads_values_and_total_value():
    body = {"data": [
        {"name": "views", "values": [{"value": 42}]},
        {"name": "likes", "total_value": {"value": 3}},
    ]}
    seen = []

    def handler(req):
        seen.append(req.url)
        return httpx.Response(200, json=body)

    assert make(handler).insights("m1") == {"views": 42, "likes": 3}
    assert seen[0].path == "/v1.0/m1/insights"
    assert seen[0].params["metric"] == "views,likes,replies,reposts,quotes"


def test_refresh_token():
    def handler(req):
        assert req.url.path == "/refresh_access_token"
        assert req.url.params["grant_type"] == "th_refresh_token"
        return httpx.Response(200, json={"access_token": "NEW", "expires_in": 5184000})

    assert make(handler).refresh_token() == ("NEW", 5184000)


def image_handler(seen, statuses=("FINISHED",)):
    queue = list(statuses)
    counter = {"n": 0}

    def handler(req):
        seen.append((req.method, req.url.path, dict(req.url.params)))
        if req.method == "GET":
            return httpx.Response(200, json={"status": queue.pop(0) if len(queue) > 1 else queue[0]})
        if req.url.path.endswith("/threads_publish"):
            return httpx.Response(200, json={"id": "m1"})
        counter["n"] += 1
        return httpx.Response(200, json={"id": f"c{counter['n']}"})
    return handler


def make_img(handler):
    http = httpx.Client(base_url=BASE, transport=httpx.MockTransport(handler))
    return ThreadsClient("123", "SECRET-TOKEN", http=http, sleep=lambda s: None)


def test_post_images_single_image():
    seen = []
    assert make_img(image_handler(seen)).post_images("글", ["https://img/1.png"]) == "m1"
    create = seen[0][2]
    assert create["media_type"] == "IMAGE" and create["image_url"] == "https://img/1.png" and create["text"] == "글"
    assert seen[1][:2] == ("GET", "/v1.0/c1")
    assert seen[-1][1] == "/v1.0/123/threads_publish" and seen[-1][2]["creation_id"] == "c1"


def test_post_images_carousel():
    seen = []
    assert make_img(image_handler(seen)).post_images("글", ["https://img/1.png", "https://img/2.png"]) == "m1"
    posts = [p for m, path, p in seen if m == "POST" and path.endswith("/threads")]
    assert [p.get("is_carousel_item") for p in posts[:2]] == ["true", "true"]
    assert "text" not in posts[0]
    assert posts[2]["media_type"] == "CAROUSEL" and posts[2]["children"] == "c1,c2" and posts[2]["text"] == "글"
    assert seen[-1][2]["creation_id"] == "c3"


def test_post_images_waits_until_finished():
    seen = []
    make_img(image_handler(seen, ("IN_PROGRESS", "IN_PROGRESS", "FINISHED"))).post_images("글", ["https://img/1.png"])
    assert sum(1 for m, _, _ in seen if m == "GET") == 3


def test_post_images_error_status_raises():
    with pytest.raises(ThreadsError) as e:
        make_img(image_handler([], ("ERROR",))).post_images("글", ["https://img/1.png"])
    assert e.value.code == "media"


def test_post_images_rejects_more_than_20():
    with pytest.raises(ValueError):
        make_img(image_handler([])).post_images("글", [f"https://img/{i}.png" for i in range(21)])
