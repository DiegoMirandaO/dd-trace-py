import dogpile

from ddtrace.internal.utils.formats import asbool
from ddtrace.trace import Pin


def _wrap_lock_ctor(func, instance, args, kwargs):
    """
    This seems rather odd. But to track hits, we need to patch the wrapped function that
    dogpile passes to the region and locks. Unfortunately it's a closure defined inside
    the get_or_create* methods themselves, so we can't easily patch those.
    """
    func(*args, **kwargs)
    ori_backend_fetcher = instance.value_and_created_fn

    def wrapped_backend_fetcher():
        pin = Pin.get_from(dogpile.cache)
        if not pin or not pin.enabled():
            return ori_backend_fetcher()

        hit = False
        expired = True
        try:
            value, createdtime = ori_backend_fetcher()
            hit = value is not dogpile.cache.api.NO_VALUE
            # dogpile sometimes returns None, but only checks for truthiness. Coalesce
            # to minimize APM users' confusion.
            expired = instance._is_expired(createdtime) or False
            return value, createdtime
        finally:
            # Keys are checked in random order so the 'final' answer for partial hits
            # should really be false (ie. if any are 'negative', then the tag value
            # should be). This means ANDing all hit values and ORing all expired values.
            span = pin.tracer.current_span()
            if span:
                span.set_tag("hit", asbool(span.get_tag("hit") or "True") and hit)
                span.set_tag("expired", asbool(span.get_tag("expired") or "False") or expired)

    instance.value_and_created_fn = wrapped_backend_fetcher
