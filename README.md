# Nesoi #

_Nesoi_ is a coordination and configuration manager for distributed
applications.  It allows clients to find services to communicate with,
and services to find its configuration.  It also allows clients to
register webhooks that will be notified when something changes.

_Nesoi_ has three concepts:

 * _Applications_ stores configuration for a service.
 * _Service_ holds information about instances of a service.
 * _Host_ communicate endpoints for an instance of a service.

The normal use-case is this: When an application is bootstrapped it
reads out its configuration from an app-resource.  When done, it
registers itself as a host for a service that it provides.  Clients
find endpoints for a service by inspecting `/srv/NAME`.

Applications are located under the `/app` tree.  A simple example
of creating an application configuration:

    $ curl -X PUT -d '{"name":"dm", "config":{}}' http://localhost:6553/app/dm

Each app object needs a `name` and `config` attribute.

To list all available applications, issue a GET to `/app`:

    $ curl http://localhost:6553/app
    {
      "apps": ["dm"]
    }

When your service has been bootstrapped, register the host instance
with the service using a simple command like this:

    $ curl -X PUT -d '{"endpoints":{"http":"http://localhost:5432/"}}' http://localhost:6553/srv/dm/host1
    {
      "endpoints": {
        "http": "http://localhost:5432/"
      },
      "updated_at": 1319523542
    }

`endpoints` property is required. Hosts, and apps can of course be
deleted using `DELETE`.

To make sure that your application instance gets notified about
changes to the configuration it can register itself with as a
web-hook.

First find the subscriptions resource:

    $ curl --verbose -X HEAD http://localhost:6553/app/dm
    ...
    < HTTP/1.1 200 OK
    < Date: Mon, 29 Aug 2011 10:00:50 GMT
    < Link: http://localhost:6553/app/dm/web-hooks, rel="Subscriptions"

POST your endpoint information to the Subscriptions resource:

    $ curl -X POST -d '{"name":"dm-host1", "endpoint":"http://localhost:4322/web-hooks"}' http://localhost:6553/app/dm/web-hooks
    {
      "endpoint": "http://localhost:4322/web-hooks",
      "name": "dm-host1"
    }

When the configuration for `dm` changes, a `HTTP POST` will be made
with a `JSON` object to the specified endpoint.  Endpoints have to be
explicitly removed using `DELETE`.  Make a note of the `Location`
header when registering the web-hook.

# Running Nesoi #

Requirements:

 - Twisted (core and web)
 - txgossip

_Nesoi_ is installed as a twistd plugin, so you'll have to start it
using the `twistd` command-line tool.  See `twistd --help` for more
information on generic options and such.

The `nesoi` service accepts the following options:

 - `--listen-address IP` listen address (*required*)
 - `--listen-port PORT` listen port (*required*)
 - `--data-file FILE` where to store config data (*required*)
 - `--seed IP:PORT` another nesoi instance to comminicate with

Example:

    twistd nesoi --listen-address 10.2.2.2 --listen-port 6553 --seed 10.2.2.1:6553

# Implementation #

_Nesoi_ is in its foundation a distributed key-value store.  Each
resource pretty much maps to a key-value pair (except for the
collection resources that maps to many key-value pairs of course).

_Nesoi_ is in itself distributed.  All _Nesoi_ instances communicate
using a gossip protocol (using `txgossip`).  Instances gossip with
each other about state changes to their local key-value stores.
Eventually all data has propagated to all nodes in the system.

Each value in the key-value store is annotated with a timestamp.  This
timestamp is used to resolve conflicts.  A newer value always wins.
As an effect of this, _Nesoi_ assumes that all nodes running _Nesoi_
instances have synchronized clocks.

Each _Nesoi_ cluster has a leader.  This leader is responsible for
sending out the watcher notifications.

# API #

The API is quite simple.

## Application Configurations

Application configurations live under `/app`.  You can retreive a
configuration using `GET /app/<appname>`.  To update a create or
update a configuration use `PUT /app/<appname>`.

The data pushed to a `/app/<appname>` must be a JSON object holding a
`config` property.

To get a list of all application configurations do a `GET /app`.

## Services and Hosts

Instances of _applications_ register themselves as a service running
on a host.  They do this but issuing a `PUT` to `/srv/<appname>/<host>`.

The data pushed to a `/srv/<appname>/<host>` must be a JSON object
holding a `endpoints` property.

Services can update their state by issuing further `PUT`s.  Also, when
an instance shuts down it **SHOULD** delete it itself from the
registry using a `DELETE` on `/srv/<appname>/<host>`.

## Webhooks (change notifications) ##

_Nesoi_ implements webhooks [1] to allow clients to monitor changes to
a resource.  See [2] for more information.  The `Notification-Type` is
currently ignored.  Hooks will be informed about all changes.

When registering a webhook, `POST` a `json` object with the following
attributes to the subscription resource:

 * A client name (`name`).  Used to identify the endpoint from a
   service point of view.  Normally constructed from hostname and
   service name.
 * An endpoint (`endpoint`).  URI where notification should be posted.

When something happens in _Nesoi_ that triggers a notification, a
`HTTP` `POST` will be sent to the registered endpoint.

The payload of the body is a `json` object with the following
attributes:

 * Name of webhook (`name`)
 * URI to the resource that was changed (`uri`)

Web-hooks can be attached to application configurations
(`/app/<appname>/web-hooks`) and service (`/srv/<appname>/web-hooks`).

An example:

    {
      "name": "node1-test",
      "uri": "/app/test"
    }

 [1] http://wiki.webhooks.org
 [2] http://wiki.webhooks.org/w/page/13385128/RESTful%20WebHooks

# Use Cases #

## Service Configuration ##

To ease configuration management, Nesoi can help with distributing
configuration data to all instances of a service.

The configuration manager (a person, or a piece of software) creates a
`/app/NAME` resource using the REST interface.  When the configuration
is changed, he or she simply updates the resource with the new config.

Service instances are configured with information about where to reach
Nesoi.  When starting up, the instance fetches the `/app/NAME`
resource.  It also installes a _watch_ on `/app/NAME` allowing the
service to be informed when the configuration is changed.

## Service Announcement ##

When a service instance has found its configuratio and initialized
itself it should announce its presence to the rest of the distributed
system.  It does this by create (or updating) a service information
resource at '/srv/APP/HOST'.  The resource holds information about
where the service endpoints (communication endspoints) are.  Other
information may also be included.  

The service instance resource contains metadata about when the data
was last updated.  This information can be used to communicate some
kind of _status_ about the service instance.  For example, a protocol
can be put in place that the service instance should update its
resource once every minute.  If the resource has not been updated for
two minutes, it should be considered dead.

If a leader among all service instances has to communicated to users
of the service, this can be done by setting a `master` field to `true`
in the resource.  When a instance looses an election, it should right
away update its resource with `master` set to `false`.  If a client
finds several service instances with that states that they are master,
the one with the latest "updated_at" time should be trusted.

When a service instance is removed from the system, the service
instance resource should be removed with it.

## Service Discovery ##

When a client wants to talk to a service it fetches a representation
of the `/srv/NAME` resource.  The resource will enumerate all known
service instances and their communication endpoints.

A client may also register a _watch_ on `/srv/NAME` so that it will
get notified about changes to service instances.

