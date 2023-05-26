#!/bin/bash
set -e
SCRIPT=$(readlink -f $0)
SCRIPTPATH=`dirname $SCRIPT`

rm -r -f $SCRIPTPATH/.env
python3.11 -m venv $SCRIPTPATH/.env
source $SCRIPTPATH/.env/bin/activate
pip install wheel
pip install -r $SCRIPTPATH/requirements.txt
pip install -r $SCRIPTPATH/requirements.dev.txt
