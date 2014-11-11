# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Tests for linking containers.
"""
from twisted.trial.unittest import TestCase

from flocker.node._docker import BASE_NAMESPACE, Unit

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
LOGSTASH_INTERNAL_PORT = 5000

LOGSTASH_APPLICATION = u"logstash"
LOGSTASH_IMAGE = u"LOGSTASH"
LOGSTASH_VOLUME_MOUNTPOINT = u'/var/lib/LOGSTASH/data'

LOGSTASH_UNIT = Unit(
    name=LOGSTASH_APPLICATION,
    container_name=BASE_NAMESPACE + LOGSTASH_APPLICATION,
    activation_state=u'active',
    container_image=LOGSTASH_IMAGE + u':latest',
    ports=frozenset([
        PortMap(internal_port=LOGSTASH_INTERNAL_PORT,
                external_port=LOGSTASH_INTERNAL_PORT),
        ]),
    volumes=frozenset([
        Volume(node_path=FilePath(b'/tmp'),
               container_path=FilePath(LOGSTASH_VOLUME_MOUNTPOINT)),
        ]),
)

KIBANA_INTERNAL_PORT = 8080
KIBANA_EXTERNAL_PORT = 80

KIBANA_APPLICATION = u"KIBANA-volume-example"
KIBANA_IMAGE = u"KIBANA"
KIBANA_VOLUME_MOUNTPOINT = u'/var/lib/KIBANA/data'

KIBANA_UNIT = Unit(
    name=KIBANA_APPLICATION,
    container_name=BASE_NAMESPACE + KIBANA_APPLICATION,
    activation_state=u'active',
    container_image=KIBANA_IMAGE + u':latest',
    ports=frozenset([
        PortMap(internal_port=KIBANA_INTERNAL_PORT,
                external_port=KIBANA_EXTERNAL_PORT),
        ]),
    volumes=frozenset([
        Volume(node_path=FilePath(b'/tmp'),
               container_path=FilePath(KIBANA_VOLUME_MOUNTPOINT)),
        ]),
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

        }

        elk_deployment = {
            u"version": 1,
            u"nodes": {
                self.node_1: [ELASTICSEARCH_APPLICATION, LOGSTASH_APPLICATION,
                    KIBANA_APPLICATION],
                self.node_2: [],
            },
        }

        getting_nodes = get_nodes(num_nodes=2)

        def deploy(node_ips):
            # flocker-deploy elk-deployment.yml elk-application.yml
            # check that there is nothing in kibana
            # telnet to add some sample data to Logstash
            # check that there is some data in kibana
            # elk-deployment-moved.yml
            # flocker-deploy elk-deployment-moved.yml elk-application.yml
            # check that it is on the new host
            # check that there is some data in kibana
            pass

        getting_nodes.addCallback(deploy)
        return getting_nodes
