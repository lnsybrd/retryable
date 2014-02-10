# Standard imports
import functools
import logging
import time

#: Module level logging for all retry logs.
log = logging.getLogger('retry')

# Default Constants
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_BACKOFF = 2
DEFAULT_RETRY_DELAY = 1


def retry(no_retry_list=None,
          count=DEFAULT_RETRY_COUNT,
          backoff=DEFAULT_RETRY_BACKOFF,
          delay=DEFAULT_RETRY_DELAY,
          callback=None):
    """
    This decorator wraps any function with retry logic.  After wrapping a function with this via::
        from retryable import retry

        @retry()
        def some_function(...):
            pass

        def some_function(...):
            pass

        retryable_func = retry(some_function)

    If all retry attempts fail, the wrapper will raise the exception caught during the last attempt.
    It will attach the ``retry_count`` attribute to the exception before it throws it.  The caller
    can then inspect the exception to see how many retries were attempted.

    If there are no retries attempted and the function raises, the original exception raised by the
    function will be passed up to the caller to be handled.

    Controlling Retry Logic
    ^^^^^^^^^^^^^^^^^^^^^^^^^

    The retry logic can be controlled via a few different ways:

    No Retry List
    =============

    If you have a list of exceptions that you know should not cause a retry, you can pass them into the
    decorator via the ``no_retry_list`` parameter.  If any exception in the ``no_retry_list`` parameter
    is caught during the execution of the wrapped function it will be reraised without a retry attempt.
    For example::

        # Do not retry if we get an OSError or an AttributeError
        @retry(no_retry_list=[OSError, AttributeError])
        def some_function(some_condition):
            if some_condition == 'os_error':
                raise OSError
            elif some_condition == 'attr_error':
                raise AttributeError
            else:
                raise RuntimeError

        # this will cause an immediate raise of OSError with no retries
        some_function('os_error')

        # This will cause a number of retries and then finally raise the RuntimeError thrown by the func.
        some_function('retry')

    If ``no_rety_list`` is empty any exception will cause a retry.

    Retries
    =============

    Number of tries. Useful when there is a retryable but we don't want to specify an _retry_count
    keyword argument each time the retryable is invoked.

    Order of precedence: retries value, followed by _retry_count. Defaults to None.

    Retry Callable
    ==============

    If the decision on whether to retry is more complex than just a simple Exception type you can provide
    a callable that will be used to determine if a call should be retried.  This callable is passed via the
    ``_retry_callback`` kwarg into the wrapped function.  The _retry_callback is then called when an
    exception is caught, passing in the caught exception.  The _retry_callback should return ``True``
    if a retry should be attempted or ``False`` if not.  A basic _retry_callback would look like this::

        # We are passed the exception that was caught
        def retry_filter(exc):
            # Do some kind of checking to determine if we should retry
            if hasattr(exc, 'retryflag'):
                return True
            else:
                return False

    How this would be used in a retryable function::

        @retry
        def some_function(condition):
            if condition == 'raise_retry':
                # Raise a RuntimeError with the retryflag set
                e = RuntimeError()
                e.retryflag = True
                raise e
            else:
                # Raise a normal RuntimeError with no flag
                raise RuntimeError()

        # Will retry
        some_function('raise_retry', _retry_callback=retry_filter)

        # Will not retry
        some_function('no_raise_retry', _retry_callback=retry_filter)

    Note: The supplied ``_retry_callback`` will only be executed for exceptions that are not in the
    ``no_retry_list``.

    Retry behavior
    ==============

    You can pass kwargs to control the retry behavior of a wrapped function.  This allows you to override
    the retry behavior at runtime.  The kwargs you can pass are:
        _retry_count:  This is the number attempts to try
        _retry_delay: The delay to use.  This delay will be used on the first retry attempt and then
                      increased by ^_retry_backoff for each subsequent attempt.
        _retry_backoff: The factor to successively multiply the delay by for the next attempt.

    These params are passed when the wrapped function is called, not when it is decorated.  Ie::
        @retry
        def some_function():
            raise err

        # Retry this up to 3 times and start with a delay of half a second.
        ret = some_function(_retry_count=3, _retry_delay=.5)
    """

    def _decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):

            # Extract retry args of of kwargs if they are there

            # Number of times to attempt a retry.  If _retry_count==None no retries will be attempted.
            _retry_count = kwargs.pop('_retry_count', count)

            # Multiplier on the current delay time applied after each retry.
            _retry_backoff = kwargs.pop('_retry_backoff', backoff)

            # The initial delay to use between attempt 0 and attempt 1.  After the first retry the current
            # delay is multiplied by the _retry_backoff factor.
            _retry_delay = kwargs.pop('_retry_delay', delay)

            # Extract the callable we should use to filter retries
            _retry_callback = kwargs.pop('_retry_callback', callback)

            # Verify arguments if we should attempt retries
            if _retry_count > 0:
                if _retry_backoff <= 1:
                    raise ValueError("_retry_backoff must be greater than 1")
                if _retry_delay < 0:
                    raise ValueError("_retry_delay must be greater than 0")

                current_delay = _retry_delay
                try_count = _retry_count + 1
            else:
                try_count = 1

            # Set our starting point
            current_try = 1

            while True:
                try:
                    log.info('Executing retryable: {0}({1}) - #{2} of {3}'
                             .format(f.__name__, args, current_try, try_count))

                    # Run the command, if all goes well we just return right here.
                    return f(*args, **kwargs)

                # Catch all exceptions
                except Exception as caught_exc:
                    last_exc = caught_exc

                    log.debug(
                        '{0} caused an exception of type {1}'
                        .format(f.__name__, type(caught_exc))
                    )

                    # Get out of the loop if we are done
                    if current_try >= try_count:
                        break
                    else:
                        # Check to see if the exception is in the no_retry_list
                        if no_retry_list:
                            # If the exception is not an instance of any type in the no_retry_list we raise
                            # the original here
                            if len(list(filter(lambda no_retry_e: isinstance(caught_exc,
                                                                             no_retry_e), no_retry_list))) > 0:
                                log.error(
                                    '{0} is not in the no_retry_list for function {1}.  Rethrowing'
                                    .format(type(caught_exc), f.__name__)
                                )
                                raise caught_exc

                        # If we've gotten this far we have an exception we should attempt to retry on
                        # First we will give the _retry_callback a chance to filter our behavior.
                        if _retry_callback:
                            log.debug('determining retryability with {0}'.format(_retry_callback))

                            try:
                                # If we should not retry lets exit here
                                _retryable = _retry_callback(caught_exc)
                            except Exception as _callback_exc:
                                log.error(
                                    '{0} raised {1} trying to determine if '
                                    '{2} was retryable. This kills the retry: {2}'
                                    .format(_retry_callback,
                                            type(_callback_exc),
                                            type(caught_exc),
                                            _callback_exc)
                                )
                                log.exception(_callback_exc)
                                raise _callback_exc

                            if not _retryable:
                                log.error(
                                    '{0} says that {1} is not retryable'
                                    .format(_retry_callback,
                                            type(caught_exc))
                                )
                                raise caught_exc

                            # Attempt the retry
                            log.debug(
                                '{0} failed with {1}, trying {2} more times'
                                .format(f.__name__,
                                        caught_exc,
                                        (try_count-current_try))
                            )

                        log.debug(
                            '{0} will retry in {1} seconds'
                            .format(f.__name__, current_delay)
                        )

                        time.sleep(current_delay)

                        # Make the next wait longer. This
                        current_delay *= _retry_backoff

                        # Update the counter
                        current_try += 1

                        # Attach the number of retries we attempted
                        caught_exc.retry_count = current_try

            log.debug('Completed {0} tries'.format(current_try))

            # if we got here we should throw whatever the last thing we got was
            raise last_exc

        return wrapper

    return _decorator
