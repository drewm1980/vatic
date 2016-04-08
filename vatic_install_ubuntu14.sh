
sudo apt-get install git libavcodec-dev libavformat-dev libswscale-dev libjpeg62 libjpeg62-dev libfreetype6 libfreetype6-dev mysql-server-5.5 mysql-client-5.5 libmysqlclient-dev gfortran 

sudo apt-get install python-setuptools python-dev 
sudo apt-get install python-pil
sudo apt-get install python-virtualenv

sudo apt-get install python-opencv

# Purge a bunch of stuff install by pip that is visible to all users
sudo apt-get remove cython
sudo pip uninstall cython
sudo pip uninstall pysql
sudo pip uninstall turkic
sudo rm /usr/local/bin/turkic
sudo rm -rf /usr/local/lib/python2.7/dist-packages/pymysql
sudo rm -rf /usr/local/lib/python2.7/dist-packages/PyMySQL*
sudo pip uninstall werkzeug

mkdir vatic_virtualenv
cd vatic_virtualenv
source bin/activate

#sudo pip install cython==0.20 # Also no Cython.DistUtils
pip install cython # 0.23.4 as of Mar 1 2016. Doesn't have Cython.DistUtils
pip install werkzeug
pip install wsgilog
pip install pysql-python
pip install munkres
pip install parsedatetime
pip install argparse
pip install numpy
#sudo pip install PIL

cp /usr/lib/python2.7/dist-packages/cv2.so ./lib/python2.7/site-packages/
cp /usr/lib/python2.7/dist-packages/cv.py ./lib/python2.7/site-packages/

git clone https://github.com/johndoherty/turkic.git
git clone https://github.com/cvondrick/pyvision.git
git clone https://github.com/johndoherty/vatic.git
git clone https://github.com/johndoherty/vatic_tracking.git

cd turkic
python setup.py install
cd ..

cd pyvision
python setup.py install
cd ..

cd vatic_tracking
python setup.py install
cd ..

echo "NOTE: If PIL was installed without JPEG, ZLIB, or FREETYPE2 it means it could not find some of the libraries installed earier."
echo "Follow the instructions at: http://jj.isgeek.net/2011/09/install-pil-with-jpeg-support-on-ubuntu-oneiric-64bits/"

echo "*****************************************************"
echo "*** Please consult README to finish installation. ***"
echo "*****************************************************"
