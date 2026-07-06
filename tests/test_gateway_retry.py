from scripts.gateway.retry import RetryPolicy, load_retry_policy


def test_is_retryable_status_matches_configured_codes():
    policy = RetryPolicy(max_attempts=3, base_delay=0.5, max_delay=8.0, jitter=0.2, retry_status_codes={429, 503})
    assert policy.is_retryable_status(429)
    assert policy.is_retryable_status(503)
    assert not policy.is_retryable_status(200)
    assert not policy.is_retryable_status(404)


def test_delay_grows_exponentially_and_caps_at_max_delay():
    policy = RetryPolicy(max_attempts=5, base_delay=1.0, max_delay=4.0, jitter=0.0, retry_status_codes=set())
    # jitter=0 so delay() is exactly the capped exponential backoff
    assert policy.delay(1) == 1.0   # 1.0 * 2^0
    assert policy.delay(2) == 2.0   # 1.0 * 2^1
    assert policy.delay(3) == 4.0   # 1.0 * 2^2 = 4.0, at the cap
    assert policy.delay(4) == 4.0   # 1.0 * 2^3 = 8.0, capped to max_delay


def test_delay_jitter_stays_within_expected_spread():
    policy = RetryPolicy(max_attempts=3, base_delay=2.0, max_delay=8.0, jitter=0.5, retry_status_codes=set())
    for _ in range(50):
        d = policy.delay(1)  # raw = 2.0, spread = +/-1.0
        assert 1.0 <= d <= 3.0


def test_delay_never_negative_even_with_large_jitter():
    policy = RetryPolicy(max_attempts=3, base_delay=1.0, max_delay=8.0, jitter=1.0, retry_status_codes=set())
    for _ in range(50):
        assert policy.delay(1) >= 0.0


def test_load_retry_policy_reads_gateway_toml():
    policy = load_retry_policy()
    assert policy.max_attempts == 3
    assert policy.base_delay == 0.5
    assert policy.max_delay == 8.0
    assert policy.retry_status_codes == {429, 500, 502, 503, 504}
