import yaml
from libcloud.compute.providers import get_driver, Provider
from libcloud.compute.base import NodeImage

aws_config = yaml.safe_load(open("aws_config.yml"))

driver = get_driver(Provider.EC2)(
    key=aws_config['access_key'],
    secret=aws_config['secret_access_token'],
    region=aws_config['region'])


def get_size(size_name):
    """
    Return a ``NodeSize`` corresponding to the name of size.
    """
    try:
        return [s for s in driver.list_sizes() if s.id == size_name][0]
    except IndexError:
        raise ValueError("Unknown EC2 size.", size_name)


def create_node(name, base_ami,
                username,  # hack for wait-for-ssh
                userdata=None,
                size="t1.micro", disk_size=8,
                private_key_file=aws_config['private_key_file'],
                keyname=aws_config['keyname']):
    """
    :param str name: The name of the node.
    :param str base_ami: The name of the ami to use.
    :param bytes userdata: User data to pass to the instance.
    :param bytes size: The name of the size to use.
    :param int disk_size: The size of disk to allocate.
    """
    node = driver.create_node(
        name=name,
        image=NodeImage(id=base_ami, name=None, driver=driver),
        size=get_size(size),

        ex_keyname=keyname,
        ex_security_groups=['acceptance'],
        ex_blockdevicemappings=[
            {"DeviceName": "/dev/sda1",
             "Ebs": {"VolumeSize": disk_size,
                     "DeleteOnTermination": True,
                     "VolumeType": "gp2"}}
        ],
        # Deploy stuff
        ex_userdata=userdata,
    )
    return node
