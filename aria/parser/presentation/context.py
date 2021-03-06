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


from .source import DefaultPresenterSource


class PresentationContext(object):
    """
    Presentation context.

    :ivar presenter: the generated presenter instance
    :vartype presenter: ~aria.parser.presentation.Presenter
    :ivar location: from where we will generate the presenter
    :vartype location: ~aria.parser.loading.Location
    :ivar presenter_source: for finding presenter classes
    :vartype presenter_source: ~aria.parser.presentation.PresenterSource
    :ivar presenter_class: overrides ``presenter_source`` with a specific class
    :vartype presenter_class: type
    :ivar import_profile: whether to import the profile by default (defaults to ``True``)
    :vartype import_profile: bool
    :ivar threads: number of threads to use when reading data
    :vartype threads: int
    :ivar timeout: timeout in seconds for loading data
    :vartype timeout: float
    :ivar print_exceptions: whether to print exceptions while reading data
    :vartype print_exceptions: bool
    """

    def __init__(self):
        self.presenter = None
        self.location = None
        self.presenter_source = DefaultPresenterSource()
        self.presenter_class = None  # overrides
        self.import_profile = True
        self.threads = 8  # reasonable default for networking multithreading
        self.timeout = 10  # in seconds
        self.print_exceptions = False

    def get(self, *names):
        """
        Gets attributes recursively from the presenter.
        """

        return self.presenter._get(*names) if self.presenter is not None else None

    def get_from_dict(self, *names):
        """
        Gets attributes recursively from the presenter, except for the last name which is used
        to get a value from the last dict.
        """

        return self.presenter._get_from_dict(*names) if self.presenter is not None else None
