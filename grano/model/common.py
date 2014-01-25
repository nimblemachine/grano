import uuid
from datetime import datetime
from slugify import slugify

from grano.core import db


def slugify_column(text):
    return slugify(text).replace('-', '_')


def make_token():
    return uuid.uuid4().get_hex()[15:]


class _CoreBase(object):
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    @classmethod
    def by_id(cls, id):
        q = db.session.query(cls).filter_by(id=id)
        return q.first()

    @classmethod
    def all(cls):
        return db.session.query(cls)


class IntBase(_CoreBase):
    id = db.Column(db.Integer, primary_key=True)

    def __repr__(self):
        return '<%s(%s)>' % (self.__class__.__name__, self.id)


class UUIDBase(_CoreBase):
    id = db.Column(db.Unicode, default=make_token, primary_key=True)

    def __repr__(self):
        return '<%s(%s)>' % (self.__class__.__name__, self.id)


class PropertyBase(object):

    @property
    def active_properties(self):
        q = self.properties.filter_by(active=True)
        q = q.order_by(self.PROPERTIES.name.desc())
        return q

    def _update_properties(self, properties):
        objs = list(self.active_properties)
        for name, prop in properties.items():
            create = True
            for obj in objs:
                if obj.name != name:
                    continue
                if obj.value == prop.get('value'):
                    create = False
                else:
                    obj.active = False
            if create and prop.get('value') is not None:
                self.PROPERTIES.save(self, name, prop)

    @classmethod
    def _filter_property(cls, q, name, value, only_active=True):
        q = q.join(cls.properties, aliased=True)
        q = q.filter(cls.PROPERTIES.name==name)
        q = q.filter(cls.PROPERTIES.value==value)
        if only_active:
            q = q.filter(cls.PROPERTIES.active==True)
        q = q.reset_joinpoint()
        return q


    @classmethod
    def by_property(cls, name, value, only_active=True):
        q = db.session.query(cls)
        q = cls._filter_property(q, name, value, only_active=only_active)
        return q
