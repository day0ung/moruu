import core
import channels.threads
import pipelines.threads_post


def test_packages_import():
    assert core and channels.threads and pipelines.threads_post
