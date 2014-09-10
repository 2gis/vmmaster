from .clone import Clone

from ..logger import log


class CloneFactory(object):
    def __new__(cls, *args, **kwargs):
        log.info("creating clone factory")
        inst = object.__new__(cls)
        return inst

    @classmethod
    def create_clone(cls, origin, session_id):
        clone = Clone(session_id, origin)
        try:
            clone = clone.create()
        except Exception:
            clone.delete()
            raise

        return clone