#!/bin/bash
SCRIPT=$(readlink -f $0)
SCRIPTPATH=`dirname $SCRIPT`

rm -r -f $SCRIPTPATH/.env
python3.10 -m venv $SCRIPTPATH/.env
source $SCRIPTPATH/.env/bin/activate
pip install wheel
pip install -r $SCRIPTPATH/requirements.txt
