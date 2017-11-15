# coding: utf-8

import logging
from threading import Lock

from sqlalchemy import create_engine, asc, desc
from sqlalchemy.orm import sessionmaker, scoped_session

from core.db.models import Session, SessionLogStep, User, Platform, Provider, Endpoint
from core.config import config

log = logging.getLogger(__name__)


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
            dbsession.expunge_all()
            dbsession.close()
    return wrapper


class Database(object):
    lock = Lock()

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
    def get_active_sessions(self, provider_id=None, dbsession=None):
        query = dbsession.query(Session)
        if provider_id:
            query = query.filter_by(provider_id=provider_id)
        return query.filter(Session.closed.is_(False)).all()

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
    def get_endpoints(self, provider_id=None, efilter="all", dbsession=None):
        base_query = dbsession.query(Endpoint)
        if provider_id:
            base_query = base_query.filter_by(provider_id=provider_id)

        if efilter == "all":
            return base_query.all()

        base_query = base_query.filter(Endpoint.deleted.is_(False))
        if efilter == "active":
            return base_query.all()
        if efilter == "using":
            return base_query.filter(Endpoint.in_use.is_(True)).all()
        if efilter == "pool":
            return base_query.filter(Endpoint.in_use.is_(False)).all()
        elif efilter == "wait for service" or efilter == "service":
            return base_query.filter_by(mode=efilter).order_by(asc(Endpoint.id)).all()
        else:
            return []

    @transaction
    def get_session_by_endpoint_id(self, endpoint_id, dbsession=None):
        return dbsession.query(Session).filter_by(endpoint_id=endpoint_id).order_by(desc(Session.id)).first()

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

    @transaction
    def get_all_plaftorms_list(self, dbsession=None):
        res = set()
        for provider in dbsession.query(Provider).filter_by(active=True).all():
            for platform in provider.platforms:
                res.add(platform.name)
        return res

    @transaction
    def get_endpoints_dict(self, provider_id=None, dbsession=None):
        if provider_id:
            endpoints_list = self.get_endpoints(provider_id=provider_id, efilter="active", dbsession=dbsession)
        else:
            endpoints_list = self.get_endpoints(efilter="active", dbsession=dbsession)
        return self._format_endpoints_dict(endpoints_list)

    @staticmethod
    def _format_endpoints_dict(endpoints_list):
        def print_view(e):
            return {
                "name": e.name,
                "ip": e.ip,
                "ready": e.ready,
                "created": e.created_time,
                "ports": e.ports
            }

        endpoints = {
            "pool": {
                'count': 0,
                'list': [],
            },
            "using": {
                'count': 0,
                'list': [],
            },
            "wait_for_service": {
                'count': 0,
                'list': [],
            },
            "on_service": {
                'count': 0,
                'list': [],
            },
            "total": 0,
        }

        for endpoint in endpoints_list:
            if endpoint.deleted:
                continue
            if endpoint.in_pool:
                endpoints["pool"]["count"] += 1
                endpoints["pool"]["list"].append(print_view(endpoint))
            if endpoint.in_use:
                endpoints["using"]["count"] += 1
                endpoints["using"]["list"].append(print_view(endpoint))
            if endpoint.in_service:
                endpoints["on_service"]["count"] += 1
                endpoints["on_service"]["list"].append(print_view(endpoint))
            if endpoint.wait_for_service:
                endpoints["wait_for_service"]["count"] += 1
                endpoints["wait_for_service"]["list"].append(print_view(endpoint))
            endpoints["total"] += 1

        return endpoints

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
    def register_provider(self, name, url, platforms, max_limit, dbsession=None):
        provider = dbsession.query(Provider).filter_by(url=url).first()
        if provider:
            provider.active = True
            provider.name = name
            provider.config = platforms
            provider.max_limit = max_limit
        else:
            provider = Provider(name=name, url=url, config=platforms, max_limit=max_limit)
        self.add(provider)
        return provider

    @transaction
    def unregister_provider(self, provider_id, dbsession=None):
        provider = dbsession.query(Provider).get(provider_id)
        provider.active = False
        self.update(provider)

    @transaction
    def add(self, obj, dbsession):
        """
        Add new object to DB
        """
        with self.lock:
            dbsession.add(obj)
            dbsession.commit()
            dbsession.expunge_all()

    @transaction
    def update(self, obj, dbsession):
        """
        Upload local object state to DB
        """
        with self.lock:
            dbsession.merge(obj)
            dbsession.commit()
            dbsession.expunge_all()

    @transaction
    def refresh(self, obj, dbsession):
        """
        Refresh object state from DB
        """
        with self.lock:
            dbsession.add(obj)
            dbsession.refresh(obj)
            dbsession.expunge_all()

    @transaction
    def delete(self, obj, dbsession):
        """
        Delete object from DB
        """
        with self.lock:
            dbsession.delete(obj)
            dbsession.commit()
            dbsession.expunge_all()
