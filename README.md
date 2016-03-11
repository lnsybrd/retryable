Retryable Python Functions
==========================

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
=======================

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
