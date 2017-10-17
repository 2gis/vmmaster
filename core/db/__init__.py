# coding: utf-8

import logging
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, scoped_session

from core.db.models import Session, SessionLogStep, User, Platform, Provider, Endpoint
from core.utils import to_thread
from core.config import config

log = logging.getLogger(__name__)


def threaded_transaction(func):
    @to_thread
    def wrapper(self, *args, **kwargs):
        dbsession = sessionmaker(bind=self.engine)()
        try:
            return func(self, dbsession=dbsession, *args, **kwargs)
        except:
            dbsession.rollback()
            raise
        finally:
            dbsession.close()
    return wrapper


def transaction(func):
    def wrapper(self, *args, **kwargs):
        # Try to use passed dbsession
        if 'dbsession' in kwargs.keys():
            if kwargs['dbsession'] is not None:
                return func(self, *args, **kwargs)
        dbsession = self.DBSession()
        try:
            return func(self, dbsession=dbsession, *args, **kwargs)
        except:
            dbsession.rollback()
            raise
        finally:
            dbsession.close()
    return wrapper


class Database(object):
    def __init__(self, connection_string=None, sqlite=False):
        if not connection_string:
            connection_string = config.DATABASE

        if sqlite:
            self.engine = create_engine(connection_string)
        else:
            self.engine = create_engine(connection_string,
                                        pool_size=200,
                                        max_overflow=100,
                                        pool_timeout=60)

        self.session_maker = sessionmaker(bind=self.engine,
                                          autocommit=False,
                                          autoflush=True,
                                          expire_on_commit=False)
        self.DBSession = scoped_session(self.session_maker)

    @transaction
    def get_session(self, session_id, dbsession=None):
        if not session_id:
            return None
        try:
            return dbsession.query(Session).get(session_id)
        except:
            log.warning("Session {} not found in db".format(session_id))
            return None

    @transaction
    def get_active_sessions(self, dbsession=None):
        return dbsession.query(Session).filter(Session.closed.is_(False)).all()

    @transaction
    def get_last_session_step(self, session_id, dbsession=None):
        return dbsession.query(SessionLogStep).filter_by(
            session_id=session_id).order_by(
            desc(SessionLogStep.id)).first()

    @transaction
    def get_log_steps_for_session(self, session_id, dbsession=None):
        return dbsession.query(SessionLogStep).filter_by(
            session_id=session_id).order_by(
                desc(SessionLogStep.id)).all()

    @transaction
    def get_step_by_id(self, log_step_id, dbsession=None):
        return dbsession.query(SessionLogStep).get(log_step_id)

    @transaction
    def get_user(self, username=None, user_id=None, token=None, dbsession=None):
        if user_id:
            return dbsession.query(User).get(user_id)
        elif username:
            return dbsession.query(User).filter_by(username=username).first()
        elif token:
            return dbsession.query(User).filter_by(token=token).first()
        return None

    @transaction
    def get_endpoint(self, endpoint_id, dbsession=None):
        try:
            return dbsession.query(Endpoint).get(endpoint_id)
        except:
            return None

    @transaction
    def get_endpoints(self, provider_id, efilter="all", dbsession=None):
        base_query = dbsession.query(Endpoint).filter_by(provider_id=provider_id)
        if efilter == "all":
            return base_query.all()

        base_query = base_query.filter(Endpoint.deleted.is_(False))
        if efilter == "active":
            return base_query.all()
        if efilter == "using":
            return base_query.filter(Endpoint.in_use.is_(True)).all()
        if efilter == "pool":
            return base_query.filter(Endpoint.in_use.is_(False)).all()
        else:
            return []

    @transaction
    def get_provider(self, provider_id, dbsession=None):
        return dbsession.query(Provider).filter_by(id=provider_id).first()

    @transaction
    def get_active_providers(self, dbsession=None):
        return dbsession.query(Provider).filter_by(active=True).all()

    @transaction
    def get_platforms(self, provider_id, dbsession=None):
        db_platforms = dbsession.query(Platform).filter_by(provider_id=provider_id).all()
        return {db_platform.name: db_platform for db_platform in db_platforms}

    @transaction
    def get_platform(self, name, provider_id=None, dbsession=None):
        if provider_id:
            platform = dbsession.query(Platform).filter_by(provider_id=provider_id).filter_by(name=name).first()
        else:
            platform = dbsession.query(Platform).filter_by(name=name).first()
        if not platform:
            log.warning("Platform {} not found".format(name))
        return platform

    def register_platforms(self, provider, platforms):
        for name in platforms:
            platform = Platform(name)
            platform.provider = provider
            self.add(platform)

    @transaction
    def unregister_platforms(self, provider, dbsession=None):
        dbsession.query(Platform).filter_by(provider=provider).delete()
        dbsession.commit()

    @transaction
    def register_provider(self, name, url, platforms, dbsession=None):
        provider = dbsession.query(Provider).filter_by(url=url).first()
        if provider:
            provider.active = True
            provider.name = name
            provider.config = platforms
            self.add(provider)
        else:
            provider = self.add(Provider(name=name, url=url, config=platforms))
        return provider

    @transaction
    def unregister_provider(self, provider_id, dbsession=None):
        provider = dbsession.query(Provider).get(provider_id)
        provider.active = False
        self.update(provider)

    @transaction
    def add(self, obj, dbsession=None):
        dbsession.add(obj)
        dbsession.commit()
        return obj

    @transaction
    def update(self, obj, dbsession=None):
        dbsession.merge(obj)
        dbsession.commit()
        return obj

    def refresh(self, obj):
        """
        Try to get existing session attached to obj and refresh object state from DB
        """
        dbsession = self.session_maker.object_session(obj)
        if dbsession:
            dbsession.close()
            dbsession = self.DBSession()
        else:
            dbsession = self.DBSession()
        dbsession.add(obj)
        res = dbsession.refresh(obj)
        dbsession.close()  # TODO: make smart-transaction decorator
        return res

    @transaction
    def delete(self, obj, dbsession=None):
        obj_to_delete = dbsession.query(type(obj)).get(obj.id)
        dbsession.delete(obj_to_delete)
        dbsession.commit()
        return obj_to_delete
