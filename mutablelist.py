from sqlalchemy.ext.mutable import  Mutable

class MutableList(Mutable, list):
    """A list type that implements :class:`.Mutable`.
    """

    def append(self, *a, **kw):
        list.append(self, *a, **kw)
        self.changed()

    def remove(self, *a, **kw):
        list.remove(self, *a, **kw)
        self.changed()

    @classmethod
    def coerce(cls, key, value):
        """Convert plain list to instance of this class."""
        if not isinstance(value, cls):
            if isinstance(value, list):
                return cls(value)
            return Mutable.coerce(key, value)
        else:
            return value

    def __getstate__(self):
        return list(self)

    def __setstate__(self, state):
        self += state
