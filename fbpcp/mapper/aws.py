#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from decimal import Decimal
from functools import reduce
from typing import Any, Dict, List

from fbpcp.entity.cloud_cost import CloudCost, CloudCostItem
from fbpcp.entity.cluster_instance import Cluster, ClusterStatus
from fbpcp.entity.container_instance import ContainerInstance, ContainerInstanceStatus
from fbpcp.entity.subnet import Subnet
from fbpcp.entity.vpc_instance import Vpc, VpcState


def map_ecstask_to_containerinstance(task: Dict[str, Any]) -> ContainerInstance:
    container = task["containers"][0]
    ip_v4 = (
        container["networkInterfaces"][0]["privateIpv4Address"]
        if len(container["networkInterfaces"]) > 0
        else None
    )

    status = container["lastStatus"]
    if status == "RUNNING":
        status = ContainerInstanceStatus.STARTED
    elif status == "STOPPED":
        if container.get("exitCode") == 0:
            status = ContainerInstanceStatus.COMPLETED
        else:
            status = ContainerInstanceStatus.FAILED
    else:
        status = ContainerInstanceStatus.UNKNOWN

    return ContainerInstance(task["taskArn"], ip_v4, status)


def map_esccluster_to_clusterinstance(cluster: Dict[str, Any]) -> Cluster:
    status = cluster["status"]
    if status == "ACTIVE":
        status = ClusterStatus.ACTIVE
    elif status == "INACTIVE":
        status = ClusterStatus.INACTIVE
    else:
        status = ClusterStatus.UNKNOWN

    tags = _convert_aws_tags_to_dict(cluster["tags"], "key", "value")
    return Cluster(cluster["clusterArn"], cluster["clusterName"], status, tags)


def map_ec2vpc_to_vpcinstance(vpc: Dict[str, Any]) -> Vpc:
    state = vpc["State"]
    if state == "pending":
        state = VpcState.PENDING
    elif state == "available":
        state = VpcState.AVAILABLE
    else:
        state = VpcState.UNKNOWN

    vpc_id = vpc["VpcId"]
    # some vpc instances don't have any tags
    tags = (
        _convert_aws_tags_to_dict(vpc["Tags"], "Key", "Value") if "Tags" in vpc else {}
    )

    return Vpc(vpc_id, state, tags)


def map_ec2subnet_to_subnet(subnet: Dict[str, Any]) -> Subnet:
    availability_zone = subnet["AvailabilityZone"]
    subnet_id = subnet["SubnetId"]
    tags = (
        _convert_aws_tags_to_dict(subnet["Tags"], "Key", "Value")
        if "Tags" in subnet
        else {}
    )
    return Subnet(subnet_id, availability_zone, tags)


def _convert_aws_tags_to_dict(
    tag_list: List[Dict[str, str]], tag_key: str, tag_value: str
) -> Dict[str, str]:
    return reduce(lambda x, y: {**x, **{y[tag_key]: y[tag_value]}}, tag_list, {})


def map_cecost_to_cloud_cost(cost_by_date: List[Dict[str, Any]]) -> CloudCost:
    total_cost_amount = Decimal(0)
    cost_items = {}
    for daily_result in cost_by_date:
        for group_result in daily_result.get("Groups"):
            amount = Decimal(group_result["Metrics"]["UnblendedCost"]["Amount"])
            total_cost_amount += amount
            cost_items[tuple(group_result["Keys"])] = (
                cost_items.get(tuple(group_result["Keys"]), 0) + amount
            )

    return CloudCost(
        total_cost_amount=total_cost_amount,
        details=[
            CloudCostItem(region=region, service=service, cost_amount=amount)
            for (region, service), amount in cost_items.items()
        ],
    )