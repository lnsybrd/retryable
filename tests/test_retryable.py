import logging

logging.basicConfig(level=logging.DEBUG)

from retryable import retry

# The function to put under test
def _test_retry(_type_to_raise=None):
    _test_retry.call_count += 1
    if _type_to_raise:
        raise _type_to_raise


def test_no_retry_list(no_retry_exc=Exception):

    # function
    _under_test = retry(no_retry_list=[no_retry_exc])(_test_retry)

    # output storage
    _test_retry.call_count = 0
    exc = None

    # do it
    try:
        _under_test(no_retry_exc)
    except no_retry_exc as e:
        exc = e

    # verify
    assert(exc is not None)
    assert(isinstance(exc, no_retry_exc))
    assert(_test_retry.call_count == 1)


def test_retry_count():
    for x in range(0, 5):
        yield _test_retry_count, (x)


def _test_retry_count(retry_count=0, retry_delay=.01):

    # function
    _under_test = retry(count=retry_count,
                        delay=retry_delay)(_test_retry)

    # output storage
    _test_retry.call_count = 0
    exc = None

    # do it
    try:
        _under_test(RuntimeError)
    except RuntimeError as e:
        exc = e

    # verify
    assert(exc is not None)
    assert(isinstance(exc, RuntimeError))
    assert(_test_retry.call_count == retry_count + 1)


def test_retry_callable_false():
    _test_retry_callable(msg='false',
                         retry_count=3,
                         retry_callback_call_count=1,
                         under_test_call_count=1)


def test_retry_callable_true():
    _test_retry_callable(msg='true',
                         retry_count=3,
                         retry_callback_call_count=3,
                         under_test_call_count=4)


def _test_retry_callable(msg=None,
                         retry_count=3,
                         retry_delay=.01,
                         retry_callback_call_count=3,
                         under_test_call_count=4):
    # input
    def _retry_callback(exc_under_eval):
        # Return True if we should retry, false if we should not
        _retry_callback.call_count += 1
        return isinstance(exc_under_eval, MsgError) and exc_under_eval.msg == 'true'

    # Custom error
    class MsgError(RuntimeError):
        def __init__(self, msg=None, **kwargs):
            super(MsgError, self).__init__(**kwargs)
            self.msg = msg

    # function
    _under_test = retry(count=retry_count, delay=retry_delay, callback=_retry_callback)(_test_retry)

    # output storage
    _retry_callback.call_count = 0
    _test_retry.call_count = 0
    exc = None

    # test the no retry case
    try:
        _under_test(MsgError(msg=msg))
    except MsgError as e:
        exc = e

    # verify
    assert(exc is not None)
    assert(isinstance(exc, MsgError))
    assert(_retry_callback.call_count == retry_callback_call_count)
    assert(_test_retry.call_count == under_test_call_count)
