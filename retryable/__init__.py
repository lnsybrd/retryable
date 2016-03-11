"""
Utility functions to retry calls
"""

# Standard imports
from __future__ import absolute_import
import functools
import logging
import time


def retry(no_retry_list=None, count=3, delay=1, backoff=2, callback=None):
    """
    A decorator for retrying a volatile function-call, with timed delay.

    :param no_retry_list: list of exception types that should not cause a retry.
    :type no_retry_list: list[Exception]
    :param count: number of retries before re-raising exception.
    :type count: int
    :param delay: number of seconds to elapse before retry.
                  Value must be greater than 0.
    :type delay: int
    :param backoff: each value of ``delay`` will be multiplied by ``backoff``
                    after each failure.  The default values ``(1, 2)`` then
                    result in a retry delay of 1s, 2s, and 4s for a total of
                    7 seconds before final exception is raised.
                    Value must be greater than 1.
    :type backoff: int
    :param callback: A callable called when an exception is caught, receiving
                     exception as first and only argument.  Such callable should
                     return a decision of ``True`` should a subsequent retries
                     be attempted.
    :type callback: callable

    Of note, any exception thrown from within a decorated function will contain
    the additional Attribute, ``retry_count``.  Note that although a function
    may be called seven times, its ``retry_count`` is only 6 -- that is, it was
    **retried** six times, for a total of 7 calls.

    Example usage, basic decorated form::

        >>> @retry(no_retry_list=[OSError], count=5, delay=0)
        ... def some_function():
        ...    raise AttributeError
        ...
        >>> some_function()
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
          File "retry.py", line 259, in wrapper
            raise final_exception
        AttributeError

    This decorator is extended to allow keyword arguments to be dynamically
    injected into the target callable at run-time by hidden keyword arguments.
    These have the same meaning as the decorator arguments ``count``,
    ``delay``, ``backoff``, and ``callback``, but with higher precedence:

    - ``_retry_count``
    - ``_retry_delay``
    - ``_retry_backoff``
    - ``_retry_callback``

    Extending the "basic decorated form" example::

        >>> def got_exception(exc):
        ...     print(('got', exc))
        ...     return True
        ...
        >>> some_function(_retry_count=2, _retry_delay=0, _retry_callback=got_exception)
        ('got', AttributeError())
        ('got', AttributeError())
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
            File "retry.py", line 259, in wrapper
                raise final_exception
            AttributeError
    """

    def _decorator(func):
        """ Outer function wrapper for ``@retry`` decorator. """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """ Inner function wrapper for ``@retry`` decorator. """
            # Extract retry args of of kwargs if they are there

            # Number of times to attempt a retry.
            # If _retry_countis None, no retries will be attempted.
            _retry_count = kwargs.pop('_retry_count', count) + 1

            # Multiplier on the current delay time applied after each retry.
            _retry_backoff = kwargs.pop('_retry_backoff', backoff)

            # The initial delay to use between attempt 0 and attempt 1.
            # After the first retry the current delay is multiplied by the _retry_backoff factor.
            _retry_delay = kwargs.pop('_retry_delay', delay)

            # Extract the callable we should use to filter retries
            _retry_callback = kwargs.pop('_retry_callback', callback)

            # Verify arguments if we should attempt retries
            if _retry_count > 0:
                if _retry_backoff < 1:
                    exc = ValueError("_retry_backoff must be >= 1")
                    exc.retry_count = 0
                    raise exc
                if _retry_delay < 0:
                    exc = ValueError("_retry_delay must be >= 0")
                    exc.retry_count = 0
                    raise exc

            # Set our starting point
            current_try = 1

            log = logging.getLogger('{0}.retry'.format(__name__))
            func_desc = ('{func_name}<args={args}, kwargs={kwargs}>'
                         .format(func_name=func.__name__, args=args, kwargs=kwargs))

            while True:
                log.debug('[{current_try} of {_retry_count}]'.format(
                    current_try=current_try, _retry_count=_retry_count))

                # pylint: disable=W0703
                #         Catching too general exception Exception
                try:
                    return func(*args, **kwargs)
                except Exception as caught_exc:
                    # decorate exception with number of *retries* attempted
                    caught_exc.retry_count = current_try - 1

                    # our final_exception is the last-most exception raised
                    # when the number of retries requested is exceeded.
                    final_exception = caught_exc

                    exc_name = caught_exc.__class__.__name__
                    exc_desc = ('{exc_name}: {exc_text}'.format(
                        exc_name=exc_name, exc_text=caught_exc))

                    log.warn('{func_desc} raised {exc_desc}; '
                             '{tries_left} tries remain'
                             .format(func_desc=func_desc,
                                     exc_desc=exc_desc,
                                     tries_left=(_retry_count - current_try)))

                    # we've exhausted our attempts
                    if current_try >= _retry_count:
                        log.error('failed: {func_desc} after {tries} tries'
                                  .format(func_desc=func_desc, tries=current_try))
                        break

                    else:
                        if no_retry_list:
                            # Check to see if the exception is in the
                            # no_retry_list.  If it is found, re-raise the caught exception and be done
                            _filter_func = lambda no_retry_e: isinstance(caught_exc, no_retry_e)
                            if len(list(filter(_filter_func, no_retry_list))) > 0:
                                log.warn('{0} in no_retry_list, re-raising'.format(exc_name))
                                raise caught_exc

                        # If we've gotten this far we have an exception we should attempt to
                        # retry First, give _retry_callback a chance to filter our behavior.
                        if _retry_callback:
                            try:
                                # If we should not retry lets exit here
                                _should_retry = _retry_callback(caught_exc)
                            except Exception as _callback_exc:
                                # log original `caught_exc' before it is lost !
                                log.fatal("_retry_callback={_retry_callback} "
                                          "raised {exc_name}: {exc_text}; expected boolean "
                                          "return value, traceback follows:".format(
                                              _retry_callback=_retry_callback,
                                              exc_name=_callback_exc.__class__.__name__,
                                              exc_text=_callback_exc))
                                log.exception(caught_exc)

                                # we must conform to our specification that
                                # *all* exceptions raised contain attribute
                                # `retry_count' before raising inner exception.
                                _callback_exc.retry_count = current_try
                                raise _callback_exc

                            log.debug('_retry_callback={_retry_callback} '
                                      'has determined that the function '
                                      '{may_retry} retry.'.format(
                                          _retry_callback=_retry_callback,
                                          may_retry='may' if _should_retry else 'may not'))

                            if not _should_retry:
                                raise caught_exc

                        log.debug('retry sleeping {0}s'.format(_retry_delay))
                        time.sleep(_retry_delay)

                        # Calculate next delay by factor of _retry_backoff.
                        _retry_delay *= _retry_backoff
                        current_try += 1

            raise final_exception

        return wrapper

    return _decorator
