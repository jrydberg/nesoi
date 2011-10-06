# Copyright 2011 Johan Rydberg
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from twisted.web import http

from nesoi import rest


class WebhookResourceMixin:
    """Mixin for resource controllers that want to provide webhooks
    subscriptions on their resource.

    This mixin only implements the discovery part of the webhooks.  A
    webhook resource also has to be present in the routing table.
    """

    def head(self, router, request, url, **args):
        """Response with a link to the subscriptions resource"""
        request.setHeader('Link', '%s, rel="Subscriptions"' % (
            str(url.child('web-hooks'))))
        return http.OK


class WebhookResource(object):
    """Resource for web-hooks."""

    def __init__(self, model, kwname, method_name):
        self.model = model
        self.kwname = kwname
        self.method_name = method_name

    def put(self, router, request, url, config, hookname=None, **kwargs):
        """Update an existing web-hook watcher."""
        try:
            getattr(self.model, 'watch_%s' % (self.method_name))(
                kwargs[self.kwname], config, hookname)
        except ValueError:
            raise rest.ControllerError(400)
        else:
            return http.CREATED

    def delete(self, router, request, url, hookname=None, **kwargs):
        """Delete a web-hook watcher."""
        try:
            getattr(self.model, 'unwatch_%s' % (self.method_name))(
                hookname, kwargs[self.kwname])
        except ValueError, ve:
            return http.BAD_REQUEST, str(ve)
        else:
            return http.NO_CONTENT


class WebhookCollectionResource(object):
    """Resource for working with web-hooks."""

    def __init__(self, model, kwname, method_name):
        self.model = model
        self.kwname = kwname
        self.method_name = method_name

    def post(self, router, request, url, config, **kwargs):
        """Create a web-hook."""
        try:
            getattr(self.model, 'watch_%s' % (self.method_name))(
                kwargs[self.kwname], config)
        except ValueError, ve:
            return http.BAD_REQUEST, str(ve)
        else:
            return http.CREATED

    def get(self, router, request, url, **kwargs):
        """List all registered web-hooks."""
        watchers = {}
        for watcher in getattr(self.model, '%s_watchers' % (
                self.method_name))(kwargs[self.kwname]):
            watchers[watcher['name']] = watcher
        return watchers


class ApplicationResource(WebhookResourceMixin):
    """Application config resource."""

    def __init__(self, model):
        self.model = model

    def put(self, router, request, url, config, appname=None):
        """Update or create application config."""
        try:
            self.model.set_app(appname, config)
        except ValueError, ve:
            return http.BAD_REQUEST, str(ve)
        else:
            return http.NO_CONTENT

    def get(self, router, request, url, appname=None):
        """Read out application configuration."""
        try:
            return self.model.app(appname)
        except ValueError:
            raise rest.NoSuchResourceError()


class ApplicationCollectionResource(object):
    """Resource for listing all applications."""

    def __init__(self, model):
        self.model = model

    def get(self, router, request, url):
        """Read out applications."""
        return {'apps': list(self.model.apps())}


class ServiceHostResource(object):
    """Configuration resource for a service host pair."""

    def __init__(self, model):
        self.model = model

    def get(self, router, request, url, srvname=None, hostname=None):
        """Return host configuration."""
        try:
            return self.model.host(srvname, hostname)
        except ValueError:
            raise rest.NoSuchResourceError()

    def delete(self, router, request, url, srvname=None, hostname=None):
        """Delete a host configuration."""
        try:
            self.model.del_host(srvname, hostname)
        except ValueError:
            raise rest.NoSuchResourceError()
        else:
            return http.NO_CONTENT

    def put(self, router, request, url, config, srvname=None,
            hostname=None):
        """Update or create a host configuration."""
        try:
            self.model.set_host(srvname, hostname, config)
        except ValueError, ve:
            return http.BAD_REQUEST, str(ve)
        else:
            return http.NO_CONTENT


class ServiceHostCollectionResource(WebhookResourceMixin):
    """Collection that will list all hosts for a particular service.

    Will also include the whole config for the host.
    """

    def __init__(self, model):
        self.model = model

    def get(self, router, request, url, srvname=None):
        """Return a mapping of all known hosts."""
        hosts = {}
        for hostname in self.model.hosts(srvname):
            hosts[hostname] = self.model.host(srvname, hostname)
        return hosts


class ServiceCollectionResource(object):
    """Collection that will list all services and their hosts."""

    def __init__(self, model):
        self.model = model

    def get(self, router, request, url):
        """Return a mapping of all known services."""
        services = {}
        for srvname in self.model.services():
            services[srvname] = {
                'hosts': list(self.model.hosts(srvname))}
        return services
