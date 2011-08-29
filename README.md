# Nesoi #

`Nesoi` is a coordination and configuration manager for distributed
applications.  It allows clients to find services to communicate with,
and services to find configuration.  It also allows clients to
register webhooks that will be notified when something changes.

# Implementation #

`Nesoi` is in its foundation a distributed key-value store.  Each
resource pretty much maps to a key-value pair (except for the
collection resources that maps to many key-value pairs of course).

`Nesoi` is in itself distributed.  All `Nesoi` instances communicate
using a gossip protocol (`txgossip` - google it).  Instances gossip
with each other about state changes to their local key-value stores.
Eventually all data has propagated to all nodes in the system.

Each value in the key-value store is annotated with a timestamp.  This
timestamp is used to resolve conflicts.  A newer value always wins.
As an effect of this, `Nesoi` assumes that all nodes running `Nesoi`
instances have synchronized clocks.

Each _Nesoi_ cluster has a leader.  This leader is responsible for
sending out the watcher notifications.

# API #

...

## Webhooks (change notifications) ##

_Nesoi_ implements webhooks [1] to allow clients to minitor changes to
a resource.  See [2] for more information.  The `Notification-Type` is
currently ignored.  Hooks will be informed about all changes.

When registering a webhook, `POST` the a `json` object with the
following attributes to the subscription resource:

 * A client name (`name`).  Used to identify the endpoint from a
   service point of view.  Normally constructed from hostname and
   service name.
 * An endpoint (`endpoint').  URI where notification should be posted.

When something happens in _Nesoi_ that triggers a notification, a
`HTTP` `POST` will be sent to the registered endpoint.  

The payload of the body is a `json` object with the following
attributes:

 * Name of webhook (`name`)
 * Change type (`what`)
 * URI to the resource that was changed (`uri`)

An example:

    {
      "name": "node1-test",
      "what": "updated",
      "uri": "http://host/app/test"
    }

 [1] http://wiki.webhooks.org
 [2] http://wiki.webhooks.org/w/page/13385128/RESTful%20WebHooks

## Webhooks ##

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

