# -*- coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2005-2007 Async Open Source <http://www.async.com.br>
## All rights reserved
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU Lesser General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Lesser General Public License for more details.
##
## You should have received a copy of the GNU Lesser General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., or visit: http://www.gnu.org/.
##
## Author(s):       Evandro Vale Miquelito      <evandro@async.com.br>
##                  Johan Dahlin                <jdahlin@async.com.br>
##
""" Base routines for domain modules """

from kiwi.component import get_utility
from sqlobject import SQLObject
from sqlobject import ForeignKey, BoolCol
from sqlobject.inheritance import InheritableSQLObject
from sqlobject.dbconnection import DBAPI, Transaction
from sqlobject.converters import sqlrepr
from sqlobject.sqlbuilder import SQLExpression, AND, const
from zope.interface.interface import adapter_hooks

from stoqlib.database.interfaces import IDatabaseSettings
from stoqlib.domain.transaction import TransactionEntry
from stoqlib.lib.component import Adapter, Adaptable
from stoqlib.database.runtime import (StoqlibTransaction, get_current_user,
                                      get_current_station)


DATABASE_ENCODING = 'UTF-8'

#
# Persistent SQLObject adapters
#

class SQLObjectAdapter(Adapter):
    def __init__(self, adaptable, kwargs):
        Adapter.__init__(self, adaptable)

        if adaptable:
            kwargs['_original'] = adaptable

        self.__dict__['_original'] = adaptable

    def get_adapted(self):
        return self._original

class AdaptableSQLObject(Adaptable):
    @classmethod
    def registerFacet(cls, facet, *ifaces):
        super(AdaptableSQLObject, cls).registerFacet(facet, *ifaces)

        if not issubclass(facet, (SQLObject, InheritableSQLObject)):
            return

        # This might not be the best location to do this, but it has
        # a nice lazy property to it. The alternative would be to
        # attach it to all domain objects during startup, or just
        # load the schema definition from postgres dynamically.
        if not hasattr(facet, '_original'):
            facet.sqlmeta.addColumn(ForeignKey(cls.__name__,
                                    name='_original',
                                    forceDBName=True))


def _adaptable_sqlobject_adapter_hook(iface, obj):
    """A zope.interface hook used to fetch an adapter when calling
    iface(adaptable).
    It fetches the facet type and does a select in the database to
    see if the object is present.

    @param iface: the interface to adapt to
    @param obj: object we want to adapt
    """

    # We're only interested in Adaptable subclasses which defines
    # the getFacetType method
    if not isinstance(obj, AdaptableSQLObject):
        return

    try:
        facetType = obj.getFacetType(iface)
    except LookupError:
        # zope.interface will handle this and raise TypeError,
        # see InterfaceClass.__call__ in zope/interface/interface.py
        return None

    if not facetType:
        return

    # Persistant Adapters
    if issubclass(facetType, SQLObjectAdapter):
        # FIXME: Use selectOneBy
        results = facetType.selectBy(
            _originalID=obj.id, connection=obj.get_connection())

        if results.count() == 1:
            return results[0]
    # Non-Persistant Adapters
    else:
        return facetType(obj)

adapter_hooks.append(_adaptable_sqlobject_adapter_hook)

#
# Abstract classes
#


class AbstractModel(object):
    """Generic methods for any domain classes."""

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if type(self) is not type(other):
            return False
        return self.id == other.id

    #
    # Overwriting some SQLObject methods
    #

    def _create(self, *args, **kwargs):
        conn = kwargs.get('connection', self._connection)
        user = get_current_user(conn)
        station = get_current_station(conn)

        timestamp = const.NOW()
        for entry, entry_type in [('te_created', TransactionEntry.CREATED),
                                  ('te_modified', TransactionEntry.MODIFIED)]:
            kwargs[entry] = TransactionEntry(
                te_time=timestamp,
                user_id=user and user.id,
                station_id=station and station.id,
                type=entry_type,
                connection=conn)
        super(AbstractModel, self)._create(*args, **kwargs)

    @classmethod
    def select(cls, clause=None, connection=None, **kwargs):
        cls._check_connection(connection)
        if clause and not isinstance(clause, SQLExpression):
            raise TypeError("Stoqlib doesn't support non sqlbuilder queries")
        clause_repr = sqlrepr(clause, get_utility(IDatabaseSettings).rdbms)
        if isinstance(clause_repr, unicode):
            clause = clause_repr.encode(DATABASE_ENCODING)
        return super(AbstractModel, cls).select(clause=clause,
                                                connection=connection,
                                                **kwargs)

    @classmethod
    def selectBy(cls, connection=None, **kw):
        cls._check_connection(connection)
        for field_name, search_str in kw.items():
            if not isinstance(search_str, unicode):
                continue
            kw[field_name] = search_str.encode(DATABASE_ENCODING)
        return super(AbstractModel, cls).selectBy(connection=connection,
                                                  **kw)

    @classmethod
    def selectOne(cls, clause=None, clauseTables=None, lazyColumns=False,
                  connection=None):
        cls._check_connection(connection)
        if clause and not isinstance(clause, SQLExpression):
            raise TypeError("Stoqlib doesn't support non sqlbuilder queries")
        clause_repr = sqlrepr(clause, get_utility(IDatabaseSettings).rdbms)
        if isinstance(clause_repr, unicode):
            clause = clause_repr.encode(DATABASE_ENCODING)
        return super(AbstractModel, cls).selectOne(
            clause=clause,
            clauseTables=clauseTables,
            lazyColumns=lazyColumns,
            connection=connection)

    @classmethod
    def selectOneBy(cls, clause=None, connection=None, **kw):
        cls._check_connection(connection)
        for field_name, search_str in kw.items():
            if not isinstance(search_str, unicode):
                continue
            kw[field_name] = search_str.encode(DATABASE_ENCODING)
        return super(AbstractModel, cls).selectOneBy(connection=connection,
                                                     **kw)

    def _SO_setValue(self, name, value, from_, to):
        super(AbstractModel, self)._SO_setValue(name, value, from_, to)

        if not self.sqlmeta._creating:
            connection = self._connection
            if isinstance(connection, StoqlibTransaction):
                connection.add_modified_object(self)

    #
    # Classmethods
    #

    @classmethod
    def _check_connection(cls, connection):
        if connection is None and issubclass(cls, InheritableSQLObject):
            # For an uncertain reason SQLObject doesn't send child
            # connection to its parent. the interesting thing is that
            # the connection is actually properly set on the instances
            return
        if connection is None:
            raise ValueError("You must provide a valid connection "
                             "argument for class %s" % cls)
        if not isinstance(connection, (Transaction, DBAPI)):
            raise TypeError("The argument connection must be of type "
                            "Transaction, or DBAPI got %r instead"
                            % connection)

    #
    # General methods
    #

    def clone(self):
        """Get a persistent copy of an existent object. Remember that we can
        not use copy because this approach will not activate SQLObject
        methods which allow creating persitent objects. We also always
        need a new id for each copied object.
        """
        columns = self.sqlmeta.columnList

        if isinstance(self, InheritableSQLObject):
            # This is an InheritableSQLObject object and we also
            # need to copy data from the parent.
            # XXX SQLObject should provide a get_parent method.
            columns += self.sqlmeta.parentClass.sqlmeta.columnList

        kwargs = {}
        for column in columns:
            if column.origName == 'childName':
                continue
            kwargs[column.origName] = getattr(self, column.origName)

        klass = type(self)
        return klass(connection=self._connection, **kwargs)

    def get_connection(self):
        return self._connection

class BaseDomain(AbstractModel, SQLObject):
    """An abstract mixin class for domain classes"""


#
# Base classes
#


class Domain(BaseDomain, AdaptableSQLObject):
    """If you want to be able to extend a certain class with adapters or
    even just have a simple class without sublasses, this is the right
    choice.
    """
    def __init__(self, *args, **kwargs):
        BaseDomain.__init__(self, *args, **kwargs)
        AdaptableSQLObject.__init__(self)

    def _create(self, id, **kw):
        if not isinstance(self._connection, StoqlibTransaction):
            raise TypeError(
                "creating a %s instance needs a StoqlibTransaction, not %s"
                % (self.__class__.__name__,
                   self._connection.__class__.__name__))
        BaseDomain._create(self, id, **kw)

    @property
    def user(self):
        return self.te_modified.user

    @classmethod
    def iselect(cls, iface, *args, **kwargs):
        """Like select, but search on the adapter implementing the interface iface
        associated with the domain class cls.

        @param iface: interface
        @returns: a SQLObject search result
        """
        adapter = cls.getAdapterClass(iface)
        return adapter.select(*args, **kwargs)

    @classmethod
    def iselectBy(cls, iface, *args, **kwargs):
        """Like selectBy, but search on the adapter implementing the interface iface
        associated with the domain class cls.

        @param iface: interface
        @returns: a SQLObject search result
        """
        adapter = cls.getAdapterClass(iface)
        return adapter.selectBy(*args, **kwargs)

    @classmethod
    def iselectOne(cls, iface, *args, **kwargs):
        """Like selectOne, but search on the adapter implementing the interface iface
        associated with the domain class cls.

        @param iface: interface
        @returns: None, object or raises SQLObjectMoreThanOneResultError
        """
        adapter = cls.getAdapterClass(iface)
        return adapter.selectOne(*args, **kwargs)

    @classmethod
    def iselectOneBy(cls, iface, *args, **kwargs):
        """Like selectOneBy, but search on the adapter implementing the interface iface
        associated with the domain class cls.

        @param iface: interface
        @returns: None, object or raises SQLObjectMoreThanOneResultError
        """
        adapter = cls.getAdapterClass(iface)
        return adapter.selectOneBy(*args, **kwargs)

    @classmethod
    def iget(cls, iface, object_id, **kwargs):
        """Like get, but gets on the adapter implementing the interface iface
        associated with the domain class cls.

        @param iface: interface
        @param object_id: id of object
        @returns: the SQLObject
        """
        adapter = cls.getAdapterClass(iface)
        return adapter.get(object_id, **kwargs)


class ValidatableDomain(Domain):

    _is_valid_model = BoolCol(default=False, forceDBName=True)

    #
    # Useful methods to deal with transaction isolation problems. See
    # domain/base docstring for further informations
    #

    def set_valid(self):
        if self._is_valid_model:
            raise ValueError('This model is already valid.')
        self._is_valid_model = True

    def set_invalid(self):
        if not self._is_valid_model:
            raise ValueError('This model is already invalid.')
        self._is_valid_model = False

    def get_valid(self):
        return self._is_valid_model

    @classmethod
    def select(cls, clause=None, connection=None, **kwargs):
        # This make queries in stoqlib applications consistent
        query = cls.q._is_valid_model == True
        if clause:
            clause = AND(query, clause)
        else:
            clause = query
        return super(AbstractModel, cls).select(clause=clause,
                                                connection=connection,
                                                **kwargs)

    @classmethod
    def selectBy(cls, connection=None, **kw):
        # This make queries in stoqlib applications consistent
        kw['_is_valid_model'] = True
        return super(ValidatableDomain, cls).selectBy(
            connection=connection, **kw)

    @classmethod
    def selectOne(cls, clause=None, clauseTables=None, lazyColumns=False,
                  connection=None):
        if clause and not isinstance(clause, SQLExpression):
            raise TypeError("Stoqlib doesn't support non sqlbuilder queries")
        # This make queries in stoqlib applications consistent
        query = cls.q._is_valid_model == True
        if clause:
            clause = AND(query, clause)
        else:
            clause = query
        return super(ValidatableDomain, cls).selectOne(
            clause=clause,
            clauseTables=clauseTables,
            lazyColumns=lazyColumns,
            connection=connection)

    @classmethod
    def selectOneBy(cls, clause=None, connection=None, **kw):
        kw['_is_valid_model'] = True
        return super(ValidatableDomain, cls).selectOneBy(
            connection=connection, **kw)



class InheritableModel(AbstractModel, InheritableSQLObject, AdaptableSQLObject):
    """Subclasses of InheritableModel are able to be base classes of other
    classes in a database level. Adapters are also allowed for these classes
    """
    def __init__(self, *args, **kwargs):
        AbstractModel.__init__(self)
        InheritableSQLObject.__init__(self, *args, **kwargs)
        AdaptableSQLObject.__init__(self)


class BaseSQLView:
    """A base marker class for SQL Views"""


#
# Adapters
#


class ModelAdapter(BaseDomain, SQLObjectAdapter):

    def __init__(self, _original=None, *args, **kwargs):
        SQLObjectAdapter.__init__(self, _original, kwargs) # Modifies kwargs
        BaseDomain.__init__(self, *args, **kwargs)


class InheritableModelAdapter(AbstractModel, InheritableSQLObject, SQLObjectAdapter):

    def __init__(self, _original=None, *args, **kwargs):
        AbstractModel.__init__(self)
        SQLObjectAdapter.__init__(self, _original, kwargs) # Modifies kwargs
        InheritableSQLObject.__init__(self, *args, **kwargs)

for klass in (InheritableModel, ValidatableDomain, Domain, ModelAdapter,
              InheritableModelAdapter):
    sqlmeta = klass.sqlmeta
    sqlmeta.cacheValues = False
    sqlmeta.addColumn(ForeignKey('TransactionEntry', name='te_created',
                                 default=None))
    sqlmeta.addColumn(ForeignKey('TransactionEntry', name='te_modified',
                                 default=None))

