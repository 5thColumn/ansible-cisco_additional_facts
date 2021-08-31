# ansible-cisco_additional_facts
This Ansible module is intended to gather more detailed facts about Cisco devices, such as route tables, MAC address tables, VRFs, and more. Currently supports IOS and NX-OS devices. It also adds a gather interfaces function that actually works properly for NX-OS devices as opposed to the default gather_facts module that does not properly gather interface details.
### Options / Module Arguments
#### fact_type
* Description: Specify the type of fact(s) to gather.
* Supported types: all, interfaces, inventory, license, mac_address_table, routes, route_neighbors, vrfs
* Required: False
* Default: all
* Notes: Recommend not using "all" as it will often result in a command timeout due to long-running operations.
