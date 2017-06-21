# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
classes:
    * Execution - execution implementation model.
    * Plugin - plugin implementation model.
    * Task - a task
"""

# pylint: disable=no-self-argument, no-member, abstract-method
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Text,
    DateTime,
    Boolean,
    Enum,
    String,
    Float,
    orm,
    PickleType)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import declared_attr

from ..orchestrator.exceptions import (TaskAbortException, TaskRetryException)
from . import mixins
from . import (
    relationship,
    types as modeling_types
)


class ExecutionBase(mixins.ModelMixin):
    """
    Execution model representation.
    """

    __tablename__ = 'execution'

    __private_fields__ = ['service_fk',
                          'service_template']

    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    PENDING = 'pending'
    STARTED = 'started'
    CANCELLING = 'cancelling'

    STATES = (SUCCEEDED, FAILED, CANCELLED, PENDING, STARTED, CANCELLING)
    END_STATES = (SUCCEEDED, FAILED, CANCELLED)

    VALID_TRANSITIONS = {
        PENDING: (STARTED, CANCELLED),
        STARTED: END_STATES + (CANCELLING,),
        CANCELLING: END_STATES,
        CANCELLED: PENDING
    }

    @orm.validates('status')
    def validate_status(self, key, value):
        """Validation function that verifies execution status transitions are OK"""
        try:
            current_status = getattr(self, key)
        except AttributeError:
            return
        valid_transitions = self.VALID_TRANSITIONS.get(current_status, [])
        if all([current_status is not None,
                current_status != value,
                value not in valid_transitions]):
            raise ValueError('Cannot change execution status from {current} to {new}'.format(
                current=current_status,
                new=value))
        return value

    created_at = Column(DateTime, index=True)
    started_at = Column(DateTime, nullable=True, index=True)
    ended_at = Column(DateTime, nullable=True, index=True)
    error = Column(Text, nullable=True)
    status = Column(Enum(*STATES, name='execution_status'), default=PENDING)
    workflow_name = Column(Text)

    def has_ended(self):
        return self.status in self.END_STATES

    def is_active(self):
        return not self.has_ended() and self.status != self.PENDING

    @declared_attr
    def logs(cls):
        return relationship.one_to_many(cls, 'log')

    @declared_attr
    def service(cls):
        return relationship.many_to_one(cls, 'service')

    @declared_attr
    def tasks(cls):
        return relationship.one_to_many(cls, 'task')

    @declared_attr
    def inputs(cls):
        return relationship.one_to_many(cls, 'input', dict_key='name')

    # region foreign keys

    @declared_attr
    def service_fk(cls):
        return relationship.foreign_key('service')

    # endregion

    # region association proxies

    @declared_attr
    def service_name(cls):
        """Required for use by SQLAlchemy queries"""
        return association_proxy('service', cls.name_column_name())

    @declared_attr
    def service_template(cls):
        """Required for use by SQLAlchemy queries"""
        return association_proxy('service', 'service_template')

    @declared_attr
    def service_template_name(cls):
        """Required for use by SQLAlchemy queries"""
        return association_proxy('service', 'service_template_name')

    # endregion

    def __str__(self):
        return '<{0} id=`{1}` (status={2})>'.format(
            self.__class__.__name__,
            getattr(self, self.name_column_name()),
            self.status
        )


class PluginBase(mixins.ModelMixin):
    """
    An installed plugin.

    Plugins are usually packaged as `wagons <https://github.com/cloudify-cosmo/wagon>`__, which
    are archives of one or more `wheels <https://packaging.python.org/distributing/#wheels>`__.
    Most of these fields are indeed extracted from the installed wagon's metadata.

    :ivar archive_name: Filename (not the full path) of the wagon's archive, often with a ".wgn"
                        extension
    :vartype archive_name: basestring
    :ivar distribution: The name of the operating system on which the wagon was installed (e.g.
                        "ubuntu")
    :vartype distribution: basestring
    :ivar distribution_release: The release of the operating system on which the wagon was installed
                                (e.g. "trusty")
    :vartype distribution_release: basestring
    :ivar distribution_version: The version of the operating system on which the wagon was installed
                                (e.g. "14.04")
    :vartype distribution_version: basestring
    :ivar package_name: The primary Python package name used when the wagon was installed, which is
                        one of the wheels in the wagon (e.g. "cloudify-script-plugin")
    :vartype package_name: basestring
    :ivar package_source: The full install string for the primary Python package name used when the
                          wagon was installed (e.g. "cloudify-script-plugin==1.2")
    :vartype package_source: basestring
    :ivar package_version: The version for the primary Python package name used when the wagon was
                           installed (e.g. "1.2")
    :vartype package_version: basestring
    :ivar supported_platform: If the wheels are *all* pure Python then this would be "any",
                              otherwise it would be the installed platform name (e.g.
                              "linux_x86_64")
    :vartype supported_platform: basestring
    :ivar supported_py_versions: The Python versions supported by all the wheels (e.g. ["py26",
                                 "py27"])
    :vartype supported_py_versions: [basestring]
    :ivar wheels: The filenames of the wheels archived in the wagon, often with a ".whl" extension
    :vartype wheels: [basestring]
    :ivar uploaded_at: Timestamp for when the wagon was installed
    :vartype uploaded_at: basestring
    """

    __tablename__ = 'plugin'

    @declared_attr
    def tasks(cls):
        return relationship.one_to_many(cls, 'task')

    archive_name = Column(Text, nullable=False, index=True)
    distribution = Column(Text)
    distribution_release = Column(Text)
    distribution_version = Column(Text)
    package_name = Column(Text, nullable=False, index=True)
    package_source = Column(Text)
    package_version = Column(Text)
    supported_platform = Column(Text)
    supported_py_versions = Column(modeling_types.StrictList(basestring))
    wheels = Column(modeling_types.StrictList(basestring), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, index=True)


class TaskBase(mixins.ModelMixin):
    """
    Represents the smallest unit of stateful execution in ARIA. The task state includes inputs,
    outputs, as well as an atomic status, ensuring that the task can only be running once at any
    given time.

    Tasks may be "one shot" or may be configured to run repeatedly in the case of failure.

    Tasks are often based on :class:`Operation`, and thus act on either a :class:`Node` or a
    :class:`Relationship`, however this is not required.

    :ivar node: The node actor (optional)
    :vartype node: :class:`Node`
    :ivar relationship: The relationship actor (optional)
    :vartype relationship: :class:`Relationship`
    :ivar plugin: The implementing plugin (set to None for default execution plugin)
    :vartype plugin: :class:`Plugin`
    :ivar function: Python path to an ``@operation`` function
    :vartype function: basestring
    :ivar arguments: Arguments that can be used by this task
    :vartype arguments: {basestring: :class:`Argument`}
    :ivar max_attempts: Maximum number of retries allowed in case of failure
    :vartype max_attempts: int
    :ivar retry_interval: Interval between retries (in seconds)
    :vartype retry_interval: int
    :ivar ignore_failure: Set to True to ignore failures
    :vartype ignore_failure: bool
    :ivar due_at: Timestamp to start the task
    :vartype due_at: datetime
    :ivar execution: Assigned execution
    :vartype execution: :class:`Execution`
    :ivar status: Current atomic status ('pending', 'retrying', 'sent', 'started', 'success',
                  'failed')
    :vartype status: basestring
    :ivar started_at: Timestamp for when task started
    :vartype started_at: datetime
    :ivar ended_at: Timestamp for when task ended
    :vartype ended_at: datetime
    :ivar attempts_count: How many attempts occurred
    :vartype attempts_count: int
    """

    __tablename__ = 'task'

    __private_fields__ = ['dependency_operation_task_fk', 'dependency_stub_task_fk', 'node_fk',
                          'relationship_fk', 'plugin_fk', 'execution_fk']

    START_WORKFLOW = 'start_workflow'
    END_WORKFLOW = 'end_workflow'
    START_SUBWROFKLOW = 'start_subworkflow'
    END_SUBWORKFLOW = 'end_subworkflow'
    STUB = 'stub'
    CONDITIONAL = 'conditional'

    STUB_TYPES = (
        START_WORKFLOW,
        START_SUBWROFKLOW,
        END_WORKFLOW,
        END_SUBWORKFLOW,
        STUB,
        CONDITIONAL,
    )

    PENDING = 'pending'
    RETRYING = 'retrying'
    SENT = 'sent'
    STARTED = 'started'
    SUCCESS = 'success'
    FAILED = 'failed'
    STATES = (
        PENDING,
        RETRYING,
        SENT,
        STARTED,
        SUCCESS,
        FAILED,
    )
    INFINITE_RETRIES = -1

    @declared_attr
    def execution(cls):
        return relationship.many_to_one(cls, 'execution')

    @declared_attr
    def execution_fk(cls):
        return relationship.foreign_key('execution', nullable=True)

    status = Column(Enum(*STATES, name='status'), default=PENDING)
    due_at = Column(DateTime, nullable=False, index=True, default=datetime.utcnow())
    started_at = Column(DateTime, default=None)
    ended_at = Column(DateTime, default=None)
    attempts_count = Column(Integer, default=1)

    _executor = Column(PickleType)
    _context_cls = Column(PickleType)
    _stub_type = Column(Enum(*STUB_TYPES))

    @declared_attr
    def logs(cls):
        return relationship.one_to_many(cls, 'log')

    @declared_attr
    def node(cls):
        return relationship.many_to_one(cls, 'node')

    @declared_attr
    def relationship(cls):
        return relationship.many_to_one(cls, 'relationship')

    @declared_attr
    def plugin(cls):
        return relationship.many_to_one(cls, 'plugin')

    @declared_attr
    def arguments(cls):
        return relationship.one_to_many(cls, 'argument', dict_key='name')

    function = Column(String)
    max_attempts = Column(Integer, default=1)
    retry_interval = Column(Float, default=0)
    ignore_failure = Column(Boolean, default=False)
    interface_name = Column(String)
    operation_name = Column(String)

    @property
    def actor(self):
        """
        Return the actor of the task
        :return:
        """
        return self.node or self.relationship

    @orm.validates('max_attempts')
    def validate_max_attempts(self, _, value):                                  # pylint: disable=no-self-use
        """Validates that max attempts is either -1 or a positive number"""
        if value < 1 and value != TaskBase.INFINITE_RETRIES:
            raise ValueError('Max attempts can be either -1 (infinite) or any positive number. '
                             'Got {value}'.format(value=value))
        return value

    # region foreign keys

    @declared_attr
    def node_fk(cls):
        return relationship.foreign_key('node', nullable=True)

    @declared_attr
    def relationship_fk(cls):
        return relationship.foreign_key('relationship', nullable=True)

    @declared_attr
    def plugin_fk(cls):
        return relationship.foreign_key('plugin', nullable=True)

    # endregion

    # region association proxies

    @declared_attr
    def node_name(cls):
        """Required for use by SQLAlchemy queries"""
        return association_proxy('node', cls.name_column_name())

    @declared_attr
    def relationship_name(cls):
        """Required for use by SQLAlchemy queries"""
        return association_proxy('relationship', cls.name_column_name())

    @declared_attr
    def execution_name(cls):
        """Required for use by SQLAlchemy queries"""
        return association_proxy('execution', cls.name_column_name())

    # endregion

    @staticmethod
    def abort(message=None):
        raise TaskAbortException(message)

    @staticmethod
    def retry(message=None, retry_interval=None):
        raise TaskRetryException(message, retry_interval=retry_interval)

    @declared_attr
    def dependency_fk(self):
        return relationship.foreign_key('task', nullable=True)

    @declared_attr
    def dependencies(cls):
        # symmetric relationship causes funky graphs
        return relationship.one_to_many_self(cls, 'dependency_fk')

    def has_ended(self):
        return self.status in (self.SUCCESS, self.FAILED)

    def is_waiting(self):
        if self._stub_type:
            return not self.has_ended()
        else:
            return self.status in (self.PENDING, self.RETRYING)

    @classmethod
    def from_api_task(cls, api_task, executor, **kwargs):
        instantiation_kwargs = {}

        if hasattr(api_task.actor, 'outbound_relationships'):
            instantiation_kwargs['node'] = api_task.actor
        elif hasattr(api_task.actor, 'source_node'):
            instantiation_kwargs['relationship'] = api_task.actor
        else:
            raise RuntimeError('No operation context could be created for {actor.model_cls}'
                               .format(actor=api_task.actor))

        instantiation_kwargs.update(
            {
                'name': api_task.name,
                'status': cls.PENDING,
                'max_attempts': api_task.max_attempts,
                'retry_interval': api_task.retry_interval,
                'ignore_failure': api_task.ignore_failure,
                'execution': api_task._workflow_context.execution,
                'interface_name': api_task.interface_name,
                'operation_name': api_task.operation_name,

                # Only non-stub tasks have these fields
                'plugin': api_task.plugin,
                'function': api_task.function,
                'arguments': api_task.arguments,
                '_context_cls': api_task._context_cls,
                '_executor': executor,
            }
        )

        instantiation_kwargs.update(**kwargs)

        return cls(**instantiation_kwargs)


class LogBase(mixins.ModelMixin):

    __tablename__ = 'log'

    __private_fields__ = ['execution_fk',
                          'task_fk']

    @declared_attr
    def execution(cls):
        return relationship.many_to_one(cls, 'execution')

    @declared_attr
    def task(cls):
        return relationship.many_to_one(cls, 'task')

    level = Column(String)
    msg = Column(String)
    created_at = Column(DateTime, index=True)

    # In case of failed execution
    traceback = Column(Text)

    # region foreign keys

    @declared_attr
    def execution_fk(cls):
        return relationship.foreign_key('execution')

    @declared_attr
    def task_fk(cls):
        return relationship.foreign_key('task', nullable=True)

    # endregion

    def __str__(self):
        return self.msg

    def __repr__(self):
        name = (self.task.actor if self.task else self.execution).name
        return '{name}: {self.msg}'.format(name=name, self=self)


class ArgumentBase(mixins.ParameterMixin):

    __tablename__ = 'argument'

    # region foreign keys

    @declared_attr
    def task_fk(cls):
        return relationship.foreign_key('task', nullable=True)

    @declared_attr
    def operation_fk(cls):
        return relationship.foreign_key('operation', nullable=True)

    # endregion

    # region many_to_one relationships

    @declared_attr
    def task(cls):
        return relationship.many_to_one(cls, 'task')

    @declared_attr
    def operation(cls):
        return relationship.many_to_one(cls, 'operation')

    # endregion
