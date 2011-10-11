
import weakref
import types


def create_weakmethod(unbound_method, im_self, im_class):
    """Allows the given callback to disappear
    when nobody else is referencing it.
    """
    ref = weakref.ref(im_self)
    im_self = None
    def wrapper(*args, **kw):
        obj = ref()
        if obj is None:
            return
        types.MethodType(unbound_method, obj, im_class)(*args, **kw)

    return wrapper
