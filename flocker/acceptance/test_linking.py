# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Tests for linking containers.
"""
from twisted.python.filepath import FilePath
from twisted.trial.unittest import TestCase

from flocker.node._docker import BASE_NAMESPACE, PortMap, Unit, Volume

from .testtools import (assert_expected_deployment, flocker_deploy, get_nodes,
                        require_flocker_cli)

ELASTICSEARCH_INTERNAL_PORT = 9200
ELASTICSEARCH_EXTERNAL_PORT = 9200

ELASTICSEARCH_APPLICATION = u"elasticsearch"
ELASTICSEARCH_IMAGE = u"clusterhq/elasticsearch"
ELASTICSEARCH_VOLUME_MOUNTPOINT = u'/var/lib/elasticsearch'

ELASTICSEARCH_UNIT = Unit(
    name=ELASTICSEARCH_APPLICATION,
    container_name=BASE_NAMESPACE + ELASTICSEARCH_APPLICATION,
    activation_state=u'active',
    container_image=ELASTICSEARCH_IMAGE + u':latest',
    ports=frozenset([
        PortMap(internal_port=ELASTICSEARCH_INTERNAL_PORT,
                external_port=ELASTICSEARCH_EXTERNAL_PORT),
        ]),
    volumes=frozenset([
        Volume(node_path=FilePath(b'/tmp'),
               container_path=FilePath(ELASTICSEARCH_VOLUME_MOUNTPOINT)),
        ]),
)

LOGSTASH_INTERNAL_PORT = 5000
LOGSTASH_EXTERNAL_PORT = 5000

LOGSTASH_LOCAL_PORT = 9200
LOGSTASH_REMOTE_PORT = 9200

LOGSTASH_APPLICATION = u"logstash"
LOGSTASH_IMAGE = u"clusterhq/logstash"

LOGSTASH_UNIT = Unit(
    name=LOGSTASH_APPLICATION,
    container_name=BASE_NAMESPACE + LOGSTASH_APPLICATION,
    activation_state=u'active',
    container_image=LOGSTASH_IMAGE + u':latest',
    ports=frozenset([
        PortMap(internal_port=LOGSTASH_INTERNAL_PORT,
                external_port=LOGSTASH_INTERNAL_PORT),
        ]),
    volumes=frozenset([]),
)

KIBANA_INTERNAL_PORT = 8080
KIBANA_EXTERNAL_PORT = 80

KIBANA_APPLICATION = u"kibana"
KIBANA_IMAGE = u"clusterhq/kibana"

KIBANA_UNIT = Unit(
    name=KIBANA_APPLICATION,
    container_name=BASE_NAMESPACE + KIBANA_APPLICATION,
    activation_state=u'active',
    container_image=KIBANA_IMAGE + u':latest',
    ports=frozenset([
        PortMap(internal_port=KIBANA_INTERNAL_PORT,
                external_port=KIBANA_EXTERNAL_PORT),
        ]),
    volumes=frozenset([]),
)

class LinkingTests(TestCase):
    """
    Tests for linking containers.

    Similar to:
    http://doc-dev.clusterhq.com/gettingstarted/examples/linking.html

    # TODO Link to this file from linking.rst
    """
    @require_flocker_cli
    def test_linking(self):
        """
        Containers can be linked to using network ports.
        """
        elk_application = {
            u"version": 1,
            u"applications": {
                ELASTICSEARCH_APPLICATION: {
                    u"image": ELASTICSEARCH_IMAGE,
                    u"ports": [{
                        u"internal": ELASTICSEARCH_INTERNAL_PORT,
                        u"external": ELASTICSEARCH_EXTERNAL_PORT,
                    }],
                    u"volume": {
                        u"mountpoint": ELASTICSEARCH_VOLUME_MOUNTPOINT,
                    },
                },
                LOGSTASH_APPLICATION: {
                    u"image": LOGSTASH_IMAGE,
                    u"ports": [{
                        u"internal": LOGSTASH_INTERNAL_PORT,
                        u"external": LOGSTASH_EXTERNAL_PORT,
                    }],
                    u"links": [{
                        u"local_port": LOGSTASH_LOCAL_PORT,
                        u"remote_port": LOGSTASH_REMOTE_PORT,
                        u"alias": u"es",
                    }],
                },
                KIBANA_APPLICATION: {
                    u"image": ELASTICSEARCH_IMAGE,
                    u"ports": [{
                        u"internal": ELASTICSEARCH_INTERNAL_PORT,
                        u"external": ELASTICSEARCH_EXTERNAL_PORT,
                    }],
                },
            },
        }

        getting_nodes = get_nodes(num_nodes=2)

        def deploy(node_ips):
            node_1, node_2 = node_ips
            elk_deployment = {
                u"version": 1,
                u"nodes": {
                    node_1: [ELASTICSEARCH_APPLICATION, LOGSTASH_APPLICATION,
                        KIBANA_APPLICATION],
                    node_2: [],
                },
            }

            flocker_deploy(self, elk_deployment, elk_application)
            # check that there is nothing in kibana
            # telnet to add some sample data to Logstash
            # check that there is some data in kibana
            # elk-deployment-moved.yml
            # flocker-deploy elk-deployment-moved.yml elk-application.yml
            # check that it is on the new host
            # check that there is some data in kibana

        getting_nodes.addCallback(deploy)
        return getting_nodes
