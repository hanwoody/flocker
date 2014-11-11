# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Tests for linking containers.
"""
from twisted.trial.unittest import TestCase

from flocker.node._docker import BASE_NAMESPACE, Unit

from .testtools import (assert_expected_deployment, flocker_deploy, get_nodes,
                        require_flocker_cli)


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
