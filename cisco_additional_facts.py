#!/usr/bin/python

# Copyright: (c) 2020, Your Name <YourName@example.org>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cisco_additional_facts

short_description: This is my Cisco additional facts module

version_added: "1.0.0"

description: This module is intended to gather more detailed facts about Cisco devices, such as routing tables, MAC address tables, VRFs, and more.

options:
  fact_type:
    type: str
    description:
    - Specify the type of fact(s) to gather (default is all).
    - Supported types: all, interfaces, inventory, license, mac_address_table, routes, route_neighbors, vrfs
    default: all

author:
- Tommy McNeela (@tmcneela5c)
'''

EXAMPLES = r'''
- name: Return ansible_facts
  my_namespace.my_collection.my_test_facts:
'''

RETURN = r'''
# These are examples of possible return values, and in general should use other names for return values.
ansible_facts:
  description: Facts to add to ansible_facts.
  returned: always
  type: dict
  contains:
    ansible_net_interfaces:
      description: Gather the network interface details.
      type: dict
      returned: when this host is a Cisco appliance
      sample:
        Ethernet2/48:
          mtu: 9216
          ipv4:
          - subnet: "30"
            address: 192.168.1.1
          type: 1000/10000 Ethernet
          duplex: full
          bandwidth: 1000000
          mediatype: 1G
          macaddress: aa:bb:cc:dd:ee:ff
          operstatus: up
          description: VPC Keepalive Link
          lineprotocol: up
    ansible_net_license:
      description: Gather the license details.
      type: str
      returned: when this host is a Cisco appliance
      sample: ""
    ansible_net_inventory:
      description: Gather hardware inventory.
      type: list
      elements: dict
      returned: when this host is a Cisco appliance
      sample:
      - name: Chassis
        description: Cisco ASR1002-HX Chassis
        pid: ASR1000X-AC-750W
        vid: V01
        sn: POG20447X81
    ansible_net_vrfs:
      description: Gather VRF facts including IP routes.
      type: list
      elements: dict
      returned: when this host is a Cisco router and has defined VRFs
      sample:
      - name: Mgmt-intf
        interfaces:
        - GigabitEthernet0
        routes:
        - route: 0.0.0.0/0
          kind: Static
          next_hop:
            address: 172.27.0.1
            interface: null
        - route: 172.27.0.0/24
          kind: Connected
          next_hop:
            address: null
            interface: GigabitEthernet0
    ansible_net_routes:
      description: Gather IP routing information facts.
      type: list
      elements: dict
      returned: when this host is a Cisco router
      sample:
      - route: 63.141.43.128/25
        kind: OSPF
        next_hop:
          address: 63.141.43.128/25
          interface: TenGigabitEthernet0/1/0
      - route: 1.0.206.0/24
        kind: BGP
        next_hop:
          address: 38.142.17.145
          interface: null
    ansible_net_route_neighbors:
      description: Gather facts about hosts this router is sharing routes with.
      type: list
      elements: dict
      returned: when this host is a Cisco router
      sample:
      - neighbor_address: 38.142.17.145
        routing_protocol: BGP
        neighbor_as_num: 174
      - neighbor_address: 63.141.40.5
        routing_protocol: OSPF
        neighbor_id: 172.31.1.2
        connection_state: FULL/-
        connected_interface: TenGigabitEthernet0/1/2
        priority: 0
    ansible_net_mac_address_table:
      description: Gather facts about the MAC addresses this switch knows about.
      type: list
      elements: dict
      returned: when this host is a Cisco switch
      sample:
      - interface: Po10
        mac_addresses:
        - mac_address: a2bf.0000.0002
          vlan_id: 100
      - interface: Po11
        mac_addresses:
        - mac_address: a2:bf:00:00:00:03
          vlan_id: 100
        - mac_address: a2:bf:00:00:00:05
          vlan_id: 110
'''

# from ansible.module_utils._text import to_native, to_text
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.cisco.ios.plugins.module_utils.network.ios.ios import run_commands
import ipaddress
import logging
from typing import Dict, List

ROUTE_TYPES = ('BGP', 'connected', 'OSPF', 'static')


def format_mac_address(mac_address: str) -> str:
    """
    Format a MAC address of arbitrary format into colon-separated standard format.
    @param mac_address: original MAC address to format
    @return: formatted MAC address
    """
    try:
        # remove delimiters and convert to lowercase
        mac = mac_address.replace('.', '').replace(':', '').replace('-', '').lower()
        # remove whitespaces
        mac = ''.join(mac.split())
        # MAC address must be alphanumeric and length 12
        assert len(mac) == 12
        assert mac.isalnum()
        mac = ':'.join(mac[i:i + 2] for i in range(0, 12, 2))
        return mac
    except:
        return mac_address


def get_device_type(module: AnsibleModule) -> str:
    """
    Get the type of device (operating system).
    @param module: ansible module object
    @return: device type (operating system)
    """
    # TODO: show context, get interfaces for NX-OS
    cmd = 'show inventory | include Chassis'
    # rc, stdout, stderr = module.run_command(cmd, use_unsafe_shell=True)
    stdout = run_commands(module, ['term len 0', cmd])
    l1 = stdout[1].splitlines[0]
    device_type = l1.split('"')[-2].strip()
    return device_type


def _get_routes_ios(module, route_type: str, vrf: str = None) -> List[Dict]:
    """
    Get IP route table from IOS device.
    @param module: ansible module object
    @param route_type: type of route (i.e. BGP, OSPF, etc)
    @param vrf: optional VRF name
    @return: list of routes
    """
    routes = []
    if vrf:
        cmd = f'show ip route vrf {vrf} secondary {route_type.lower()}'
    else:
        cmd = f'show ip route secondary {route_type.lower()}'
    # rc, stdout, stderr = module.run_command(cmd, use_unsafe_shell=True)
    # lines = stdout.splitlines()
    stdout = run_commands(module, ['term len 0', cmd])
    lines = stdout[1].splitlines()
    if route_type.lower() != 'ospf':
        first_letter = route_type[0].upper()
        for line in lines:
            if line.startswith(f'{first_letter} ') or line.startswith(f'{first_letter}*'):
                splitter = line.split()
                # make sure we're only getting private routes and directly connected routes (otherwise we'll get a massive BGP table from edge routers)
                addr_obj = ipaddress.IPv4Address(splitter[1].split('/')[0])
                if addr_obj.is_private or splitter[1] == '0.0.0.0/0' or route_type.lower() == 'connected':
                    route_details = {'route': splitter[1],
                                     'kind': route_type.capitalize() if route_type.lower() not in ['bgp', 'eigrp',
                                                                                                   'isis'] else route_type.upper()}
                    if 'directly connected' in line:
                        route_details['next_hop'] = [{'address': None, 'interface': splitter[-1]}]
                    elif ' via ' in line:
                        route_details['next_hop'] = [{'address': splitter[4].replace(',', ''), 'interface': None}]
                    routes.append(route_details)
    else:
        first_line = True
        for line in lines:
            if line.startswith('O ') or line.startswith('O*'):
                splitter = line.split()
                if len(splitter) < 3:
                    first_line = False
                    route = splitter[1]
                else:
                    first_line = True
                    r = 1
                    n = 4
                    route = splitter[r]
                    next_hop_address = splitter[n]
                    while route in ['E1', 'E2', 'IA', 'N1', 'N2']:
                        r += 1
                        n += 1
                        route = splitter[r]
                        next_hop_address = splitter[n]
                    addr_obj = ipaddress.IPv4Address(route.split('/')[0])
                    if addr_obj.is_private or route == '0.0.0.0/0':
                        routes.append({'route': route, 'kind': 'OSPF',
                                       'next_hop': [{'address': next_hop_address.replace(',', ''),
                                                     'interface': splitter[-1]}]})
            elif not first_line:
                splitter = line.split()
                # make sure this is a private route
                addr_obj = ipaddress.IPv4Address(route.split('/')[0])
                if addr_obj.is_private or route == '0.0.0.0/0':
                    routes.append({'route': route, 'kind': 'OSPF',
                                   'next_hop': [{'address': splitter[2].replace(',', ''), 'interface': splitter[-1]}]})
    return routes


def _get_routes_nxos(module: AnsibleModule, route_type: str, vrf: str = None) -> List[Dict]:
    """
    Get IP route table from NX-OS device.
    @param module: ansible module object
    @param route_type: type of route (i.e. BGP, OSPF, etc)
    @param vrf: optional VRF name
    @return: list of routes
    """
    routes = []
    route_type_aliases = {'connected': 'direct'}
    rt = route_type
    if route_type in route_type_aliases:
        rt = route_type_aliases[route_type]
    if vrf:
        cmd = f'show ip route vrf {vrf} {rt.lower()} | begin ubest'
    else:
        cmd = f'show ip route {rt.lower()} | begin ubest'
    stdout = run_commands(module, ['term len 0', cmd])
    lines = stdout[1].splitlines()
    next_hops = []
    route_obj = None
    for line in lines:
        if 'ubest' in line:
            if route_obj:
                route_obj['next_hop'] = next_hops
                routes.append(route_obj)
            next_hops = []
            route = line.split()[0].replace(',', '')
            addr_obj = ipaddress.IPv4Address(route.split('/')[0])
            if addr_obj.is_private or route == '0.0.0.0/0' or route_type.lower() == 'connected':
                route_obj = {'route': route,
                             'kind': route_type.capitalize() if route_type.lower() not in ['bgp', 'eigrp', 'isis',
                                                                                           'ospf'] else route_type.upper()}
        elif 'via' in line:
            if route_obj:
                splitter = line.replace(',', '').split()
                next_hop_address = splitter[1].split('%')[0]
                next_hop_interface = None
                try:
                    ipaddress.IPv4Address(next_hop_address)
                    next_hop_interface = splitter[
                        2] if route_type.lower() == 'connected' or route_type.lower() == 'ospf' else None
                except:
                    next_hop_interface = next_hop_address
                    next_hop_address = None
                next_hops.append({'address': next_hop_address, 'interface': next_hop_interface})
    if next_hops:
        route_obj['next_hop'] = next_hops
        routes.append(route_obj)
    return routes


def get_routes(module: AnsibleModule, operating_system: str, route_type: str, vrf: str = None) -> List[Dict]:
    """
    Get the route table.
    @param module: ansible module object
    @param operating_system: operating system to pull from
    @param route_type: type of route (i.e. BGP, OSPF, etc)
    @param vrf: optional VRF name
    @return: list of routes
    """
    routes = []
    if operating_system.upper() == 'IOS':
        routes = _get_routes_ios(module, route_type, vrf)
    elif operating_system.upper() == 'NXOS':
        routes = _get_routes_nxos(module, route_type, vrf)
    else:
        logging.error(f'Unknown operating system')
    return routes


def get_vrfs(module: AnsibleModule, operating_system: str) -> List[Dict]:
    """
    Get the list of VRFs and their routes and interfaces defined on this device.
    @param module: ansible module object
    @param operating_system: operating system to pull from
    @return: list of VRFs and their routes and interfaces
    """
    vrfs = []
    cmd = 'show vrf'
    # rc, stdout, stderr = module.run_command(cmd, use_unsafe_shell=True)
    stdout = run_commands(module, ['term len 0', cmd])
    lines = stdout[1].splitlines()
    if len(lines) > 1:
        for line in lines[1:]:
            splitter = line.split()
            vrf_name = splitter[0]
            vrf_interfaces = None
            if not splitter[-1].startswith('ipv'):
                vrf_interfaces = splitter[-1].split(',')
                if vrf_interfaces[0] == '--':
                    vrf_interfaces = None
            vrf_details = {'name': vrf_name, 'interfaces': vrf_interfaces}
            routes = []
            for route_type in ROUTE_TYPES:
                try:
                    routes.extend(get_routes(module, operating_system, route_type, vrf_name))
                except Exception as e:
                    logging.warning(e)
            vrf_details['routes'] = routes
            vrfs.append(vrf_details)
    return vrfs


def get_route_neighbors(module: AnsibleModule) -> List[Dict]:
    """
    Get the list of neighbors we are sharing routes with.
    @param module: ansible module object
    @return: list of route neighbors
    """
    route_neighbors = []
    # get OSPF neighbors
    cmd = 'show ip ospf neighbor | begin Neighbor'
    # rc, stdout, stderr = module.run_command(cmd, use_unsafe_shell=True)
    # lines = stdout.splitlines()[2:]
    stdout = run_commands(module, ['term len 0', cmd])
    lines = stdout[1].splitlines()[1:]
    for line in lines:
        line = line.replace(' -', '')
        splitter = line.split()
        neighbor_id, priority, connection_state, dead_time, neighbor_address, connected_interface = splitter
        route_neighbors.append(
            {'neighbor_address': neighbor_address, 'routing_protocol': 'OSPF', 'neighbor_id': neighbor_id,
             'connection_state': connection_state, 'connected_interface': connected_interface, 'priority': priority})
    # get BGP neighbors
    cmd = 'show ip bgp summary | begin Neighbor'
    # rc, stdout, stderr = module.run_command(cmd, use_unsafe_shell=True)
    # lines = stdout.splitlines()[2:]
    stdout = run_commands(module, ['term len 0', cmd])
    lines = stdout[1].splitlines()[1:]
    # lines = stdout[2:]
    for line in lines:
        splitter = line.split()
        try:
            ipaddress.IPv4Address(splitter[0])
        except:
            continue
        route_neighbors.append(
            {'neighbor_address': splitter[0], 'routing_protocol': 'BGP', 'neighbor_as_num': splitter[2]})
    return route_neighbors


def get_mac_address_table(module: AnsibleModule) -> List[Dict]:
    """
    Get the MAC address table from this switch.
    @param module: ansible module object
    @return:
    """
    mac_address_table = {}
    cmd = 'show mac address-table dynamic'
    # rc, stdout, stderr = module.run_command(cmd, use_unsafe_shell=True)
    # lines = stdout.splitlines()
    stdout = run_commands(module, ['term len 0', cmd], check_rc=False)
    lines = stdout[1].splitlines()
    for line in lines:
        if line.startswith('* '):
            splitter = line.split()
            vlan = splitter[1]
            mac_address = format_mac_address(splitter[2])
            interface = splitter[7]
            if interface not in mac_address_table:
                mac_address_table[interface] = []
            mac_address_table[interface].append({'mac_address': mac_address, 'vlan_id': vlan})
    mac_address_table_list = []
    for k, v in mac_address_table.items():
        mac_address_table_list.append({'interface': k, 'mac_addresses': v})
    return mac_address_table_list if len(mac_address_table_list) > 0 else None


def get_inventory(module: AnsibleModule) -> List[Dict]:
    """
    Get the hardware inventory from this device.
    @param module: ansible module object
    @return: list of hardware inventory
    """
    inventory = []
    stdout = run_commands(module, ['term len 0', 'show inventory'])
    lines = stdout[1].splitlines()
    for line in lines:
        if line.startswith('NAME:'):
            splitter = line.split('"')
            inv_name = splitter[1]
            inv_descr = splitter[3]
        elif line.startswith('PID:'):
            splitter = line.replace(',', '').split()
            inv_pid = splitter[1]
            inv_vid = None
            inv_sn = None
            if len(splitter) > 4:
                inv_vid = splitter[3]
                inv_sn = splitter[5]
            inventory.append({'name': inv_name, 'description': inv_descr, 'pid': inv_pid, 'vid': inv_vid, 'sn': inv_sn})
    return inventory


def _get_interfaces_nxos(module: AnsibleModule) -> Dict[str, Dict]:
    """
    Get details of interfaces assigned to this host.
    @param module: ansible module object
    @return: dictionary of interfaces found on this host
    """
    interfaces = {}
    stdout = run_commands(module, ['term len 0', 'show ip interf br oper vrf all'])
    lines = stdout[1].splitlines()
    for line in lines:
        splitter = line.split()
        if len(splitter) == 3:
            iface_name = splitter[0]
            iface_status = splitter[-1].split('/')
            iface_lineprotocol = iface_status[0].split('-')[-1]
            iface_operstatus = iface_status[1].split('-')[-1]
            stdout2 = run_commands(module, ['term len 0', f'show interf {iface_name}'])
            lines2 = stdout2[1].splitlines()
            iface_name = lines2[0].split()[0]
            iface_mtu = None
            iface_subnet_mask = None
            iface_ip_address = None
            iface_type = None
            iface_duplex = None
            iface_bandwidth = None
            iface_mediatype = None
            iface_mac_address = None
            iface_description = None
            for line2 in lines2[1:]:
                if 'Hardware:' in line2:
                    splitter2 = line2.split(',')
                    iface_type = splitter2[0].split(':')[1].strip()
                    try:
                        iface_mac_address = format_mac_address(splitter2[1].split()[-1].replace(')', ''))
                    except:
                        pass
                elif 'Hardware is' in line2:
                    splitter2 = line2.split(',')
                    iface_type = ''.join(splitter2[0].split()[2:])
                    try:
                        iface_mac_address = format_mac_address(splitter2[1].split()[-1])
                    except:
                        pass
                elif 'Description:' in line2:
                    iface_description = line2.split(':')[1].strip()
                elif 'Internet Address' in line2:
                    ip_details = line2.split()[-1].split('/')
                    iface_ip_address, iface_subnet_mask = ip_details
                elif 'MTU' in line2:
                    splitter2 = line2.split(',')
                    iface_mtu = splitter2[0].split()[1]
                    iface_bandwidth = splitter2[1].split()[1]
                elif 'duplex' in line2:
                    splitter2 = line2.split(',')
                    iface_duplex = 'half' if 'full' not in splitter2[0] else 'full'
                    iface_mediatype = splitter2[-1].replace('media type is', '').strip()
            interfaces[iface_name] = {'mtu': int(iface_mtu),
                                      'ipv4': [{'subnet': str(iface_subnet_mask), 'address': iface_ip_address}],
                                      'type': iface_type, 'duplex': iface_duplex, 'bandwidth': int(iface_bandwidth),
                                      'mediatype': iface_mediatype, 'macaddress': iface_mac_address,
                                      'operstatus': iface_operstatus, 'description': iface_description,
                                      'lineprotocol': iface_lineprotocol}
    return interfaces


def get_interfaces(module: AnsibleModule, operating_system: str) -> Dict[str, Dict]:
    """
    Get details of interfaces assigned to this host.
    @param module: ansible module object
    @param operating_system: operating system running on this host (i.e. IOS, NX-OS)
    @return: dictionary of interfaces found on this host
    """
    interfaces = None
    if operating_system.upper() == 'NXOS':
        interfaces = _get_interfaces_nxos(module)
    return interfaces


def _get_license_ios(module: AnsibleModule) -> str:
    """
    Get license information.
    @param module: ansible module object
    @return: license information
    """
    stdout = run_commands(module, ['term len 0', 'show license all'])
    software_license = stdout[1]
    return software_license


def _get_license_nxos(module: AnsibleModule) -> str:
    """
    Get license information.
    @param module: ansible module object
    @return: license information
    """
    stdout = run_commands(module, ['term len 0', 'show license'])
    software_license = stdout[1]
    return software_license


def get_license(module: AnsibleModule, operating_system: str) -> str:
    """
    Get license information.
    @param module: ansible module object
    @param operating_system: operating system running on this device (i.e. IOS, NX-OS, etc)
    @return: license information
    """
    software_license = None
    if operating_system.upper() == 'IOS':
        software_license = _get_license_ios(module)
    elif operating_system.upper() == 'NXOS':
        software_license = _get_license_nxos(module)
    else:
        logging.error(f'Unknown operating system')
    return software_license


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(fact_type=dict(type='str', required=False))

    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        ansible_facts=dict(),
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    params = module.params
    if 'fact_type' not in params:
        params['fact_type'] = 'all'
    elif params.get('fact_type') not in ('all', 'interfaces', 'inventory', 'license', 'mac_address_table', 'routes',
                                         'route_neighbors', 'vrfs'):
        logging.warning(f'Error, invalid fact type requested: {params["fact_type"]}')
        params['fact_type'] = 'all'

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    # manipulate or modify the state as needed (this is going to be the
    # part where your module will do what it needs to do)
    # rc, stdout, stderr = module.run_command('term len 0', use_unsafe_shell=True)
    # rc, stdout, stderr = module.run_command('show version', use_unsafe_shell=True)
    # determine operating system (default to IOS)
    operating_system = 'IOS'
    output = run_commands(module, ['term len 0', 'show version'])
    lines = output[1].splitlines()
    if 'IOS' in lines[0]:
        operating_system = 'IOS'
    elif 'NX-OS' in lines[0] or 'Nexus' in lines[0]:
        operating_system = 'NXOS'
    # start gathering results
    result['ansible_facts'] = {
        'ansible_net_inventory': None,
        'ansible_net_license': None,
        'ansible_net_mac_address_table': None,
        'ansible_net_routes': None,
        'ansible_net_route_neighbors': None,
        'ansible_net_vrfs': None
    }
    fact_type = params['fact_type']
    if fact_type == 'interfaces' or (fact_type == 'all' and operating_system == 'NXOS'):
        result['ansible_facts']['ansible_net_interfaces'] = get_interfaces(module, operating_system)
    if fact_type == 'inventory' or fact_type == 'all':
        result['ansible_facts']['ansible_net_inventory'] = get_inventory(module)
    if fact_type == 'license' or fact_type == 'all':
        result['ansible_facts']['ansible_net_license'] = get_license(module, operating_system)
    if fact_type == 'mac_address_table' or fact_type == 'all':
        # get MAC address table
        mac_address_table = None
        try:
            mac_address_table = get_mac_address_table(module)
        except Exception as e:
            logging.warning(e)
        result['ansible_facts']['ansible_net_mac_address_table'] = mac_address_table
    if fact_type == 'routes' or fact_type == 'all':
        # get L3 routes
        routes = []
        for route_type in ROUTE_TYPES:
            try:
                routes.extend(get_routes(module, operating_system, route_type))
            except Exception as e:
                logging.warning(e)
        if len(routes) == 0:
            routes = None
        result['ansible_facts']['ansible_net_routes'] = routes
    if fact_type == 'route_neighbors' or fact_type == 'all':
        # get route neighbors info
        route_neighbors = None
        try:
            route_neighbors = get_route_neighbors(module)
        except Exception as e:
            logging.warning(e)
        result['ansible_facts']['ansible_net_route_neighbors'] = route_neighbors
    if fact_type == 'vrfs' or fact_type == 'all':
        # get VRF info
        result['ansible_facts']['ansible_net_vrfs'] = get_vrfs(module, operating_system)
    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
