from dub import cloud


def test_non_demo_outputs_go_under_the_expiring_prefix():
    assert cloud.output_prefix("abc", demo=False) == "jobs/abc"
    assert cloud.output_prefix("abc", demo=True) == "demo/abc"
