
#!/bin/bash
# Script: get_temp.sh
# Purpose: Display the ARM CPU and GPU  temperature of Raspberry Pi 4 
# Author: Max Parker
# -------------------------------------------------------


while true; do
    cpu=$(</sys/class/thermal/thermal_zone0/temp)
    echo "$(date) @ $(hostname)"
    echo "-------------------------------------------"
    echo "GPU => $(/opt/vc/bin/vcgencmd measure_temp)"
    echo "CPU => $((cpu/1000))'C"
    echo 
    echo 
    echo 
    sleep 1
done