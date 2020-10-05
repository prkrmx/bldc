#!/bin/bash

# DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
DIR="${PWD%/*}" 

usage () {
	echo "# usage: ./build.sh (component-name)"
	echo "# (optional) valid component names are: opencv, pigpio, libuvc, all"
	exit 1
}

installIfMissing () {
	dpkg -s $@ > /dev/null
	if [ $? -ne 0 ]; then
		echo "# - missing $@, installing dependency"
		sudo apt-get install $@ -y
	fi
}

sayAndDo () {
	echo $@
	eval $@
	if [ $? -ne 0 ]; then
		echo "# ERROR: command failed!"
		exit 1
	fi
}


COMPONENT="all"
if [ ! -z "$1" ]; then
	COMPONENT="$1"
	echo "# single component specified"
	if [ "$COMPONENT" == "opencv" ] || [ "$COMPONENT" == "pigpio" ] || [ "$COMPONENT" == "libuvc" ]; then
		echo "# - found, building and installing $COMPONENT"
	else
		echo "# - ERROR : invalid component ($COMPONENT)"
		usage
	fi
fi

echo "# update the system"
sayAndDo sudo apt-get update
sayAndDo sudo apt-get upgrade -y
echo "# - done"
echo

echo "# adding additional tools"
installIfMissing vim
installIfMissing locate
#installIfMissing xscreensaver
echo "# - done"
echo

echo "# go to parent directory path: $DIR"
sayAndDo cd $DIR

if [ "$COMPONENT" == "all" ] || [ "$COMPONENT" == "opencv" ]; then
	echo "#####################################################################"
	echo "# opencv - building and installing"
	echo "# checking build dependencies"

#	sayAndDo	sudo rpi-update -y

	installIfMissing	build-essential
	installIfMissing	cmake
	installIfMissing	pkg-config
    installIfMissing    libjpeg-dev
	installIfMissing    libpng-dev
	installIfMissing    libtiff-dev
	installIfMissing    openexr
    installIfMissing    libtiff5-dev 
    installIfMissing    libjasper-dev 
    installIfMissing    libpng12-dev
    installIfMissing    libavcodec-dev 
    installIfMissing    libavformat-dev 
    installIfMissing    libswscale-dev 
    installIfMissing    libv4l-dev
    installIfMissing    libxvidcore-dev 
    installIfMissing    libx264-dev
    installIfMissing    libgtk2.0-dev 
    installIfMissing    libgtk-3-dev
    installIfMissing    libatlas-base-dev 
    installIfMissing    gfortran
    installIfMissing    python3-dev
    installIfMissing    python3-pip
	installIfMissing    python3-pyqt5
	installIfMissing    python3-numpy
	installIfMissing    libtbb2 
	installIfMissing    libtbb-dev 
	installIfMissing    libdc1394-22-dev
	installIfMissing    libopenexr-dev
    installIfMissing    libgstreamer-plugins-base1.0-dev 
	installIfMissing    libgstreamer1.0-dev

    # sayAndDo    sudo pip3 install numpy
	# sayAndDo    sudo pip3 install face_recognition
	sayAndDo    git clone https://github.com/opencv/opencv.git
    sayAndDo    git clone https://github.com/opencv/opencv_contrib.git
	sayAndDo    cd opencv
	# sayAndDo  git tag -l
	# sayAndDo  git checkout 4.4.0
	sayAndDo    mkdir build
	sayAndDo    cd build
	sayAndDo    cmake -D CMAKE_BUILD_TYPE=RELEASE \
				-D CMAKE_INSTALL_PREFIX=/usr/local \
				-D INSTALL_PYTHON_EXAMPLES=ON \
				-D OPENCV_GENERATE_PKGCONFIG=ON \
				-D OPENCV_EXTRA_MODULES_PATH="$DIR"/opencv_contrib/modules \
				-D BUILD_EXAMPLES=ON ..
	sayAndDo    make -j$(nproc)
	sayAndDo	sudo make install
	sayAndDo	sudo ldconfig
	sayAndDo	cd $DIR
	echo "# - done"
	echo
fi


if [ "$COMPONENT" == "all" ] || [ "$COMPONENT" == "pigpio" ]; then
	echo "#####################################################################"
	echo "# pigpio - building and installing"
	echo "# checking build dependencies"
	installIfMissing	python-setuptools
	installIfMissing	python3-setuptools

	sayAndDo 	git clone https://github.com/joan2937/pigpio.git
	sayAndDo 	cd pigpio
	sayAndDo 	make -j$(nproc)
	sayAndDo 	sudo make install
	sayAndDo 	sudo ldconfig
	sayAndDo 	cd $DIR
	echo "# - done"
	echo
fi

if [ "$COMPONENT" == "all" ] || [ "$COMPONENT" == "libuvc" ]; then
	echo "#####################################################################"
	echo "# libuvc - building and installing"
	echo "# checking build dependencies"
	installIfMissing	libusb-1.0-0-dev
	installIfMissing	libjpeg-dev

	sayAndDo 	git clone https://github.com/groupgets/libuvc
	sayAndDo 	cd libuvc
	sayAndDo    mkdir build
	sayAndDo    cd build
	sayAndDo	cmake ..
	sayAndDo 	make -j$(nproc)
	sayAndDo 	sudo make install
	sayAndDo	sudo ldconfig
	sayAndDo 	cd $DIR
	echo "# - done"
	echo
fi


#####################################################################
# VIM INSERT BUG:
# sudo vi /usr/share/vim/vim81/defaults.vim
#	set mouse-=a

# To increase the swap size OPENCV
# sudo vi /etc/dphys-swapfile
#	CONF_SWAPSIZE=2048

# Mouse issue 
# sudo vi /boot/cmdline.txt
#	usbhid.mousepoll=0

# Monitor not full screen
# sudo vi /boot/config.txt
# 	disable_overscan=1

# sudo vi /etc/ssh/sshd_config
# 	PermitRootLogin yes
# /etc/init.d/ssh restart
# sudo passwd root