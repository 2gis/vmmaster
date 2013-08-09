# dependenies:
+ nmap
+ libvirt
+ netifaces

# commands to create qcow2 VM's origins
+ qemu-img create -f qcow2 -o preallocation=metadata ubuntu-13.04-x64-origin.qcow2 8G
+ sudo virt-install --connect=qemu:///system --name ubuntu-13.04-x64-origin --network=bridge:virbr0 --ram 2048 --vcpus 2 --disk path=/home/vmmaster/vmmaster/origins/ubuntu-13.04-x64-origin.qcow2,format=qcow2,bus=virtio,cache=none --cdrom /home/vmmaster/ubuntu-13.04-desktop-amd64.iso --vnc --accelerate --os-type=linux --os-variant=generic26 --hvm